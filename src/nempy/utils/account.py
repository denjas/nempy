import json
import os

import click
import stdiomask
from nempy.wallet import Wallet
from nempy.account import Account, print_warning, DecoderStatus, GenerationTypes
from nempy.engine import XYMEngine, EngineStatusCode
from .monitoring import connector
from tabulate import tabulate


addresses = None


@click.group('account')
def main():
    """
    Interactive account management
    :return:
    """
    print('|Interactive account management|')


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
    Get the balance for the current  account
    """
    wallet = Wallet()
    engine = XYMEngine(wallet.profile.account)
    if not address:
        address = wallet.profile.account.address
    balance = engine.get_balance(address)
    if balance == {}:
        print('There is no account, or there was no movement of funds on it')
        exit(0)
    h_balance = engine.mosaic_humanization(balance)
    print(json.dumps(h_balance, sort_keys=True, indent=2))


def monitoring_callback(transaction_info: dict):
    global addresses
    address = transaction_info['topic'].split('/')[1]
    if 'unconfirmedAdded/' in transaction_info['topic'] and address in addresses:
        print('[UNCONFIRMED] Transaction related to the given address enters the unconfirmed state, waiting to be included in a block.')
    elif 'confirmedAdded/' in transaction_info['topic'] and address in addresses:
        print('[CONFIRMED] Transaction related to the given address is included in a block')
        exit(0)
    elif 'status/' in transaction_info['topic'] and address in addresses:
        print(f'[REJECTED] Transaction rejected: {transaction_info["data"]["code"]}')
        exit(1)


def confirmation(address, mosaics, message, is_encrypted, fee, deadline):
    prepare = list()
    prepare.append(['Recipient address:', address])
    for mosaic in mosaics:
        prepare.append([f'Mosaic: {mosaic[0]}', f'Amount: {mosaic[1]}'])
    if message:
        prepare.append([f'Message (encrypted {is_encrypted})', message])
    prepare.append(['Max Fee:', fee])
    prepare.append(['Deadline (minutes):', f'{deadline}'])
    table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
    print(table)
    answer = input('Funds will be debited from your balance!\nWe continue? y/N: ')
    if answer.lower() != 'y':
        exit(1)


@main.command('send')
@click.option('-a', '--address', type=str, required=True, help='Recipient address')
@click.option('-pm', '--plain-message', type=str, required=False, default='', help='Plain message')
@click.option('-em', '--encrypted-message', type=str, required=False, default='', help='Encrypted message')
@click.option('-d', '--deadline', type=int, required=False, default=3, show_default=True,
              help='Transaction expiration time in minutes')
@click.option('-m', '--mosaics', type=str, required=False, multiple=True, default=None,
              help='Mosaic to transfer in the format (mosaicId(hex)|@aliasName)::absoluteAmount.` (examples: @symbol.xym::1.0 or 091F837E059AE13C:1.0)')
@click.option('-f', '--fee', type=click.Choice(['slowest', 'slow', 'average', 'fast']), required=False,
              default='slowest', show_default=True, help='Maximum commission you are willing to pay')
def send(address, plain_message, encrypted_message, mosaics, fee, deadline):
    """
    send mosaics or messages to the addressee
    """
    global addresses
    addresses = [address]
    if plain_message != '' and encrypted_message != '':
        print('Specify one of the message types.')
        exit(1)
    if plain_message == '' and encrypted_message == '' and mosaics is None:
        print('Specify for sending one of two - mosaic or a messages')
        exit(1)
    wallet = Wallet()
    engine = XYMEngine(wallet.profile.account)
    mosaics = [(mosaic.split(':')[0], float(mosaic.split(':')[1])) for mosaic in mosaics]
    message = plain_message or encrypted_message or ''
    is_encrypted = True if encrypted_message else False
    confirmation(address, mosaics, message, is_encrypted, fee, deadline)
    password = stdiomask.getpass(f'Enter your `{wallet.profile.name} [{wallet.profile.network_type.name}]` profile password: ')
    result = engine.send_tokens(recipient_address=address,
                                mosaics=mosaics,
                                message=message,
                                is_encrypted=is_encrypted,
                                password=password,
                                deadline={'minutes': deadline})
    if isinstance(result, EngineStatusCode):
        if result == EngineStatusCode.INVALID_ACCOUNT_INFO:
            print(result.value, '\nThe account either does not exist, or there were no transactions on it.\nUnable to get the public key from the network')
            exit(1)
    if result:
        subscribers = ['confirmedAdded', 'unconfirmedAdded', 'status']
        subscribers = [os.path.join(subscribe, address) for subscribe in subscribers]
        connector(engine.node_selector.url, subscribers, formatting=True, callback=monitoring_callback)


@main.command('history')
def setdefault():
    """
    Show history
    """
    wallet = Wallet()
    engine = XYMEngine(wallet.profile.account)
    wallet.profile.account.history(engine.timing)


if __name__ == '__main__':
    main()
