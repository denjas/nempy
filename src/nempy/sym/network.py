import asyncio
import datetime
import json
import logging
import multiprocessing
import threading
import time
import re
from base64 import b32encode
from binascii import unhexlify
from http import HTTPStatus
from typing import Optional, Union, List, Callable, Dict
from urllib.parse import urlparse
from requests.exceptions import RequestException

import requests
import websockets
from nempy.sym.constants import BlockchainStatuses, EPOCH_TIME_TESTNET, EPOCH_TIME_MAINNET, NetworkType, \
    TransactionTypes, AccountValidationState
from pydantic import BaseModel, StrictInt, StrictFloat
from symbolchain.core.CryptoTypes import Hash256
from symbolchain.core.facade.SymFacade import SymFacade
from tabulate import tabulate
from websockets import exceptions

from . import ed25519, constants, config
from .constants import TransactionStatus

logger = logging.getLogger(__name__)


class SymbolNetworkException(Exception):
    """Is one exception for the convenience of working with the blockchain network"""
    codes = {
        'ResourceNotFound': 404,
        'InvalidAddress': 409,
        'InvalidArgument': 409,
        'InvalidContent': 400,
        'Internal': 500,
    }

    def __init__(self, code, message):
        self.code = self.codes.get(code)
        self.name = code
        self.message = message
        super(SymbolNetworkException, self).__init__(f'{self.code} - {self.name}', self.message)


def url_validation(url):
    """django URL validation regex
    Raise an exception if the url is not valid"""
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    if re.match(regex, url) is None:
        raise ValueError(f'`{url}` is not a valid URL')


def mosaic_id_to_name_n_real(mosaic_id: str, amount: int) -> Dict[str, float]:
    """
    Converts mosaic identifiers to names and integer numbers to real numbers.

    Parameters
    ----------
    mosaic_id
        Mosaic ID as string
    amount
        Mosaic units in Symbol are defined as absolute amounts. To get an absolute amount,
        multiply the amount of assets you want to create or send by 10^divisibility.
        For example, if the mosaic has divisibility 2, to create or send 10 units (relative)
        you should define 1,000 (absolute) instead.
    Returns
    -------
    Dict[str, float]
        A dictionary with a name and a real amount value. For example
    ```py
    {'id': 'symbol.xym', 'amount': 1.1}
    ```
    """
    if not isinstance(amount, int):
        raise TypeError('To avoid confusion, automatic conversion to integer is prohibited')
    divisibility = get_divisibility(mosaic_id)
    divider = 10 ** int(divisibility)
    mn = get_mosaic_names(mosaic_id)
    name = mosaic_id
    names = mn['mosaicNames'][0]['names']
    if len(names) > 0:
        name = names[0]
    return {'id': name, 'amount': float(amount / divider)}


class Meta(BaseModel):
    """Transaction meta information"""
    height: int
    hash: str
    merkleComponentHash: str
    index: int


class MosaicInfo(BaseModel):
    """Mosaic information in a transaction"""
    id: str
    amount: Union[StrictInt, StrictFloat]

    def __str__(self):
        return f'{self.amount}({self.id})'


class TransactionInfo(BaseModel):
    """Contains information about transactions of the blockchain network"""
    size: int
    signature: str
    signerPublicKey: str
    version: int
    network: int
    type: Union[int, str]
    maxFee: int
    deadline: Union[int, datetime.datetime]
    recipientAddress: str
    message: Optional[str]
    signer_address: Optional[str]
    mosaics: List[MosaicInfo]

    def humanization(self):
        """Converts information from the blockchain into a readable form"""
        self.deadline = Timing().deadline_to_date(self.deadline)
        if self.message is not None:
            self.message = unhexlify(self.message)[1:].decode('utf-8')
        self.recipientAddress = b32encode(unhexlify(self.recipientAddress)).decode('utf-8')[:-1]
        self.mosaics = [MosaicInfo(**mosaic_id_to_name_n_real(mosaic.id, mosaic.amount)) for mosaic in self.mosaics]
        self.type = TransactionTypes.get_type_by_id(self.type).name
        facade = SymFacade(node_selector.network_type.value)
        self.signer_address = str(facade.network.public_key_to_address(Hash256(self.signerPublicKey)))


