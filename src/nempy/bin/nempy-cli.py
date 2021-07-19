#!/usr/bin/env python

import logging

import click
from nempy.utils.sym.monitoring import main as monitoring_sym
from nempy.utils.sym.profile import main as profile_sym


logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('asyncio.coroutines').setLevel(logging.ERROR)
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


@click.group()
@click.option('-d', '--debug', is_flag=True)
def main(debug):
    if debug:
        logging.basicConfig(level=logging.DEBUG)


main.add_command(monitoring_sym)
main.add_command(profile_sym)


if __name__ == '__main__':
    main()
