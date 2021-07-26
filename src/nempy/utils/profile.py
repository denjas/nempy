#!/usr/bin/env python

import click
from nempy.wallet import Wallet, Profile


@click.group('profile', help='- Interactive account management')
def main():
    Wallet(skip_checks=True)
    print('Interactive account management:')


@main.command('create')
def create_profile():
    """
    Create a new profile
    """
    profile, is_default = Profile.create_profile()
    if is_default:
        wallet = Wallet()
        wallet.set_default_profile(profile)


@main.command('setdefault')
def setdefault():
    """
    Change the default profile
    """
    wallet = Wallet()
    wallet.set_default_profile()


@main.command('info')
@click.option('-n', '--name', type=str, required=False, default='', help='Account name')
@click.option('--list', 'is_list', required=False, is_flag=True, help='List of all profile of the current wallet')
def profile_info(name, is_list):
    """
    Displays profile information
    """
    wallet = Wallet()
    if is_list:
        wallet.print_profiles()
    print(wallet.profile)


if __name__ == '__main__':
    main()