class TransactionResponse(BaseModel):
    id: str
    meta: Meta
    transaction: TransactionInfo
    status: Optional[str]

    def __str__(self):
        if self.transaction.signer_address.startswith('T'):
            test_net_explorer = 'http://explorer.testnet.symboldev.network/transactions/'
        else:
            test_net_explorer = 'http://explorer.symbolblockchain.io/transactions/'
        prepare = list()
        mosaics = [str(mosaic) for mosaic in self.transaction.mosaics]
        mosaics = '\n'.join(mosaics)
        prepare.append(['Type:', self.transaction.type.title()])
        prepare.append(['Status:', self.status.title()])
        prepare.append(['Hash:', f'{test_net_explorer}{self.meta.hash}'])
        prepare.append(['Paid Fee:', f'{self.transaction.maxFee / 1000000}(XYM)'])
        prepare.append(['Height:', self.meta.height])
        prepare.append(['Deadline:', self.transaction.deadline])
        prepare.append(['Signature:', self.transaction.signature])
        prepare.append(['Signer Public Key:', self.transaction.signerPublicKey])
        prepare.append(['From:', self.transaction.signer_address])
        prepare.append(['To:', self.transaction.recipientAddress])
        prepare.append(['Mosaic:', mosaics])
        prepare.append(['Message:', self.transaction.message])
        table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
        return table


def send_transaction(payload: bytes) -> bool:
    """Announces a transaction to the network"""
    try:
        headers = {'Content-type': 'application/json'}
        answer = requests.put(f'{node_selector.url}/transactions', data=payload, headers=headers, timeout=10)
        if answer.status_code != HTTPStatus.ACCEPTED:
            raise SymbolNetworkException(**answer.json())
    except (RequestException, SymbolNetworkException) as e:
        logger.exception(e)
        return False
    else:
        return True


def get_mosaic_names(mosaics_ids: Union[list, str]) -> Optional[dict]:
    """
    Get readable names for a set of mosaics.

    Parameters
    ----------
    mosaics_ids
        IDs of mosaic as list or str if there is only one mosaic
    Returns
    -------
    Optional[Dict[str, list]]
        dict of mosaics. For example:
    ```py
    {"mosaicNames": [{"mosaicId": "091F837E059AE13C", "names": ["symbol.xym"]}]}
    ```
    """
    if isinstance(mosaics_ids, str):
        mosaics_ids = [mosaics_ids]
    try:
        for mosaic_id in mosaics_ids:
            if not ed25519.check_hex(mosaic_id, constants.HexSequenceSizes.MOSAIC_ID):
                raise SymbolNetworkException('InvalidArgument', f'mosaicId `{mosaic_id}` has an invalid format')
        payload = {'mosaicIds': mosaics_ids}
        headers = {'Content-type': 'application/json'}
        answer = requests.post(f'{node_selector.url}/namespaces/mosaic/names', json=payload, headers=headers, timeout=10)
        if answer.status_code != HTTPStatus.OK:
            raise SymbolNetworkException(**answer.json())
    except (RequestException, SymbolNetworkException) as e:
        logger.exception(e)
        raise
    else:
        return answer.json()


def get_accounts_info(address: str) -> Optional[dict]:
    try:
        if (avs := ed25519.check_address(address)) != AccountValidationState.OK:
            raise SymbolNetworkException('InvalidAddress', f'Incorrect account address: `{address}`: {avs}')
        endpoint = f'{node_selector.url}/accounts/{address}'
        answer = requests.get(endpoint)
        if answer.status_code != HTTPStatus.OK:
            return None
    except RequestException as e:
        logger.exception(e)
        raise
    except SymbolNetworkException as e:
        logger.exception(e)
        raise
    else:
        return answer.json()


