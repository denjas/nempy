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

import requests
import websockets
from nempy.sym.constants import BlockchainStatuses, EPOCH_TIME_TESTNET, EPOCH_TIME_MAINNET, NetworkType, \
    TransactionTypes
from pydantic import BaseModel
from symbolchain.core.CryptoTypes import Hash256
from symbolchain.core.facade.SymFacade import SymFacade
from tabulate import tabulate
from websockets import exceptions

from . import ed25519, constants, config
from .constants import TransactionStatus

logger = logging.getLogger(__name__)


def url_validation(url):
    # django url validation regex
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
    if not isinstance(amount, int):
        raise TypeError('To avoid confusion, automatic conversion to integer is prohibited')
    divisibility = get_divisibility(mosaic_id)
    if divisibility is None:
        raise ValueError(f'Failed to get divisibility from network')
    divider = 10 ** int(divisibility)

    mn = get_mosaic_names(mosaic_id)
    name = mosaic_id
    if mn is not None:
        names = mn['mosaicNames'][0]['names']
        if len(names) > 0:
            name = names[0]
    return {'id': name, 'amount': float(amount / divider)}


class Meta(BaseModel):
    height: int
    hash: str
    merkleComponentHash: str
    index: int


class MosaicInfo(BaseModel):
    id: str
    amount: int


class HumMosaicInfo(MosaicInfo):
    amount: float

    def __str__(self):
        return f'{self.amount}({self.id})'


class TransactionInfo(BaseModel):
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
    mosaics: List[Union[MosaicInfo, HumMosaicInfo]]

    def humanization(self):
        self.deadline = Timing().deadline_to_date(self.deadline)
        if self.message is not None:
            self.message = unhexlify(self.message)[1:].decode('utf-8')
        self.recipientAddress = b32encode(unhexlify(self.recipientAddress)).decode('utf-8')[:-1]
        self.mosaics = [HumMosaicInfo(**mosaic_id_to_name_n_real(mosaic.id, mosaic.amount)) for mosaic in self.mosaics]
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


def get_mosaic_names(mosaics: Union[list, str]) -> Optional[dict]:
    """
    Get readable names for a set of mosaics
    :param mosaics:
    :return:
    """
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
    params = {key: val for key, val in params.items() if val is not None}
    endpoint = f'{node_selector.url}/transactions/{transaction_status.value}'
    try:
        answer = requests.get(endpoint, params=params)
    except Exception as e:
        logger.error(e)
        return None
    if answer.status_code != HTTPStatus.OK:
        logger.error(answer.text)
        return None
    transactions = json.loads(answer.text)
    transactions_response = []
    for transaction in transactions['data']:
        mosaics = [MosaicInfo(**mosaic) for mosaic in transaction['transaction']['mosaics']]
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
    namespace_info = json.loads(answer.text)
    return namespace_info


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
            return NetworkType.TEST_NET
        elif network_generation_hash_seed == constants.NETWORK_GENERATION_HASH_SEED_PUBLIC:
            return NetworkType.MAIN_NET
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


def get_divisibilities():
    mosaics = {}
    params = {'pageSize': 100}
    while True:
        try:
            answer = requests.get(f'{node_selector.url}/mosaics', params=params)
        except Exception as e:
            logger.error(e)
            return None
        if answer.status_code == HTTPStatus.OK:
            mosaics_pages = json.loads(answer.text)['data']
            if len(mosaics_pages) == 0:
                return mosaics
            last_page = None
            for page in mosaics_pages:
                mosaic_id = page['mosaic']['id']
                divisibility = page['mosaic']['divisibility']
                mosaics[mosaic_id] = divisibility
                last_page = page
            params['offset'] = last_page['id']


def get_balance(address: str, mosaic_filter: Union[list, str] = None, is_linked: bool = False) -> Optional[dict]:
    if isinstance(mosaic_filter, str):
        mosaic_filter = [mosaic_filter]
    if mosaic_filter is None:
        mosaic_filter = []
    for mosaic_id in mosaic_filter:
        if not ed25519.check_hex(mosaic_id, constants.HexSequenceSizes.mosaic_id):
            logger.error(f'Incorrect mosaic ID: `{mosaic_id}`')
            return None
    address_info = get_accounts_info(address)
    if address_info == {}:
        return address_info
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


class Monitor:
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
            else:
                raise RuntimeError('Server mot response')


class Timing:

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


class NodeSelector:
    _URL: Optional[str] = None
    _URLs: Optional[list] = None
    _re_elections: Optional[bool] = False
    _network_type: NetworkType = NetworkType.TEST_NET

    def __init__(self, node_urls: Union[List[str], str]):
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
        if len(self._URLs) > 1:
            if self.health(self._URL) != BlockchainStatuses.OK:
                self.reelection_node()
        return self._URL

    @url.setter
    def url(self, urls: Union[list, str]):
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            url_validation(url)
        self._URLs = urls
        if len(self._URLs) == 1:
            self._re_elections = None  # stop background iteration of nodes
            self._URL = self._URLs[0]  # setting a single URL value
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
        _sorted_URLs = [k for k, v in sorted(working.items(), key=lambda item: item[1][0])]
        new_url = _sorted_URLs[0] if len(_sorted_URLs) > 0 else None
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
        except Exception:
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
        :rtype: list
        Builds a list composed of latency_points
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
    async def latency_point(host: str, port: int = 443, timeout: float = 5) -> [float, None]:
        '''
        :rtype: Returns float if possible
        Calculate a latency point using sockets. If something bad happens the point returned is None
        '''
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
