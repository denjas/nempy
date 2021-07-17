#!/usr/bin/env python

import asyncio
import os.path

import websockets
import json
import click

where_to_subscribe = {
    'address': [
        'confirmedAdded',
        'unconfirmedAdded',
        'unconfirmedRemoved',
        'partialAdded',
        'partialRemoved',
        'cosignature',
        'status'
    ],
    'blocks': [
        'block',
        'finalizedBlock'
    ]
}

_host = None
_port = None


async def monitoring(subscribers):
    uri = f"ws://{_host}:{_port}/w/messages"
    async with websockets.connect(uri, ) as ws:
        # response = json.loads(await ws.recv())
        # print('UID:', response["uid"])
        # # print('For address:', address)
        # if 'uid' in response:
        #     for subscriber in subscribers:
        #         added = json.dumps({"uid": response["uid"], "subscribe": f"{subscriber}"})
        #         await ws.send(added)
        #         print('Subscribed to: ', subscriber)
        #     print('Listening... `Ctrl+C` for abort')
        while True:
            res = await ws.recv()
            print(res)
        # else:
        #     raise RuntimeError('Server mot response')


def connector(subscribers):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(monitoring(subscribers))


@click.group()
@click.option('-h', '--host', type=str, required=True)
@click.option('-p', '--port', type=int, default=3000, show_default=True)
def cli(host, port):
    global _host, _port
    _host = host
    _port = port


@cli.command('address')
@click.option('-s', '--slots', nargs=0, type=str)
@click.argument('slots', nargs=-1)
@click.option('-a', '--address', type=str, multiple=True, required=True)
def address(slots, address):
    all_subscribers = []
    slot_group = 'address'
    for addr in address:
        if (len(slots) == 1 and slots[0] == 'all') or len(slots) == 0:
            all_subscribers += [os.path.join(x, addr) for x in where_to_subscribe[slot_group]]
        else:
            all_subscribers += [os.path.join(x, addr) for x in slots if x in where_to_subscribe[slot_group]]
    connector(all_subscribers)


@cli.command('block')
@click.option('-s', '--slots', nargs=0, type=str, show_default=True)
@click.argument('slots', nargs=-1)
def block(slots):
    slot_group = 'blocks'
    if (len(slots) == 1 and slots[0] == 'all') or len(slots) == 0:
        subscribers = where_to_subscribe[slot_group]
    else:
        subscribers = [x for x in slots if x in where_to_subscribe[slot_group]]
    connector(subscribers)


if __name__ == '__main__':
    # cli = click.CommandCollection(sources=[sync, address, cli])
    # cli()
    d = cli(obj={})
    print(d)


