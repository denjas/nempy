import datetime
import tempfile
import time
from unittest.mock import patch

import pytest
from requests import exceptions
from aiohttp import http_exceptions

from nempy.sym import network
from nempy.sym.constants import NetworkType
from nempy.sym.network import Monitor
from nempy.sym.node_selector import node_selector, get_node_network, NodeSelector


@pytest.mark.asyncio
async def test_get_divisibility():
    divisibility = await network.get_divisibility('091F837E059AE13C')
    assert divisibility == 6
    with pytest.raises(network.SymbolNetworkException):
        await network.get_divisibility('0' * 16)
    with pytest.raises(network.SymbolNetworkException):
        await network.get_divisibility('INVALID_MOSAIC_ID')
    with patch('aiohttp.ClientSession', side_effect=http_exceptions.HttpProcessingError):
        with pytest.raises(http_exceptions.HttpProcessingError):
            await network.get_divisibility('091F837E059AE13C')


@pytest.mark.asyncio
async def test_get_accounts_info():
    account = await network.get_accounts_info('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')
    assert account['account']['publicKey'] == 'ED50271958F5174792884FD44286F3E5F951BD5820222B11531DE99C6FB7B998'
    with pytest.raises(network.SymbolNetworkException):
        await network.get_accounts_info('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ' + 'random')
    assert await network.get_accounts_info('TDNJ2CV3NQVNIYFNAUSWYAOVJTLOF3HNK3CVVLY') is None
    with patch('aiohttp.ClientSession', side_effect=http_exceptions.HttpProcessingError):
        with pytest.raises(http_exceptions.HttpProcessingError):
            await network.get_accounts_info('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')


@pytest.mark.asyncio
async def test_get_balance():
    balance = await network.get_balance('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')
    assert len(balance) > 0
    with pytest.raises(network.SymbolNetworkException):
        await network.get_balance('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ' + 'random')
    assert await network.get_balance('TDNJ2CV3NQVNIYFNAUSWYAOVJTLOF3HNK3CVVLY') == {}


@pytest.mark.asyncio
async def test_send_transaction():
    assert await network.send_transaction(
        b'{"payload": "DD00000000000000FA750016DD8DD2B1370A73A30A9126D9515D21BA978578FD2D92'
        b'30DFA9A9F4EBC69962D60EDB77DBF7F4584082E08AA6E226A5D5B2FF950E10415A3564F14503ED502'
        b'71958F5174792884FD44286F3E5F951BD5820222B11531DE99C6FB7B9980000000001985441545600'
        b'0000000000AB3C7CA1020000009815392229DA89DADF49973DC00A56874FCC618DF50115C30D00030'
        b'0000000003CE19A057E831F09400D03000000000092A662650B92BD63A0860100000000002F459612'
        b'74B9E271E0930400000000000048656C6C6F20576F726C6421"}') is True
    # InvalidContent
    assert await network.send_transaction(b'random bytes') is False
    # InvalidArgument
    assert await network.send_transaction(b'{"payload-err": "DD"}') is False


@pytest.mark.asyncio
async def test_search_transactions():
    transactions = await network.search_transactions(address='TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')
    assert len(transactions) == 10
    with pytest.raises(network.SymbolNetworkException):
        await network.search_transactions(address='TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQI+random')
    keys = ['Type:', 'Status:', 'Hash:', 'Paid Fee:', 'Height:', 'Deadline:', 'Signature:',
            'Signer Public Key:', 'From:', 'To:', 'Mosaic:', 'Message:']
    assert all(False for key in keys if key not in str(transactions[0]))


@pytest.mark.asyncio
async def test_get_divisibilities():
    mosaics = await network.get_divisibilities(2)
    assert len(mosaics) == 200


@pytest.mark.asyncio
async def test_get_network_properties():
    np = await network.get_network_properties()
    for key in ['network', 'chain', 'plugins']:
        assert key in np


@pytest.mark.asyncio
async def test_get_block_information():
    bn = await network.get_block_information(1)
    assert bn['meta']['hash'] == 'AAF1AE7E0E03D4CC0B3B73DB56530C06465AE8229B1A85C3CA22EC114189AD00'


