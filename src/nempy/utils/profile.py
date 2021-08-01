#!/usr/bin/env python

import click
from nempy.wallet import Wallet
from nempy.profile import Profile, PasswordPolicyError, RepeatPasswordError


@click.group('profile', help='- Interactive account management')
def main():
    Wallet(init_only=True)
    print('Interactive account management:')


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
    wallet.inquirer_default_profile()


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
    print(wallet.profile)


if __name__ == '__main__':
    main()
