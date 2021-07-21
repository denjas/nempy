import os

import click
from nempy.wallet import Wallet
from nempy.account import Account, print_warning, DecoderStatus, GenerationTypes
from nempy.engine import XYMEngine


@click.group('account')
def main():
    """
    Interactive account management
    :return:
    """
    print('Interactive account management.')


@main.command('import')
def import_account():
    """
    Create a new account with existing private key or mnemonic
    """
    wallet = Wallet()
    account_path, name, bip32_coin_id, is_default = Account.init_general_params(wallet.profile.network_type)
    if is_default:
        wallet.profile.set_default_account(name)
    password = wallet.profile.check_pass(attempts=3)
    gen_type = Account.get_gen_type()
    if gen_type == GenerationTypes.MNEMONIC:
        account = Account.account_by_mnemonic(wallet.profile.network_type, bip32_coin_id)
    if gen_type == GenerationTypes.PRIVATE_KEY:
        raise NotImplemented('The functionality of building an account from a private key is not implemented')
    account = Account(account)
    account.name = name
    account.profile = wallet.profile.name
    account.account_creation(account_path, password)


@main.command('create')
def create_account():
    """
    Create a new account
    """
    wallet = Wallet()
    account_path, name, bip32_coin_id, is_default = Account.init_general_params(wallet.profile.network_type)
    if is_default:
        wallet.profile.set_default_account(name)
    password = wallet.profile.check_pass(attempts=3)
    if password is not None:
        account = Account.account_by_mnemonic(wallet.profile.network_type, bip32_coin_id, is_generate=True)
        account = Account(account)
        account.name = name
        account.profile = wallet.profile.name
        account.account_creation(account_path, password)


@main.command('setdefault')
def setdefault():
    """
    Change the default account
    """
    wallet = Wallet()
    wallet.profile.input_default_account()


@main.command('info')
@click.option('-n', '--name', type=str, required=False, default='', help='Account name. If not set, the default account name will be used')
@click.option('--decode', required=False, is_flag=True, help='Decode secret data')
@click.option('--list', 'is_list', required=False, is_flag=True, help='List of all accounts of the current profile')
def info(name, decode, is_list):
    """
    Account Information
    """
    wallet = Wallet()
    accounts = wallet.profile.load_accounts()
    if not accounts:
        print(f'There are no accounts for the {wallet.profile.name} profile.')
        print('To create an account, run the command: `nempy-cli.py account create`')
        exit(1)
    if not is_list:

        if not name and wallet.profile.account is not None:
            name = wallet.profile.account.name
        account = accounts.get(name, {})
        if not account:
            # print(f'The account named `{name}` does not exist in profile `{wallet.profile.name}`')
            wallet.profile.input_default_account()
            account = wallet.profile.account
        accounts = {name: account}
    password = None
    if decode:
        print('Attention! Hide information received after entering a password from prying eyes')
        password = wallet.profile.check_pass(attempts=3)
        if password is None:
            exit(1)
    for account in accounts.values():
        if decode:
            account = account.decode(password)
            if isinstance(account, DecoderStatus):
                exit(1)
        print(account)
        print('###################################################################################')
    if decode:
        print_warning()


@main.command('balance')
@click.option('-a', '--address', type=str, required=False, default='', help='Get the balance at the address. Default current account balance')
def get_balance(address):
    """
    Get the balance for the current account
    """
    wallet = Wallet()
    engine = XYMEngine(wallet.profile.account)
    if not address:
        address = wallet.profile.account.address
    balance = engine.get_balance(address)
    if balance == {}:
        print('There is no account, or there was no movement of funds on it')
        exit(0)
    print(balance)


if __name__ == '__main__':
    main()