def search_transactions(address: Optional[str] = None,
                        recipient_address: Optional[str] = None,
                        signer_public_key: Optional[str] = None,
                        height: Optional[int] = None,
                        from_height: Optional[int] = None,
                        to_height: Optional[str] = None,
                        from_transfer_amount: Optional[str] = None,
                        to_transfer_amount: Optional[str] = None,
                        type: int = 16724,
                        embedded: bool = False,
                        transfer_mosaic_id: Optional[str] = None,
                        page_size: int = 10,
                        page_number: int = 1,
                        offset: Optional[str] = None,
                        order: str = 'desc',
                        transaction_status: TransactionStatus = TransactionStatus.CONFIRMED_ADDED
                        ) -> Optional[list]:
    params = {
        'address': address,
        'recipientAddress': recipient_address,
        'signerPublicKey': signer_public_key,
        'height': height,
        'fromHeight': from_height,
        'toHeight': to_height,
        'fromTransferAmount': from_transfer_amount,
        'toTransferAmount': to_transfer_amount,
        'type': type,
        'embedded': str(embedded).lower(),
        'transferMosaicId': transfer_mosaic_id,
        'pageSize': page_size,
        'pageNumber': page_number,
        'offset': offset,
        'order': order
    }
    payload = {key: val for key, val in params.items() if val is not None}
    endpoint = f'{node_selector.url}/transactions/{transaction_status.value}'
    try:
        answer = requests.get(endpoint, params=payload)
        if answer.status_code != HTTPStatus.OK:
            raise SymbolNetworkException(**answer.json())
    except RequestException as e:
        logger.exception(e)
        raise
    except SymbolNetworkException as e:
        logger.exception(e)
        raise
    transactions = answer.json()
    transactions_response = []
    for transaction in transactions['data']:
        mosaics = [MosaicInfo(id=mosaic['id'], amount=int(mosaic['amount'])) for mosaic in transaction['transaction']['mosaics']]
        del(transaction['transaction']['mosaics'])
        _transaction = TransactionResponse(id=transaction['id'],
                                           meta=Meta(**transaction['meta']),
                                           transaction=TransactionInfo(mosaics=mosaics, **transaction['transaction'])
                                           )
        _transaction.status = transaction_status.value
        transactions_response.append(_transaction)
        _transaction.transaction.humanization()
    return transactions_response


def get_namespace_info(namespace_id: str) -> Optional[dict]:
    endpoint = f'{node_selector.url}/namespaces/{namespace_id}'
    try:
        answer = requests.get(endpoint)
    except Exception as e:
        logger.error(e)
        return None
    if answer.status_code != HTTPStatus.OK:
        logger.error(answer.text)
        if answer.status_code == HTTPStatus.NOT_FOUND:
            logger.error(f'Invalid namespace ID `{namespace_id}`')
            return {}
        return None
    namespace_info = answer.json()
    return namespace_info


def check_transaction_state(transaction_hash):
    timeout = 10
    check_order = ['confirmed', 'unconfirmed', 'partial']
    status = TransactionStatus.NOT_FOUND
    for checker in check_order:
        endpoint = f'{node_selector.url}/transactions/{checker}/{transaction_hash}'
        try:
            answer = requests.get(endpoint, timeout=timeout)
            if answer.status_code != 200:
                raise SymbolNetworkException(**answer.json())
        except (RequestException, SymbolNetworkException) as e:
            if isinstance(e, SymbolNetworkException) and e.code == 404:
                return TransactionStatus.NOT_FOUND
            logger.exception(e)
            raise
        else:
            if checker == 'confirmed':
                status = TransactionStatus.CONFIRMED_ADDED
            elif checker == 'unconfirmed':
                status = TransactionStatus.UNCONFIRMED_ADDED
            elif checker == 'partial':
                status = TransactionStatus.PARTIAL_ADDED
        return status


def get_network_properties():
    answer = requests.get(f'{node_selector.url}/network/properties')
    if answer.status_code == HTTPStatus.OK:
        network_properties = answer.json()
        return network_properties
    answer.raise_for_status()


def get_node_network():
    try:
        answer = requests.get(f'{node_selector.url}/node/info')
    except RequestException as e:
        logger.exception(e)
        raise
    if answer.status_code == HTTPStatus.OK:
        fee_info = answer.json()
        network_generation_hash_seed = fee_info['networkGenerationHashSeed']
        if network_generation_hash_seed == constants.NETWORK_GENERATION_HASH_SEED_TEST:
            return NetworkType.TEST_NET
        elif network_generation_hash_seed == constants.NETWORK_GENERATION_HASH_SEED_PUBLIC:
            return NetworkType.MAIN_NET
        else:
            return None
    answer.raise_for_status()


def get_block_information(height: int):
    answer = requests.get(f'{node_selector.url}/blocks/{height}')
    if answer.status_code == HTTPStatus.OK:
        block_info = answer.json()
        return block_info
    answer.raise_for_status()


