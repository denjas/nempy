import json
import os

import click
import stdiomask
from nempy.user_data import DecoderStatus
from nempy.config import C
from nempy.engine import XYMEngine, EngineStatusCode
from nempy.sym import ed25519
from nempy.sym.constants import HexSequenceSizes
from nempy.sym.network import Monitor, NetworkType
from nempy.wallet import Wallet
from nempy.ui import AccountUI, ProfileUI, print_warning
from tabulate import tabulate


@click.group('account', help='- Interactive account management')
def main():
    Wallet()
    print('|Interactive account management|')


@main.command('import')
def import_account():
    """
    Create a new account with existing private key or mnemonic
    """
    wallet = Wallet()
    account_data, is_default = AccountUI.iu_create_account(wallet.profile.data, wallet.accounts_dir, is_import=True)
    if account_data and is_default:
        wallet.profile.account.set_default_account(account_data)


@main.command('create')
def create_account():
    """
    Create a new account
    """
    wallet = Wallet()
    account_data, is_default = AccountUI.iu_create_account(wallet.profile.data, wallet.accounts_dir)
    if account_data and is_default:
        wallet.profile.account.set_default_account(account_data)


@main.command('info')
@click.option('-n', '--name', type=str, required=False, default='', help='Account name. If not set, the default account name will be used')
@click.option('-d', '--decrypt', required=False, is_flag=True, help='Decrypt secret data')
@click.option('-l', '--list', 'is_list', required=False, is_flag=True, help='List of all accounts of the current profile')
def info(name, decrypt, is_list):
    """
    Account Information
    """
    wallet = Wallet()
    accounts_data = wallet.profile.load_accounts()
    if not is_list:
        if not name and wallet.profile.account.data is not None:
            name = wallet.profile.account.data.name
        account = accounts_data.get(name, {})
        accounts_data = {name: account}
    password = None
    if decrypt:
        print(f'{C.RED}Attention! Hide information received after entering a password from prying eyes{C.END}')
        password = ProfileUI.ui_check_pass(wallet.profile.data, attempts=3)
        if password is None:
            exit(1)
    for account_data in accounts_data.values():
        if decrypt:
            account_data = account_data.decrypt(password)
            if isinstance(account_data, DecoderStatus):
                exit(1)
        str_account_data = str(account_data)
        if account_data.name == wallet.profile.account.data.name:
            str_account_data = str_account_data.replace('|              |', f'|  >{C.OKGREEN}DEFAULT{C.END}<   |', 1)
        print(str_account_data)
        print(f'{C.GREY}###################################################################################{C.END}')
    if decrypt:
        print_warning()


@main.command('balance')
@click.option('-a', '--address', type=str, required=False, default='', help='Get the balance at the address. Default current account balance')
def get_balance(address):
    """
    Get the balance for the current  account
    """
    wallet = Wallet()
    if not address:
        address = wallet.profile.account.data.address
    engine = XYMEngine(wallet.profile.account.data)
    balance = engine.get_balance(address, humanization=True)
    if balance == {}:
        print(f'Account `{address}` does not exist, or there was no movement of funds on it')
        exit(0)
    print(json.dumps(balance, sort_keys=True, indent=2))


def monitoring_callback(transaction_info: dict, addresses: list):
    address = transaction_info['topic'].split('/')[1]
    if 'unconfirmedAdded/' in transaction_info['topic'] and address in addresses:
        print(
            '[UNCONFIRMED] Transaction related to the given address enters the unconfirmed state, '
            'waiting to be included in a block...')
    elif 'confirmedAdded/' in transaction_info['topic'] and address in addresses:
        print('[CONFIRMED] Transaction related to the given address is included in a block')
        exit(0)
    elif 'status/' in transaction_info['topic'] and address in addresses:
        print(f'[REJECTED] Transaction rejected: {transaction_info["data"]["code"]}')
        exit(1)


