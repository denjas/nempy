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
from typing import Optional, Union
import requests

from nempy.utils.sym.measure_latency import measure_latency
from nempy.sym.constants import BlockchainStatuses, EPOCH_TIME_TESTNET, EPOCH_TIME_MAINNET, NetworkType
from . import ed25519, constants, config
from .constants import TransactionStatus


logger = logging.getLogger(os.path.splitext(os.path.basename(__name__))[0])


class SymbolNetworkException(Exception):

    def __init__(self, error):
        err = json.loads(error.text)
        super(SymbolNetworkException, self).__init__(err['code'], err['message'])


def send_transaction(payload: bytes) -> bool:
    headers = {'Content-type': 'application/json'}
    try:
        answer = requests.put(f'{node_selector.url}/transactions', data=payload, headers=headers, timeout=10)
    except ConnectionError as e:
        logger.error(str(e))
        return False
    if answer.status_code == HTTPStatus.ACCEPTED:
        return True
    logger.error(answer.text)
    return False


def get_mosaic_names(mosaics: [list, str]) -> Optional[dict]:
    if isinstance(mosaics, str):
        mosaics = [mosaics]
    data = {'mosaicIds': mosaics}
    headers = {'Content-type': 'application/json'}
    try:
        answer = requests.post(f'{node_selector.url}/namespaces/mosaic/names', json=data, headers=headers, timeout=10)
    except ConnectionError as e:
        logger.error(str(e))
        return None
    if answer.status_code == HTTPStatus.OK:
        return json.loads(answer.text)
    else:
        logger.error(answer.text)
    return None


def get_accounts_info(address: str) -> Optional[dict]:
    if not ed25519.check_address(address):
        logger.error(f'Incorrect wallet address: `{address}`')
        return None
    endpoint = f'{node_selector.url}/accounts/{address}'
    try:
        answer = requests.get(endpoint)
    except Exception as e:
        logger.error(e)
        return None
    if answer.status_code != HTTPStatus.OK:
        logger.error(answer.text)
        if answer.status_code == HTTPStatus.NOT_FOUND:
            logger.error('Invalid recipient account info')
            return {}
        return None
    address_info = json.loads(answer.text)
    return address_info


def check_transaction_state(transaction_hash):
    timeout = 10
    check_order = ['confirmed', 'unconfirmed', 'partial']
    status = TransactionStatus.NOT_FOUND
    for checker in check_order:
        endpoint = f'{node_selector.url}/transactions/{checker}/{transaction_hash}'
        try:
            answer = requests.get(endpoint, timeout=timeout)
        except Exception as e:
            logger.error(str(e))
            return None
        if answer.status_code == 200:
            if checker == 'confirmed':
                status = TransactionStatus.CONFIRMED_ADDED
            if checker == 'unconfirmed':
                status = TransactionStatus.UNCONFIRMED_ADDED
            if checker == 'partial':
                status = TransactionStatus.PARTIAL_ADDED
        if answer.status_code == HTTPStatus.CONFLICT:
            logger.error(answer.text)
    return status


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
    try:
        answer = requests.get(f'{node_selector.url}/network/fees/transaction')
    except Exception as e:
        logger.error(e)
        return None
    if answer.status_code == HTTPStatus.OK:
        fee_multipliers = json.loads(answer.text)
        return fee_multipliers
    return None


def get_divisibility(mosaic_id: str):
    try:
        answer = requests.get(f'{node_selector.url}/mosaics/{mosaic_id}')
    except Exception as e:
        logger.error(e)
        return None
    if answer.status_code == HTTPStatus.OK:
        node_info = json.loads(answer.text)
        divisibility = int(node_info['mosaic']['divisibility'])
        return divisibility
    err = json.loads(answer.text)
    logger.error(f"{err['code']}: {err['message']}")
    return None


def get_balance(address: str, mosaic_filter: [list, str] = None, is_linked: bool = False) -> Optional[dict]:
    if isinstance(mosaic_filter, str):
        mosaic_filter = [mosaic_filter]
    if mosaic_filter is None:
        mosaic_filter = []
    for mosaic_id in mosaic_filter:
        if not ed25519.check_hex(mosaic_id, constants.HexSequenceSizes.mosaic_id):
            logger.error(f'Incorrect mosaic ID: `{mosaic_id}`')
            return None
    address_info = get_accounts_info(address)
    mosaics = address_info['account']['mosaics']
    balance = {}
    for mosaic in mosaics:
        div = get_divisibility(mosaic['id'])
        if div is None:
            return None
        balance[mosaic['id']] = int(mosaic['amount']) / 10 ** div
    if mosaic_filter:
        filtered_balance = {key: balance.get(key) for key in mosaic_filter if key in balance}
        return filtered_balance
    return balance