def get_fee_multipliers():
    try:
        answer = requests.get(f'{node_selector.url}/network/fees/transaction')
    except RequestException as e:
        logger.exception(e)
        return None
    if answer.status_code == HTTPStatus.OK:
        fee_multipliers = answer.json()
        return fee_multipliers
    return None


def get_divisibility(mosaic_id: str) -> Optional[int]:
    try:
        if not ed25519.check_hex(mosaic_id, constants.HexSequenceSizes.MOSAIC_ID):
            raise SymbolNetworkException('InvalidArgument', f'mosaicId `{mosaic_id}` has an invalid format')
        answer = requests.get(f'{node_selector.url}/mosaics/{mosaic_id}')
        if answer.status_code == HTTPStatus.OK:
            node_info = answer.json()
            divisibility = int(node_info['mosaic']['divisibility'])
        else:
            raise SymbolNetworkException(**answer.json())
    except RequestException as e:
        logger.exception(e)
        raise
    except SymbolNetworkException as e:
        logger.exception(e)
        raise
    else:
        return divisibility


def get_divisibilities(n_pages: int = 0):
    mosaics = {}
    payload = {'pageSize': 100}

    page_count = 1
    while True:
        try:
            answer = requests.get(f'{node_selector.url}/mosaics', params=payload)
        except Exception as e:
            logger.error(e)
            return None
        if answer.status_code == HTTPStatus.OK:
            mosaics_pages = answer.json()['data']
            if len(mosaics_pages) == 0:
                return mosaics
            last_page = None
            for page in mosaics_pages:
                mosaic_id = page['mosaic']['id']
                divisibility = page['mosaic']['divisibility']
                mosaics[mosaic_id] = divisibility
                last_page = page
            payload['offset'] = last_page['id']
            page_count = page_count + 1 if n_pages else page_count
            if page_count > n_pages:
                return mosaics


def get_balance(address: str) -> Optional[dict]:
    try:
        address_info = get_accounts_info(address)
        if address_info is None:
            return {}
        mosaics = address_info['account']['mosaics']
        balance = {mosaic['id']: int(mosaic['amount']) / 10 ** get_divisibility(mosaic['id']) for mosaic in mosaics}
    except (SymbolNetworkException, RequestException) as e:
        if isinstance(e, SymbolNetworkException) and e.code == 404:
            return {}
        raise
    else:
        return balance


class Monitor:
    """Allows you to subscribe to events on the blockchain network"""
    where_to_subscribe = {
            'confirmedAdded': 'address',
            'unconfirmedAdded': 'address',
            'unconfirmedRemoved': 'address',
            'partialAdded': 'address',
            'partialRemoved': 'address',
            'cosignature': 'address',
            'status': 'address',
            'block': None,
            'finalizedBlock': None
    }

    def __init__(self,
                 url: str,
                 subscribers: List[str],
                 formatting: bool = False,
                 log: str = '',
                 callback: Optional[Callable] = None):
        self.url = url
        self.subscribers = subscribers
        self.formatting = formatting
        self.log = log
        self.callback = callback
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.monitoring())

    async def monitoring(self):
        result = urlparse(self.url)
        url = f"ws://{result.hostname}:{result.port}/ws"
        print(f'MONITORING: {url}')
        try:
            async with websockets.connect(url) as ws:
                response = json.loads(await ws.recv())
                print(f'UID: {response["uid"]}')
                if 'uid' in response:
                    prepare = []
                    for subscriber in self.subscribers:
                        added = json.dumps({"uid": response["uid"], "subscribe": f"{subscriber}"})
                        await ws.send(added)
                        # print(f'Subscribed to: {subscriber}')
                        prepare.append([subscriber])
                    table = tabulate(prepare, headers=['Subscribers'], tablefmt='grid')
                    print(table)
                    print('Listening... `Ctrl+C` for abort')
                    while True:
                        res = await ws.recv()
                        if self.formatting:
                            res = json.dumps(json.loads(res), indent=4)
                        if self.callback is not None:
                            self.callback(json.loads(res))
                            continue
                        print(res)
                        if self.log:
                            with open(self.log, 'a+') as f:
                                res += '\n'
                                f.write(res)
        except exceptions.WebSocketException as e:
            logger.exception(e)
            raise


