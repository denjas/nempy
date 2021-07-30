import threading
import time
from unittest.mock import patch, PropertyMock

import pytest
from nempy.sym import network
from nempy.sym.constants import NetworkType


def test_search_transactions():
    transactions = network.search_transactions(address='TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')
    assert len(transactions) == 10
    keys = ['Type:', 'Status:', 'Hash:', 'Paid Fee:', 'Height:', 'Deadline:', 'Signature:',
            'Signer Public Key:', 'From:', 'To:', 'Mosaic:', 'Message:']
    assert all(False for key in keys if key not in str(transactions[0]))


def test_node_selector():
    urls = ['http://ngl-dual-301.testnet.symboldev.network:3000', 'http://ngl-dual-401.testnet.symboldev.network:3000']
    network.node_selector.url = urls[0]
    assert network.node_selector.url == urls[0]
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


