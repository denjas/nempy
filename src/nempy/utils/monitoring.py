#!/usr/bin/env python

import asyncio
import json
import logging
import os.path
from collections import Callable
from urllib.parse import urlparse

import click
import websockets
from nempy.sym.network import node_selector
from tabulate import tabulate


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


async def monitoring(url, subscribers, formatting, log, callback):
    result = urlparse(url)
    url = f"ws://{result.hostname}:{result.port}/ws"
    print(f'MONITORING: {url}')
    async with websockets.connect(url) as ws:
        response = json.loads(await ws.recv())
        print(f'UID: {response["uid"]}')
        if 'uid' in response:
            prepare = []
            for subscriber in subscribers:
                added = json.dumps({"uid": response["uid"], "subscribe": f"{subscriber}"})
                await ws.send(added)
                # print(f'Subscribed to: {subscriber}')
                prepare.append([subscriber])
            table = tabulate(prepare, headers=['Subscribers'], tablefmt='grid')
            print(table)
            print('Listening... `Ctrl+C` for abort')
            while True:
                res = await ws.recv()
                if formatting:
                    res = json.dumps(json.loads(res), indent=4)
                if callback is not None:
                    callback(json.loads(res))
                    continue
                print(res)
                if log:
                    with open(log, 'a+') as f:
                        res += '\n'
                        f.write(res)
        else:
            raise RuntimeError('Server mot response')


def connector(url, subscribers, formatting: bool = False, log: str = '', callback: Callable = None):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(monitoring(url, subscribers, formatting, log, callback))


@click.command('monitoring', help='- Monitor blocks, transactions and errors', context_settings=dict(max_content_width=300))
@click.option('--url', type=str, required=False, default=None,
              help='Node URL (example: http://ngl-dual-001.testnet.symboldev.network:3000)')
@click.option('-c', '--channels', nargs=0,
              type=click.Choice(where_to_subscribe.keys()), default='all',
              show_default=True, help='Channels available for subscribe')
@click.argument('channels', nargs=-1, )
@click.option('-a', '--address', type=str, multiple=True, required=False, help='Account address')
@click.option('-l', '--log', type=str, required=False, default='', help='Path to the log file')
@click.option('-f', '--formatting', is_flag=True, help='Formatted output')
def main(url, channels, address, formatting, log):
    addresses = address
    if log and os.path.exists(log):
        answer = input(f'`{log}` file exists, overwrite? y/N: ')
        if answer.lower() != 'y':
            exit(0)
    if url is not None:
        node_selector.url = url
    if not len(channels):
        channels = where_to_subscribe.keys()
    subscribers = []
    for channel in channels:
        param = where_to_subscribe[channel]
        if param == 'address':
            if not len(address):
                raise AttributeError(f'When specifying the `{channel}` channel, you must specify the account address (example: "-a TAKTSIRJ3KE5VX2JS464ACSWQ5H4YYMN6UARLQY")')
            for address in addresses:
                subscribers.append(os.path.join(channel, address))
        else:
            subscribers.append(channel)
    logging.debug(subscribers)
    connector(node_selector.url, subscribers, formatting, log)


if __name__ == '__main__':
    main()



