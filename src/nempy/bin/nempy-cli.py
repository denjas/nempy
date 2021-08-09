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


class MyGroup(click.Group):
    def parse_args(self, ctx, args):
        if '-v' in args or '--version' in args:
            print(f'NEMpy {open("version.txt", "r").read()}')
            if '-d' in args or '--debug' in args:
                import sys
                print(sys.version)
            exit(0)
        super(MyGroup, self).parse_args(ctx, args)


@click.group(cls=MyGroup)
@click.option('-d', '--debug', is_flag=True, default=False, help='Turns on debug mode for logs')
@click.option('-v', '--version', is_flag=True, default=False, help='Show this version and exit.')
def main(debug, version):
    log_format = "[%(asctime)s][%(levelname)s] %(name)s - %(message)s"
    if debug:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    else:
        logging.basicConfig(level=logging.ERROR, format=log_format)


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
