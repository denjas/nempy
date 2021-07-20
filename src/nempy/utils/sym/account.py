import os

import click
from nempy.wallet import Account, print_warning, DecoderStatus, Wallet, GenerationTypes


@click.group('account')
def main():
    """
    Interactive account management
    :return:
    """
    print('Interactive account management.')


@main.command('import')
def import_account():
    wallet = Wallet()
    account_path, name, bip32_coin_id = Account.init_general_params(wallet.default_profile.network_type)
    password = wallet.default_profile.check_pass(attempts=3)
    gen_type = Account.get_gen_type()
    if gen_type == GenerationTypes.MNEMONIC:
        account = Account.account_by_mnemonic(wallet.default_profile.network_type, bip32_coin_id)
    account = Account(account)
    account.name = name
    account.profile = wallet.default_profile.name
    account.account_creation(account_path, password)


@main.command('create')
def create_account():
    wallet = Wallet()
    account_path, name, bip32_coin_id = Account.init_general_params(wallet.default_profile.network_type)
    password = wallet.default_profile.check_pass(attempts=3)
    if password is not None:
        account = Account.account_by_mnemonic(wallet.default_profile.network_type, bip32_coin_id, is_generate=True)
        account = Account(account)
        account.name = name
        account.profile = wallet.default_profile.name
        account.account_creation(account_path, password)


@main.command('info')
@click.option('-n', '--name', type=str, required=False, default='', help='Account name')
@click.option('--decode', required=False, is_flag=True, help='Account name')
@click.option('--list', 'is_list', required=False, is_flag=True, help='Account name')
def info(name, decode, is_list):
    wallet = Wallet()
    if not name:
        name = Account.get_default_account()
    account_path = Account.build_account_path(name)
    if not os.path.exists(account_path):
        print(f'The account named `{name}` does not exist')
        wallet.default_profile.set_default_account()
    password = None
    if decode:
        print('Attention! Hide information received after entering a password from prying eyes')
        password = wallet.default_profile.check_pass(attempts=3)
        if password is None:
            exit(1)
    accounts = wallet.default_profile.load_accounts(password)
    if not accounts:
        print(f'There are no accounts for the {wallet.default_profile.name} profile. To create an account, run the command: `nempy-cli.py account create`')
        exit(1)
    if not is_list:
        accounts = {name: accounts.get(name, {})}
    for account in accounts.values():
        if isinstance(account, DecoderStatus):
            exit(1)
        print(account)
        print('#############################################################################################')
    if decode:
        print_warning()


if __name__ == '__main__':
    main()
