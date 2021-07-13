import asyncio
import datetime
import json
import logging
import multiprocessing
import os
import threading
import time
from http import HTTPStatus
from urllib.parse import urlparse

import requests

from nempy.utils.measure_latency import measure_latency
from nempy.xym import constants
from nempy.xym.constants import BlockchainStatuses
from . import ed25519

logging.basicConfig(level=logging.DEBUG)


def send_transaction(payload: bytes) -> bool:
    headers = {'Content-type': 'application/json'}
    try:
        answer = requests.put(f'{node_selector.url}/transactions', data=payload, headers=headers, timeout=10)
    except ConnectionError:
        return False
    if answer.status_code == HTTPStatus.ACCEPTED:
        return True
    return False


def check_transaction_confirmation(transaction_hash):
    timeout = 10
    endpoint = f'{node_selector.url}/transactions/confirmed/{transaction_hash}'
    try:
        answer = requests.get(endpoint, timeout=timeout)
        if answer.status_code == 200:
            return True
        if answer.status_code == 404:
            return False
        if answer.status_code == 409:
            # logger.error(str(answer.json()))
            return False
    except Exception as e:
        # logger.error(str(e))
        return False


def get_network_properties():
    answer = requests.get(f'{node_selector.url}/network/properties')
    if answer.status_code == HTTPStatus.OK:
        network_properties = json.loads(answer.text)
        return network_properties
    answer.raise_for_status()


def get_node_network():
    answer = requests.get(f'{node_selector.url}/node/info')
    if answer.status_code == HTTPStatus.OK:
        fee_info = json.loads(answer.text)
        network_generation_hash_seed = fee_info['networkGenerationHashSeed']
        if network_generation_hash_seed == constants.NETWORK_GENERATION_HASH_SEED_TEST:
            return 'public_test'
        elif network_generation_hash_seed == constants.NETWORK_GENERATION_HASH_SEED_PUBLIC:
            return 'public'
        else:
            return None
    answer.raise_for_status()


def get_block_information(height: int):
    answer = requests.get(f'{node_selector.url}/blocks/{height}')
    if answer.status_code == HTTPStatus.OK:
        block_info = json.loads(answer.text)
        return block_info
    answer.raise_for_status()


def get_fee_multipliers():
    answer = requests.get(f'{node_selector.url}/network/fees/transaction')
    if answer.status_code == HTTPStatus.OK:
        fee_multipliers = json.loads(answer.text)
        return fee_multipliers
    answer.raise_for_status()


def get_divisibility(mosaic_id: str):
    answer = requests.get(f'{node_selector.url}/mosaics/{mosaic_id}')
    node_info = json.loads(answer.text)
    divisibility = int(node_info['mosaic']['divisibility'])
    if answer.status_code == HTTPStatus.OK:
        return divisibility
    answer.raise_for_status()


def get_balance(address: str, mosaic_filter: [list, str] = None, is_linked: bool = False) -> (dict, int):
    if ed25519.check_address(address):
        endpoint = f'{node_selector.url}/accounts/{address}'
        answer = requests.get(endpoint)
        if answer.status_code != HTTPStatus.OK:
            return answer.text, answer.status_code
        address_info = json.loads(answer.text)
        mosaics = address_info['account']['mosaics']
        balance = {}
        for mosaic in mosaics:
            div, status_code = get_divisibility(mosaic['id'])
            if status_code != HTTPStatus.OK:
                return div, status_code
            amount = int(mosaic['amount']) / 10 ** div
            balance[mosaic['id']] = amount
        if mosaic_filter is not None:
            if isinstance(mosaic_filter, str):
                mosaic_filter = [mosaic_filter]
            filtered_balance = {key: balance[key] for key in mosaic_filter}
            return filtered_balance, HTTPStatus.OK
        return balance, HTTPStatus.OK
    else:
        return 'Incorrect wallet address', HTTPStatus.BAD_REQUEST


