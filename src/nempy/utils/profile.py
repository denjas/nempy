#!/usr/bin/env python

import click
from nempy.wallet import Wallet
from nempy.profile import ProfileUI


@click.group('profile', help='- Interactive profile management')
def main():
    # Wallet(init_only=True)
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
    ProfileUI.ui_default_profile(wallet.profile_io.load_profiles())


@main.command('info')
@click.option('-n', '--name', type=str, required=False, default='', help='Profile name')
@click.option('--list', 'is_list', required=False, is_flag=True, help='List of all profile of the current wallet')
def profile_info(name, is_list):
    """
    Displays profile information
    """
    wallet = Wallet()
    if is_list:
        wallet.print_profiles()
        exit(0)
    print(wallet.profile)


if __name__ == '__main__':
    main()