class Timing:
    """Works with network time"""
    def __init__(self, network_type: Optional[NetworkType] = None):
        if network_type is None:
            network_type = node_selector.network_type
        if network_type == NetworkType.TEST_NET:
            self.epoch_time = EPOCH_TIME_TESTNET
        elif network_type == NetworkType.MAIN_NET:
            self.epoch_time = EPOCH_TIME_MAINNET
        else:
            raise EnvironmentError('It is not possible to determine the type of network')

    def calc_deadline(self, days: float = 0, seconds: float = 0, milliseconds: float = 0,
                      minutes: float = 0, hours: float = 0, weeks: float = 0) -> int:

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

    def deadline_to_date(self, deadline: int, is_local: bool = False) -> datetime:
        def utc2local(utc):
            utc_epoch = time.mktime(utc.timetuple())
            offset = datetime.datetime.fromtimestamp(utc_epoch) - datetime.datetime.utcfromtimestamp(utc_epoch)
            return utc + offset

        deadline = int(deadline)
        epoch_timestamp = datetime.datetime.timestamp(self.epoch_time)
        deadline_date_utc = datetime.datetime.utcfromtimestamp(epoch_timestamp + deadline / 1000)
        if is_local:
            local_deadline_date = utc2local(deadline_date_utc)
            return local_deadline_date
        return deadline_date_utc


class Thread:
    """A helper class for working with a thread, starting and stopping it by signals"""
    def __init__(self):
        self.stop_event: Optional[threading.Event] = None
        self.thread: Optional[threading.Thread] = None
        self.is_started = False
        self.updated = threading.Event()

    def stop(self):
        if self.thread is not None and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()
            self.is_started = False
            logger.debug(f'The node actualization thread {self.thread.name} has been stopped.')

    def start(self, func: Callable, interval: int = 3600):
        self.is_started = True
        self.stop_event = threading.Event()
        self.updated = threading.Event()
        params = {'interval': interval, 'stop_event': self.stop_event, 'updated': self.updated}
        self.thread = threading.Thread(target=func, kwargs=params, daemon=True)
        self.thread.start()
        logger.debug(f'New actualizer thread started: {self.thread.name}')
        return self

    def wait(self):
        updated_is_set = self.updated.wait(60)
        if not updated_is_set:
            raise RuntimeError('Very long waiting time for node selection')