class NodeSelector:
    _URL: str = None
    _URLs: list = None
    _sorted_URLs = None

    def __init__(self, node_urls: list[str], logger=None):
        self.logger = logging.getLogger(os.path.splitext(os.path.basename(__file__))[0]) if logger is None else logger
        self._URLs = node_urls
        # hourly update of the node in case it appears more relevant
        self.actualizer = threading.Thread(target=self.node_actualizer, kwargs={'interval': 3}, daemon=True)
        self.actualizer.start()

    def node_actualizer(self, interval):
        asyncio.set_event_loop(asyncio.new_event_loop())
        while True:
            self.reselect_node()
            time.sleep(interval)

    @property
    def url(self):
        if self.health(self._URL) != BlockchainStatuses.OK:
            self.reselect_node()
        return self._URL

    def reselect_node(self):
        self.logger.debug('Node reselecting...')
        heights = [NodeSelector.get_height(url) for url in self._URLs]
        max_height = max(heights)
        heights_filter = [True if height >= max_height * 0.97 else False for height in heights]
        # filtered by block height - 97%
        filtered_by_height = [url for i, url in enumerate(self._URLs) if heights_filter[i]]
        urls_p_h = {url: (NodeSelector.ping(url), NodeSelector.simple_health(url)) for url in filtered_by_height}
        # Remove non-working nodes from the dict
        working = {key: val for key, val in urls_p_h.items() if val[1]}
        self._sorted_URLs = [k for k, v in sorted(working.items(), key=lambda item: item[1][0])]
        new_url = self._sorted_URLs[0] if len(self._sorted_URLs) > 0 else None
        if new_url != self._URL and self._URL is not None:
            self.logger.warning(f'Reselection node: {self._URL} -> {new_url}')
        if new_url is None:
            self.logger.error('It was not possible to select the current node from the list of available ones')
        self._URL = new_url

    @staticmethod
    def health(url):
        if url is None:
            return BlockchainStatuses.NO_NODES_AVAILABLE
        try:
            answer = requests.get(f'{url}/node/health', timeout=1)
        except:
            return BlockchainStatuses.REST_FAILURE
        if answer.status_code == HTTPStatus.OK:
            node_info = json.loads(answer.text)
            if node_info['status']['apiNode'] == 'up' and node_info['status']['db'] == 'up':
                return BlockchainStatuses.OK
            if node_info['status']['apiNode'] == 'down':
                return BlockchainStatuses.NODE_FAILURE
            if node_info['status']['db'] == 'down':
                return BlockchainStatuses.DB_FAILURE
        return BlockchainStatuses.UNKNOWN

    @staticmethod
    def simple_health(url):
        health_status = NodeSelector.health(url)
        if health_status == BlockchainStatuses.OK:
            return True
        return False

    @staticmethod
    def get_height(url):
        try:
            answer = requests.get(f'{url}/chain/info', timeout=1)
        except:
            return 0
        node_info = json.loads(answer.text)
        height = node_info['height']
        return int(height)

    @staticmethod
    def ping(url):
        if multiprocessing.current_process().daemon:
            asyncio.set_event_loop(asyncio.new_event_loop())
        parse_result = urlparse(url)
        loop = asyncio.get_event_loop()
        latency = loop.run_until_complete(measure_latency(host=parse_result.hostname, port=parse_result.port, runs=5))
        if (result := len(list(filter(None, latency)))) == 0:
            return None
        average = sum(filter(None, latency)) / result
        return average


node_selector = NodeSelector(os.getenv('NIS_URLs', 'http://192.168.0.103:3000').replace(' ', '').split(","))


class Timing:

    def __init__(self):
        network_properties = get_network_properties()
        epoch_adjustment = int(network_properties['network']['epochAdjustment'][0:-1])
        self.datetime = datetime.datetime.fromtimestamp(epoch_adjustment, tz=datetime.timezone.utc)

    def calc_deadline(self, days: float = 0, seconds: float = 0, milliseconds: float = 0,
                      minutes: float = 0, hours: float = 0, weeks: float = 0):

        if days + seconds + milliseconds + minutes + hours + weeks <= 0:
            raise TimeoutError('Added time must be positive otherwise the transaction will not have time to process')
        # perhaps this code will be needed if you need to get time from a node
        # node_info = json.loads(requests.get(endpoint).text)
        # receive_timestamp = int(node_info['communicationTimestamps']['receiveTimestamp'])
        # td = datetime.timedelta(milliseconds=receive_timestamp)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        td = now - self.datetime
        td += datetime.timedelta(days=days, seconds=seconds,
                                 milliseconds=milliseconds, minutes=minutes,
                                 hours=hours, weeks=weeks)
        deadline = int(td.total_seconds() * 1000)
        return deadline