def confirmation(address, mosaics, message, is_encrypted, fee, deadline, balance, network_type: NetworkType):
    prepare = list()
    network_type_str = network_type.value.upper()
    if network_type == NetworkType.MAIN_NET:
        network_type_str = f'{C.RED}{network_type.value.upper()}{C.END}'
    prepare.append(['Network Type', network_type_str])
    prepare.append(['Recipient address:', '-'.join(address[i:i + 6] for i in range(0, len(address), 6))])
    if message:
        prepare.append([f'Message (encrypted {is_encrypted})', message])
    prepare.append(['Max Fee:', fee])
    prepare.append(['Deadline (minutes):', f'{deadline}'])
    mosaics = {mosaic[0].replace("@", ""): {'amount': mosaic[1], 'balance': balance.get(mosaic[0].replace("@", ""), 0)}
               for mosaic in mosaics}
    mosaics_str_list = [f'`{k}`: {C.RED}- {v["amount"]}{C.END} (balance: {v["balance"]})' for k, v in mosaics.items()]
    mosaic_str = '\n'.join(mosaics_str_list)
    prepare.append(['Mosaics:', mosaic_str])
    table = tabulate(prepare, tablefmt='grid')
    print(table)
    for v in mosaics.values():
        if v['amount'] > v['balance']:
            print(f'Amount {C.ORANGE}{v["amount"]}{C.END} being sent exceeds the available balance {C.ORANGE}{v["balance"]}{C.END}')
            exit(1)
    answer = input(f'{C.ORANGE}Funds will be debited from your balance!{C.END}\nWe continue? y/N: ')
    if answer.lower() != 'y':
        exit(1)


@main.command('send')
@click.option('-a', '--address', type=str, required=True, help='Recipient address')
@click.option('-pm', '--plain-message', type=str, required=False, default='', help='Plain message')
@click.option('-em', '--encrypted-message', type=str, required=False, default='', help='Encrypted message')
@click.option('-d', '--deadline', type=int, required=False, default=3, show_default=True,
              help='Transaction expiration time in minutes')
@click.option('-m', '--mosaics', type=str, required=False, multiple=True, default=None,
              help='Mosaic to transfer in the format (mosaicId(hex)|@aliasName):amount.` '
                   '(examples: @symbol.xym:0.1 or 091F837E059AE13C:1.1)')
@click.option('-f', '--fee', type=click.Choice(['slowest', 'slow', 'average', 'fast']), required=False,
              default='slowest', show_default=True, help='Maximum commission you are willing to pay')
def send(address: str, plain_message: str, encrypted_message: str, mosaics: str, fee: str, deadline: int):
    """
    send mosaics or messages to the addressee
    """
    #  instead of the global variable 'addresses'
    def _monitoring_callback(transaction_info: dict):
        monitoring_callback(transaction_info, addresses)

    address = address.replace('-', '')
    addresses = [address]
    if plain_message != '' and encrypted_message != '':
        print('Specify one of the message types.')
        exit(1)
    if plain_message == '' and encrypted_message == '' and mosaics is None:
        print('Specify for sending one of two - mosaic or a messages')
        exit(1)
    for mosaic in mosaics:
        if not ed25519.check_hex(mosaic[0], HexSequenceSizes.MOSAIC_ID) and not mosaic[0].startswith('@'):
            print(f'`{mosaic[0]}` cannot be a mosaic index. You may have forgotten to put `@` in front of the alias name (example: @symbol.xym)')
            exit(1)
    wallet = Wallet()
    engine = XYMEngine(wallet.profile.account.data)
    balance = engine.get_balance(humanization=True)
    mosaics = [(mosaic.split(':')[0], float(mosaic.split(':')[1])) for mosaic in mosaics]
    message = plain_message or encrypted_message or ''
    is_encrypted = True if encrypted_message else False
    confirmation(address, mosaics, message, is_encrypted, fee, deadline, balance, wallet.profile.data.network_type)
    password = stdiomask.getpass(f'Enter your `{wallet.profile.data.name} [{wallet.profile.data.network_type.name}]` profile password: ')
    entity_hash, status = engine.send_tokens(recipient_address=address,
                                             mosaics=mosaics,
                                             message=message,
                                             is_encrypted=is_encrypted,
                                             password=password,
                                             deadline={'minutes': deadline})
    if status != EngineStatusCode.ACCEPTED:
        if status == EngineStatusCode.INVALID_ACCOUNT_INFO:
            print(status.value, '\nThe account either does not exist, or there were no transactions on it.'
                                '\nUnable to get the public key from the network')
        exit(1)
    subscribers = ['confirmedAdded', 'unconfirmedAdded', 'status']
    subscribers = [os.path.join(subscribe, address) for subscribe in subscribers]
    Monitor(engine.node_selector.url, subscribers, formatting=True, callback=_monitoring_callback)


@main.command('history')
@click.option('-ps', '-page-size', 'page_size', type=int, required=False, default=10, show_default=True,
              help='Select the number of entries to return.')
def history(page_size):
    """
    Show history
    """
    wallet = Wallet()
    AccountUI.ui_history_inquirer(wallet.profile.account.data.address, page_size)


@main.command('setdefault')
def setdefault():
    """
    Set default account
    """
    wallet = Wallet()
    AccountUI.ui_default_account(wallet.profile.load_accounts())


if __name__ == '__main__':
    main()
