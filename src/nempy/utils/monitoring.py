#!/usr/bin/env python

import logging
import os.path

import click
from nempy.sym.network import Monitor, node_selector


@click.command('monitoring', help='- Monitor blocks, transactions and errors', context_settings=dict(max_content_width=300))
@click.option('--url', type=str, required=False, default=None,
              help='Node URL (example: http://ngl-dual-001.testnet.symboldev.network:3000)')
@click.option('-c', '--channels', nargs=0,
              type=click.Choice(Monitor.where_to_subscribe.keys()), default='all',
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
        channels = Monitor.where_to_subscribe.keys()
    subscribers = []
    for channel in channels:
        param = Monitor.where_to_subscribe[channel]
        if param == 'address':
            if not len(address):
                raise AttributeError(f'When specifying the `{channel}` channel, you must specify the account address (example: "-a TAKTSIRJ3KE5VX2JS464ACSWQ5H4YYMN6UARLQY")')
            for address in addresses:
                subscribers.append(os.path.join(channel, address))
        else:
            subscribers.append(channel)
    logging.debug(subscribers)
    Monitor(node_selector.url, subscribers, formatting, log)


if __name__ == '__main__':
    main()
