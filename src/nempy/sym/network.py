import asyncio
import datetime
import json
import logging
import time
from base64 import b32encode
from binascii import unhexlify
from http import HTTPStatus
from typing import Optional, Union, List, Callable, Dict, Coroutine
from urllib.parse import urlparse

import aiohttp
import requests
import websockets
from pydantic import BaseModel, StrictInt, StrictFloat
from requests.exceptions import RequestException
from symbolchain.core.CryptoTypes import Hash256
from symbolchain.core.facade.SymbolFacade import SymbolFacade
from tabulate import tabulate
from websockets import exceptions

from . import ed25519, constants
from .constants import EPOCH_TIME_TESTNET, EPOCH_TIME_MAINNET, NetworkType, AccountValidationState
from .constants import TransactionStatus, TransactionTypes
from .node_selector import node_selector

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


async def mosaic_id_to_name_n_real(mosaic_id: str, amount: int) -> dict:
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
    divisibility = await get_divisibility(mosaic_id)
    divider = 10 ** int(divisibility)
    mn: dict = await get_mosaic_names(mosaic_id)
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

    async def humanization(self):
        """Converts information from the blockchain into a readable form"""
        self.deadline = (await Timing()).deadline_to_date(self.deadline)
        if self.message is not None:
            self.message = unhexlify(self.message)[1:].decode('utf-8', 'ignore')
        self.recipientAddress = b32encode(unhexlify(self.recipientAddress)).decode('utf-8')[:-1]
        self.mosaics = [MosaicInfo(**(await mosaic_id_to_name_n_real(mosaic.id, mosaic.amount))) for mosaic in self.mosaics]
        self.type = TransactionTypes.get_type_by_id(self.type).name
        facade = SymbolFacade((await node_selector.network_type).value)
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


async def send_transaction(payload: bytes) -> bool:
    """Announces a transaction to the network"""
    try:
        headers = {'Content-type': 'application/json'}
        async with aiohttp.ClientSession() as session:
            async with session.put(
                    f'{await node_selector.url}/transactions',
                    data=payload,
                    headers=headers,
                    timeout=10
            ) as response:
                if response.status != HTTPStatus.ACCEPTED:
                    raise SymbolNetworkException(**(await response.json()))
    except (RequestException, SymbolNetworkException) as e:
        logger.exception(e)
        return False
    else:
        return True