class NodeSelector:
    """Works with a list of nodes in both the main and test networks.
       Offline finds the best connection options and makes adjustments if conditions change.
       Also allows you to add connections manually.
    """
    _URL: Optional[str] = None
    _URLs: Optional[list] = None
    is_elections: bool = False
    _network_type: NetworkType = NetworkType.TEST_NET

    def __init__(self, node_urls: Union[List[str], str]):
        self.thread = Thread()
        self.url = node_urls

    @property
    def url(self):
        while self.is_elections:
            time.sleep(0.1)
        return self._URL

    @url.setter
    def url(self, urls: Union[list, str]):
        self.is_elections = True
        self.thread.stop()
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            url_validation(url)
        self._URLs = urls
        if len(self._URLs) == 1:
            self._URL = self._URLs[0]  # setting a single URL value
            logger.debug(f'Installed node: {self._URL}')
        else:
            self.thread.start(self.node_actualizer, interval=3600).wait()
        self.is_elections = False

    def node_actualizer(self, interval, stop_event, updated):
        while True:
            self.reelection_node()
            updated.set()
            event_is_set = stop_event.wait(interval)
            if event_is_set:
                break

    def reelection_node(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        logger.debug('Node reselecting...')
        heights = [NodeSelector.get_height(url) for url in self._URLs]
        max_height = max(heights)
        heights_filter = [True if height >= max_height * 0.97 else False for height in heights]
        # filtered by block height - 97%
        filtered_by_height = [url for i, url in enumerate(self._URLs) if heights_filter[i]]
        urls_p_h = {url: (NodeSelector.ping(url), NodeSelector.simple_health(url)) for url in filtered_by_height}
        # Remove non-working nodes from the dict
        working = {key: val for key, val in urls_p_h.items() if val[1]}
        _sorted_URLs = [k for k, v in sorted(working.items(), key=lambda item: item[1][0])]
        new_url = _sorted_URLs[0] if len(_sorted_URLs) > 0 else None
        if new_url != self._URL and self._URL is not None:
            logger.warning(f'Reselection node: {self._URL} -> {new_url}')
        if new_url is None:
            logger.error('It was not possible to select the current node from the list of available ones')
        self._URL = new_url
        logger.debug(f'Selected node: {self._URL}')

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

    @staticmethod
    def health(url) -> BlockchainStatuses:
        """
        Returns the statuses of node services
        Parameters
        ----------
        url
            URL node in the form of http://ngl-dual-001.testnet.symboldev.network:3000
        Returns
        -------
        BlockchainStatuses
            The statuses of node services
        ```py
        BlockchainStatuses.DB_FAILURE
        BlockchainStatuses.NO_NODES_AVAILABLE
        BlockchainStatuses.NOT_INITIALIZED
        BlockchainStatuses.REST_FAILURE
        BlockchainStatuses.OK
        BlockchainStatuses.UNKNOWN
        ```
        """
        if url is None:
            return BlockchainStatuses.NO_NODES_AVAILABLE
        try:
            answer = requests.get(f'{url}/node/health', timeout=1)
        except Exception as e:
            logger.exception(e)
            return BlockchainStatuses.REST_FAILURE
        if answer.status_code == HTTPStatus.OK:
            node_info = answer.json()
            if node_info['status']['apiNode'] == 'up' and node_info['status']['db'] == 'up':
                return BlockchainStatuses.OK
            if node_info['status']['apiNode'] == 'down':
                return BlockchainStatuses.NODE_FAILURE
            if node_info['status']['db'] == 'down':
                return BlockchainStatuses.DB_FAILURE
        return BlockchainStatuses.UNKNOWN

    @staticmethod
    def simple_health(url) -> bool:
        health_status = NodeSelector.health(url)
        if health_status == BlockchainStatuses.OK:
            return True
        return False

    @staticmethod
    def get_height(url) -> int:
        """
        Returns the last block known to the node
        Parameters
        ----------
        url
            URL node in the form of http://ngl-dual-001.testnet.symboldev.network:3000

        Returns
        -------

        """
        try:
            answer = requests.get(f'{url}/chain/info', timeout=1)
        except Exception:
            return 0
        node_info = answer.json()
        height = node_info['height']
        return int(height)

    @staticmethod
    def ping(url) -> Optional[float]:
        """Calculate and return a latency point using sockets"""
        if multiprocessing.current_process().daemon:
            asyncio.set_event_loop(asyncio.new_event_loop())
        parse_result = urlparse(url)
        loop = asyncio.get_event_loop()
        latency = loop.run_until_complete(NodeSelector.measure_latency(host=parse_result.hostname, port=parse_result.port, runs=3))
        if (result := len(list(filter(None, latency)))) == 0:
            return None
        average = sum(filter(None, latency)) / result
        return average

    @staticmethod
    async def measure_latency(
            host: str,
            port: int = 443,
            timeout: float = 5,
            runs: int = 1,
            wait: float = 0,
    ) -> list:
        """
        Builds a list composed of latency_points
        Parameters
        ----------
        host
            Host name
        port
            Port
        timeout
            Server response timeout
        runs
            Number of attempts
        wait
            Delay before request
        Returns
        -------
        list
            list of latency for all runs
        """
        tasks = []
        latency_points = []
        for i in range(runs):
            await asyncio.sleep(wait)
            tasks.append(asyncio.create_task(NodeSelector.latency_point(host=host, port=port, timeout=timeout)))
            # last_latency_point = await latency_point(host=host, port=port, timeout=timeout)
        for i in range(runs):
            latency_points.append(await tasks[i])
        return latency_points

    @staticmethod
    async def latency_point(host: str, port: int = 443, timeout: float = 5) -> Optional[float]:
        """
        Calculate a latency point using sockets. If something bad happens the point returned is None
        Parameters
        ----------
        host
            Host name
        port
            Port
        timeout
            Server response timeout
        Returns
        -------
        Optional[float]
            Returns float if possible
        """
        # New Socket and Time out
        # Start a timer
        s_start = time.time()

        # Try to Connect
        uri = f"ws://{host}:{port}"
        try:
            async with websockets.connect(uri, close_timeout=timeout):
                pass
        except exceptions.InvalidMessage:
            pass
        except exceptions.InvalidStatusCode:
            pass
        except Exception as e:
            logger.debug(str(e))
            return None

        # Stop Timer
        s_runtime = (time.time() - s_start) * 1000
        return float(s_runtime)


# singleton for background work with the list of nodes
node_selector = NodeSelector(config.TEST_NODE_URLs)
