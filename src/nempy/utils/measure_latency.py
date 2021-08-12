#!/usr/bin/env python

import asyncio

import click
from nempy.sym.network import NodeSelector


@click.command()
@click.option('-h', '--host', 'hosts', default=tuple('google.com'), type=str, multiple=True, help='host to check latency')
@click.option('-p', '--port', default=443, help='port to check')
@click.option('-r', '--runs', default=3, help='port to check')
def main(hosts, port, runs):
    loop = asyncio.get_event_loop()
    for i, host in enumerate(hosts):
        latency = loop.run_until_complete(NodeSelector.measure_latency(host=host, port=port, runs=runs))
        if None in latency:
            print(print(f'{i+1}. {host}:{port} - --'))
            continue
        print(f'{i+1}. {host}:{port} - {sum(latency)/runs}')


if __name__ == '__main__':
    main()
