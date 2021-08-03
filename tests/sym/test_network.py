import threading
import time
from unittest.mock import patch, PropertyMock

import pytest
from nempy.sym import network
from nempy.sym.constants import NetworkType
import requests
from requests import exceptions


def test_search_transactions():
    transactions = network.search_transactions(address='TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')
    assert len(transactions) == 10
    keys = ['Type:', 'Status:', 'Hash:', 'Paid Fee:', 'Height:', 'Deadline:', 'Signature:',
            'Signer Public Key:', 'From:', 'To:', 'Mosaic:', 'Message:']
    assert all(False for key in keys if key not in str(transactions[0]))
    time.sleep(1)


def test_node_selector():
    urls = ['http://ngl-dual-301.testnet.symboldev.network:3000', 'http://ngl-dual-401.testnet.symboldev.network:3000']
    network.node_selector.url = urls
    assert network.node_selector.url in urls
    not_valid_url = 'http:/ngl-dual-301.testnet.symboldev.network:3000'
    with pytest.raises(ValueError):
        network.node_selector.url = not_valid_url
    not_worked_url = 'http://sdfgdfg.sdfgdsgdgfd.sdfgd.sdfgsdg:3000'
    network.node_selector.url = not_worked_url
    assert network.node_selector.url == not_worked_url
    network.node_selector.url = urls
    assert network.node_selector.url in urls
    with patch.object(threading.Event, 'wait', return_value=False):
        with pytest.raises(RuntimeError):
            network.node_selector.url = urls
    network.node_selector.url = urls[0]
    assert network.node_selector.url == urls[0]


def test_get_divisibility():
    divisibility = network.get_divisibility('091F837E059AE13C')
    assert divisibility == 6
    with pytest.raises(network.SymbolNetworkException):
        network.get_divisibility('0' * 16)
    with pytest.raises(network.SymbolNetworkException):
        network.get_divisibility('INVALID_MOSAIC_ID')
    with patch('requests.get', side_effect=exceptions.RequestException):
        with pytest.raises(exceptions.RequestException):
            network.get_divisibility('091F837E059AE13C')


def test_get_accounts_info():
    account = network.get_accounts_info('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')
    assert account['account']['publicKey'] == 'ED50271958F5174792884FD44286F3E5F951BD5820222B11531DE99C6FB7B998'
    with pytest.raises(network.SymbolNetworkException):
        network.get_accounts_info('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ' + 'random')
    assert network.get_accounts_info('TDNJ2CV3NQVNIYFNAUSWYAOVJTLOF3HNK3CVVLY') is None


def test_get_balance():
    balance = network.get_balance('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')
    assert len(balance) > 0
    with pytest.raises(network.SymbolNetworkException):
        network.get_balance('TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ' + 'random')
    assert network.get_balance('TDNJ2CV3NQVNIYFNAUSWYAOVJTLOF3HNK3CVVLY') == {}


def test_send_transaction():

    assert network.send_transaction(b'{"payload": "DD00000000000000FA750016DD8DD2B1370A73A30A9126D9515D21BA978578FD2D92'
                                    b'30DFA9A9F4EBC69962D60EDB77DBF7F4584082E08AA6E226A5D5B2FF950E10415A3564F14503ED502'
                                    b'71958F5174792884FD44286F3E5F951BD5820222B11531DE99C6FB7B9980000000001985441545600'
                                    b'0000000000AB3C7CA1020000009815392229DA89DADF49973DC00A56874FCC618DF50115C30D00030'
                                    b'0000000003CE19A057E831F09400D03000000000092A662650B92BD63A0860100000000002F459612'
                                    b'74B9E271E0930400000000000048656C6C6F20576F726C6421"}') is True
    # InvalidContent
    assert network.send_transaction(b'random bytes') is False
    # InvalidArgument
    assert network.send_transaction(b'{"payload-err": "DD"}') is False


def test_get_divisibilities():
    network.node_selector.network_type = NetworkType.MAIN_NET
    network.node_selector.thread.wait()
    mosaics = network.get_divisibilities(2)
    assert len(mosaics) == 200
    network.node_selector.network_type = NetworkType.TEST_NET
    mosaics = network.get_divisibilities(2)
    assert len(mosaics) == 200


def test_get_network_properties():
    np = network.get_network_properties()
    for key in ['network', 'chain', 'plugins']:
        assert key in np


def test_get_block_information():
    bn = network.get_block_information(1)
    assert bn['meta']['hash'] == 'AAF1AE7E0E03D4CC0B3B73DB56530C06465AE8229B1A85C3CA22EC114189AD00'


