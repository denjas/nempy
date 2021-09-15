import pytest

from nempy.sym.node_selector import  NodeSelector


@pytest.mark.asyncio
async def test_node_selector():
    urls = ['http://ngl-dual-301.testnet.symboldev.network:3000', 'http://ngl-dual-401.testnet.symboldev.network:3000']
    _node_selector = NodeSelector(urls)
    assert await _node_selector.url in urls
    not_valid_url = 'http:/ngl-dual-301.testnet.symboldev.network:3000'
    with pytest.raises(ValueError):
        NodeSelector(not_valid_url)
    not_worked_url = 'http://sdfgdfg.sdfgdsgdgfd.sdfgd.sdfgsdg:3000'
    _node_selector = NodeSelector(not_worked_url)
    assert await _node_selector.url == not_worked_url
    _node_selector = NodeSelector(urls[0])
    assert await _node_selector.url == urls[0]