@pytest.mark.asyncio
async def test_get_mosaic_names():
    # InvalidArgument 409
    name = 'symbol.xym'
    id = '091F837E059AE13C'
    with pytest.raises(network.SymbolNetworkException):
        await network.get_mosaic_names([name])
    assert await network.get_mosaic_names(id) == await network.get_mosaic_names([id])
    with patch('aiohttp.ClientSession', side_effect=http_exceptions.HttpProcessingError):
        with pytest.raises(http_exceptions.HttpProcessingError):
            await network.get_mosaic_names(id)


@pytest.mark.asyncio
async def test_mosaic_id_to_name_n_real():
    name_n_real: dict = await network.mosaic_id_to_name_n_real('091F837E059AE13C', 1000000)
    assert name_n_real['id'] == 'symbol.xym'
    assert name_n_real['amount'] == 1.0
    with pytest.raises(TypeError):
        await network.mosaic_id_to_name_n_real('091F837E059AE13C', 1000000.0)


@pytest.mark.asyncio
async def test_check_transaction_state():
    transaction_hash = '84BDE34A9A64B77324C4D08B86E9355B8EF94D5BFBF136A6AE44D9D620AE7532'
    status = await network.check_transaction_state(transaction_hash)
    assert status == network.TransactionStatus.CONFIRMED_ADDED
    with patch('aiohttp.ClientSession', side_effect=http_exceptions.HttpProcessingError):
        with pytest.raises(http_exceptions.HttpProcessingError):
            await network.check_transaction_state(transaction_hash)
    # 500 - Internal
    with pytest.raises(network.SymbolNetworkException):
        await network.check_transaction_state(transaction_hash + 'random')
    # 409 - InvalidArgument
    with pytest.raises(network.SymbolNetworkException):
        await network.check_transaction_state('V'*len(transaction_hash))
    c = transaction_hash.replace('B', '0')
    assert await network.check_transaction_state(transaction_hash.replace('B', '0')) == network.TransactionStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_get_node_network():
    assert await get_node_network() == NetworkType.TEST_NET
    with patch('aiohttp.ClientSession', side_effect=http_exceptions.HttpProcessingError):
        with pytest.raises(http_exceptions.HttpProcessingError):
            await get_node_network()


class TestTiming:

    @pytest.mark.asyncio
    async def test_init(self):
        with pytest.raises(EnvironmentError):
            await network.Timing('UNKNOWN')

    @pytest.mark.asyncio
    async def test_calc_deadline(self):
        timing_test_net = await network.Timing(NetworkType.TEST_NET)
        timing_main_net = await network.Timing(NetworkType.MAIN_NET)

        calc_deadline_tn = timing_test_net.calc_deadline(days=1)
        calc_deadline_mn = timing_main_net.calc_deadline(days=1)
        delta = (calc_deadline_mn - calc_deadline_tn) / 1000
        intervals = datetime.timedelta(seconds=delta)
        assert intervals.seconds == 64192
        assert intervals.days == 9
        with pytest.raises(TimeoutError):
            timing_test_net.calc_deadline()

    @pytest.mark.asyncio
    async def test_deadline_to_date(self):
        timing_test_net = await network.Timing(NetworkType.TEST_NET)
        deadline_date = datetime.datetime(2021, 8, 4, 15, 18, 11, 574000, tzinfo=datetime.timezone.utc).replace(tzinfo=None)
        date = timing_test_net.deadline_to_date(11395314574)
        assert date == deadline_date
        date_local = timing_test_net.deadline_to_date(11395314574, is_local=True)
        if time.timezone != 0:
            assert date != date_local


@pytest.mark.asyncio
async def test_monitor():
    def monitoring_callback(bock):
        raise SystemExit('Stop monitoring')
    subscribers = ['block']
    with tempfile.NamedTemporaryFile() as log:
        with pytest.raises(SystemExit):
            await Monitor(await node_selector.url, subscribers, formatting=True, log=log, callback=monitoring_callback).monitoring()




