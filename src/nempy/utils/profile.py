#!/usr/bin/env python

import click
from nempy.config import C
from nempy.wallet import Wallet
from nempy.ui import ProfileUI


@click.group('profile', help='- Interactive profile management')
def main():
    Wallet()
    print('Interactive profile management:')


@main.command('create')
def create_profile():
    """
    Create a new profile
    """
    wallet = Wallet()
    profile = wallet.create_profile()
    print(profile)


@main.command('setdefault')
def setdefault():
    """
    Change the default profile
    """
    wallet = Wallet()
    profile_data = ProfileUI.ui_default_profile(wallet.profile.load_profiles())
    wallet.profile.set_default_profile(profile_data)


@main.command('info')
@click.option('-n', '--name', type=str, required=False, default='', help='Profile name')
@click.option('-l', '--list', 'is_list', required=False, is_flag=True, help='List of all profile of the current wallet')
def profile_info(name, is_list):
    """
    Displays profile information
    """
    wallet = Wallet()
    if is_list or name:
        wallet.print_profiles(name)
        exit(0)
    str_profile_data = str(wallet.profile.data).replace('|              |', f'|  >{C.OKGREEN}DEFAULT{C.END}<   |', 1)
    print(str_profile_data)


if __name__ == '__main__':
    main()
