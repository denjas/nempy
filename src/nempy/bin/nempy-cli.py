#!/usr/bin/env python

import logging

import click
from nempy.utils.sym_monitoring import main as monitoring_sym


logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('asyncio.coroutines').setLevel(logging.ERROR)
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


@click.group()
@click.option('-d', '--debug', is_flag=True)
def main(debug):
    if debug:
        logging.basicConfig(level=logging.DEBUG)


main.add_command(monitoring_sym, 'monitoring')


if __name__ == '__main__':
    main()
