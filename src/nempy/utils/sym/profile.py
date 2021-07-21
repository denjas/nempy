
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
@click.option('--list', 'is_list', required=False, is_flag=True, help='List of all profile of the current wallet')
def profile_info(name, is_list):
    """
    Displays profile information
    """
    wallet = Wallet()
    if is_list:
        wallet.print_profiles()
    print(wallet.default_profile)
    #


if __name__ == '__main__':
    main()