class Timing:

    def __init__(self, network_type: str = None):
        if network_type is None:
            network_properties = get_network_properties()
            epoch_adjustment = int(network_properties['network']['epochAdjustment'][0:-1])
            self.epoch_time = datetime.datetime.fromtimestamp(epoch_adjustment, tz=datetime.timezone.utc)
        elif network_type == 'public_test':
            self.epoch_time = EPOCH_TIME_TESTNET
        elif network_type == 'public':
            self.epoch_time = EPOCH_TIME_MAINNET
        else:
            raise EnvironmentError()

    def calc_deadline(self, days: float = 0, seconds: float = 0, milliseconds: float = 0,
                      minutes: float = 0, hours: float = 0, weeks: float = 0):

        if days + seconds + milliseconds + minutes + hours + weeks <= 0:
            raise TimeoutError('Added time must be positive otherwise the transaction will not have time to process')
        # perhaps this code will be needed if you need to get time from a node
        # node_info = json.loads(requests.get(endpoint).text)
        # receive_timestamp = int(node_info['communicationTimestamps']['receiveTimestamp'])
        # td = datetime.timedelta(milliseconds=receive_timestamp)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        td = now - self.epoch_time
        td += datetime.timedelta(days=days, seconds=seconds,
                                 milliseconds=milliseconds, minutes=minutes,
                                 hours=hours, weeks=weeks)
        deadline = int(td.total_seconds() * 1000)
        return deadline


class NodeSelector:
    _URL: str = None
    _URLs: list = None
    _sorted_URLs = None
    _re_elections = False
    _network_type = NetworkType.TEST_NET

    def __init__(self, node_urls: [list[str], str]):
        self.url = node_urls

    @property
    def network_type(self):
        return self._network_type

    @network_type.setter
    def network_type(self, network_type):
        if network_type == self.network_type:
            return
        self._network_type = network_type
        if self._network_type == NetworkType.MAIN_NET:
            logger.debug('Switch to MAIN network')
            self.url = config.MAIN_NODE_URLs
        elif self._network_type == NetworkType.TEST_NET:
            logger.debug('Switch to TEST network')
            self.url = config.TEST_NODE_URLs
        else:
            raise TypeError('Unknown network type')

    def node_actualizer(self, interval):
        asyncio.set_event_loop(asyncio.new_event_loop())
        while True:
            self._re_elections = False
            self.reelection_node()
            if self._re_elections is None:
                break
            self._re_elections = True
            time.sleep(interval)
            if self._re_elections is None:
                break
        logger.debug('The node actualization thread has been stopped.')

    @property
    def url(self):
        if self._re_elections is None:
            return self._URL
        # waiting for the node re-election
        while not self._re_elections:
            time.sleep(0.5)
        if self.health(self._URL) != BlockchainStatuses.OK:
            self.reelection_node()
        return self._URL

    @url.setter
    def url(self, value):
        if isinstance(value, str):
            value = [value]
        self._URLs = value
        if len(self._URLs) == 1:
            self._re_elections = None
            self._URL = self._URLs[0]
            logger.debug(f'Selected node: {self._URL}')
        else:
            #  if the daemon is running and not actualizing right now
            if self._re_elections:  # not started and not waiting
                # actualize and exit
                self.reelection_node()
                return
            # hourly update of the node in case it appears more relevant
            self.actualizer = threading.Thread(target=self.node_actualizer, kwargs={'interval': 3600}, daemon=True)
            self.actualizer.start()

    def reelection_node(self):
        logger.debug('Node reselecting...')
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
        if self._re_elections is not None:
            if new_url != self._URL and self._URL is not None:
                logger.warning(f'Reselection node: {self._URL} -> {new_url}')
            if new_url is None:
                logger.error('It was not possible to select the current node from the list of available ones')
            self._URL = new_url
            logger.debug(f'Selected node: {self._URL}')

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
        latency = loop.run_until_complete(measure_latency(host=parse_result.hostname, port=parse_result.port, runs=3))
        if (result := len(list(filter(None, latency)))) == 0:
            return None
        average = sum(filter(None, latency)) / result
        return average


# singleton for background work with the list of nodes
node_selector = NodeSelector(config.TEST_NODE_URLs)
