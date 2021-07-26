#!/usr/bin/env python

import logging

import click
from nempy.utils.monitoring import main as monitoring_sym
from nempy.utils.profile import main as profile_sym
from nempy.utils.account import main as account_sym
from pyfiglet import Figlet

logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('asyncio.coroutines').setLevel(logging.ERROR)
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


@click.group()
@click.option('-d', '--debug', is_flag=True)
def main(debug):
    if debug:
        log_format = "[%(asctime)s][%(levelname)s] %(name)s - %(message)s"
        logging.basicConfig(level=logging.DEBUG, format=log_format)


@main.command()
def about():
    """
    - About the program
    """
    figlet = Figlet()
    print(figlet.renderText('NEMpy'))


main.add_command(monitoring_sym)
main.add_command(profile_sym)
main.add_command(account_sym)


if __name__ == '__main__':
    main()
