
from enum import Enum
import click
from nempy.wallet import Wallet, Profile


@click.group('profile')
def main():
    """
    Interactive account management
    :return:
    """
    print('Interactive account management:')


@main.command('import')
def import_account():
    pass


@main.command('create')
def create_profile():
    """
    Create a new profile
    """
    profile = Profile()
    profile.create_profile()


@main.command('setdefault')
def setdefault():
    """
    Change the default profile
    """
    wallet = Wallet()
    wallet.set_default_profile()


@main.command('info')
@click.option('-n', '--name', type=str, required=False, default='', help='Account name')
def profile_info(name):
    """
    Displays account information
    """
    wallet = Wallet()
    print(wallet.default_profile)
    # wallet.print_profiles()


if __name__ == '__main__':
    main()