async def get_mosaic_names(mosaics_ids: Union[list, str]) -> Dict[str, list]:
    """
    Get readable names for a set of mosaics.

    Parameters
    ----------
    mosaics_ids
        IDs of mosaic as list or str if there is only one mosaic
    Returns
    -------
    Coroutine[Dict[str, list]]
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
        async with aiohttp.ClientSession() as session:
            async with session.post(
                    f'{await node_selector.url}/namespaces/mosaic/names',
                    json=payload,
                    headers=headers,
                    timeout=1) as response:
                result = await response.json()
                if response.status != HTTPStatus.OK:
                    raise SymbolNetworkException(**result)
                return dict(result)
    except (RequestException, SymbolNetworkException) as e:
        logger.exception(e)
        raise


async def get_accounts_info(address: str) -> Optional[dict]:
    try:
        if (avs := ed25519.check_address(address)) != AccountValidationState.OK:
            raise SymbolNetworkException('InvalidAddress', f'Incorrect account address: `{address}`: {avs}')
        endpoint = f'{await node_selector.url}/accounts/{address}'
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=1) as response:
                if response.status != HTTPStatus.OK:
                    return None
                return await response.json()
    except RequestException as e:
        logger.exception(e)
        raise
    except SymbolNetworkException as e:
        logger.exception(e)
        raise


async def search_transactions(address: Optional[str] = None,
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
    endpoint = f'{await node_selector.url}/transactions/{transaction_status.value}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, params=payload, timeout=1) as response:
                result = await response.json()
                if response.status != HTTPStatus.OK:
                    raise SymbolNetworkException(**result)
                transactions = result
                transactions_response = []
                for transaction in transactions['data']:
                    mosaics = [MosaicInfo(id=mosaic['id'], amount=int(mosaic['amount'])) for mosaic in
                               transaction['transaction']['mosaics']]
                    del (transaction['transaction']['mosaics'])
                    _transaction = TransactionResponse(id=transaction['id'],
                                                       meta=Meta(**transaction['meta']),
                                                       transaction=TransactionInfo(mosaics=mosaics,
                                                                                   **transaction['transaction'])
                                                       )
                    _transaction.status = transaction_status.value
                    transactions_response.append(_transaction)
                    await _transaction.transaction.humanization()
                return transactions_response
    except RequestException as e:
        logger.exception(e)
        raise
    except SymbolNetworkException as e:
        logger.exception(e)
        raise


async def get_namespace_info(namespace_id: str) -> Optional[dict]:
    endpoint = f'{await node_selector.url}/namespaces/{namespace_id}'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=1) as response:
                if response.status != HTTPStatus.OK:
                    logger.error(await response.text())
                    if response.status == HTTPStatus.NOT_FOUND:
                        logger.error(f'Invalid namespace ID `{namespace_id}`')
                        return {}
                    return None
                namespace_info = await response.json()
                return namespace_info
    except Exception as e:
        logger.error(e)
        return None


async def check_transaction_state(transaction_hash):
    check_order = ['confirmed', 'unconfirmed', 'partial']
    status = TransactionStatus.NOT_FOUND
    for checker in check_order:
        endpoint = f'{await node_selector.url}/transactions/{checker}/{transaction_hash}'
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, timeout=1) as response:
                    if response.status != HTTPStatus.OK:
                        raise SymbolNetworkException(**(await response.json()))
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


async def get_network_properties():
    endpoint = f'{await node_selector.url}/network/properties'
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint, timeout=1) as response:
            if response.status == HTTPStatus.OK:
                network_properties = await response.json()
                return network_properties
            response.raise_for_status()


async def get_block_information(height: int):
    endpoint = f'{await node_selector.url}/blocks/{height}'
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint, timeout=1) as response:
            if response.status == HTTPStatus.OK:
                block_info = await response.json()
                return block_info
            response.raise_for_status()


async def get_fee_multipliers():
    endpoint = f'{await node_selector.url}/network/fees/transaction'
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(endpoint, timeout=1) as response:
                if response.status == HTTPStatus.OK:
                    fee_multipliers = await response.json()
                    return fee_multipliers
                return None
    except RequestException as e:
        logger.exception(e)
        return None


async def get_divisibility(mosaic_id: str) -> Optional[int]:
    try:
        if not ed25519.check_hex(mosaic_id, constants.HexSequenceSizes.MOSAIC_ID):
            raise SymbolNetworkException('InvalidArgument', f'mosaicId `{mosaic_id}` has an invalid format')
        async with aiohttp.ClientSession() as session:
            async with session.get(f'{await node_selector.url}/mosaics/{mosaic_id}', timeout=1) as response:

                node_info = await response.json()
                if response.status == HTTPStatus.OK:
                    divisibility = int(node_info['mosaic']['divisibility'])
                else:
                    raise SymbolNetworkException(**node_info)
    except RequestException as e:
        logger.exception(e)
        raise
    except SymbolNetworkException as e:
        logger.exception(e)
        raise
    else:
        return divisibility


async def get_divisibilities(n_pages: int = 0):
    mosaics = {}
    payload = {'pageSize': 100}
    endpoint = f'{await node_selector.url}/mosaics'

    page_count = 1
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(endpoint, params=payload, timeout=1) as response:
                    if response.status == HTTPStatus.OK:
                        mosaics_pages = (await response.json())['data']
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
        except Exception as e:
            logger.error(e)
            return None


async def get_balance(address: str) -> Optional[dict]:
    try:
        address_info = await get_accounts_info(address)
        if address_info is None:
            return {}
        mosaics = address_info['account']['mosaics']
        balance = {mosaic['id']: int(mosaic['amount']) / 10 ** await get_divisibility(mosaic['id']) for mosaic in mosaics}
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
        # loop = asyncio.get_event_loop()
        # loop.run_until_complete(self.monitoring())

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
    network_type: Optional[NetworkType] = None
    epoch_time: datetime.datetime = None
    """Works with network time"""
    def __init__(self, network_type: Optional[NetworkType] = None):
        self.network_type = network_type

    def __await__(self):
        return self.__init().__await__()

    async def __init(self):
        """ Crutch used for __await__ after spawning """
        if self.network_type is None:
            self.network_type = await node_selector.network_type
        if self.network_type == NetworkType.TEST_NET:
            self.epoch_time = EPOCH_TIME_TESTNET
        elif self.network_type == NetworkType.MAIN_NET:
            self.epoch_time = EPOCH_TIME_MAINNET
        else:
            raise EnvironmentError('It is not possible to determine the type of network')
        return self

    def calc_deadline(self, days: float = 0, seconds: float = 0, milliseconds: float = 0,
                      minutes: float = 0, hours: float = 0, weeks: float = 0) -> int:
        if self.epoch_time is None:
            raise RuntimeError('Incomplete initialization Timing. Execute with `await Timing()`')
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

        if self.epoch_time is None:
            raise RuntimeError('Incomplete initialization Timing. Execute with `await Timing()`')

        deadline = int(deadline)
        epoch_timestamp = datetime.datetime.timestamp(self.epoch_time)
        deadline_date_utc = datetime.datetime.utcfromtimestamp(epoch_timestamp + deadline / 1000)
        if is_local:
            local_deadline_date = utc2local(deadline_date_utc)
            return local_deadline_date
        return deadline_date_utc


