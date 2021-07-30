import threading
import time
from unittest.mock import patch, PropertyMock

import pytest
from nempy.sym import network


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

