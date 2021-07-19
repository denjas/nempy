import binascii
import os
import random
from enum import Enum
from hashlib import blake2b

import click
import inquirer
import stdiomask
from bip_utils import Bip39MnemonicGenerator, Bip39Languages
from nempy.config import DEFAULT_WALLETS_DIR
from nempy.sym import network
from nempy.wallet import Account, write_account, read_account
from password_strength import PasswordPolicy
from symbolchain.core.Bip32 import Bip32
from symbolchain.core.facade.SymFacade import SymFacade


class GenerationTypes(Enum):
    MNEMONIC = 0
    PRIVATE_KEY = 1


def get_gen_type() -> GenerationTypes:
    questions = [
        inquirer.List(
            "type",
            message="Select an import type?",
            choices=["Mnemonic", "Private Key"],
        ),
    ]

    answers = inquirer.prompt(questions)
    import_type = answers['type']
    if import_type == 'Private Key':
        return GenerationTypes.PRIVATE_KEY
    return GenerationTypes.MNEMONIC


def init_general_params() -> (str, int, str):
    while True:
        name = input('Enter the account name: ')
        if name != '':
            account_path = os.path.join(DEFAULT_WALLETS_DIR, name + '.account')
            if os.path.exists(account_path):
                print('An account with the same name already exists, please select a different name')
                continue
            break
        print('The name cannot be empty.')
    node_url = input('Enter the Symbol node URL. (Example: http://localhost:3000): ')
    network.node_selector.url = node_url
    network_type = network.get_node_network()
    print(network_type.upper())
    if network_type == 'public':
        bip32_coin_id = 4343
    elif network_type == 'public_test':
        bip32_coin_id = 1
    else:
        raise ValueError('Invalid URL or network not supported')
    return account_path, name, network_type, bip32_coin_id, node_url


def input_pass(n_attempts: int, valid_pass: str = None):
    policy = PasswordPolicy.from_names(
        length=8,  # min length: 8
        uppercase=1,  # need min. 1 uppercase letters
        numbers=2,  # need min. 2 digits
        special=1,  # need min. 1 special characters
        nonletters=2,  # need min. 2 non-letter characters (digits, specials, anything)
    )
    for i in range(n_attempts):
        password = stdiomask.getpass(f'Enter your wallet password {policy.test("")}: ')
        in_policies = policy.test(password)
        if in_policies:
            if valid_pass is not None:
                print(f'The entered password does not match the previously entered. Attempts left: {n_attempts - i}')
            else:
                print(in_policies)
        else:
            if valid_pass is not None:
                if valid_pass == password:
                    return password
                else:
                    print(f'The entered password does not match the previously entered. Attempts left: {n_attempts - i}')
                    continue
            else:
                return password
    return None


def derive_key_by_mnemonic(network_type, bip32_coin_id, mnemonic):
    facade = SymFacade(network_type)

    bip = Bip32(facade.BIP32_CURVE_NAME)
    root_node = bip.from_mnemonic(mnemonic, '')
    accounts = {}
    for i in range(10):
        path = [44, bip32_coin_id, i, 0, 0]
        child_node = root_node.derive_path(path)
        child_key_pair = facade.bip32_node_to_key_pair(child_node)
        private_key = str(child_key_pair.private_key).upper()
        public_key = str(child_key_pair.public_key).upper()
        address = str(facade.network.public_key_to_address(child_key_pair.public_key)).upper()
        address_view = '-'.join(address[i:i + 6] for i in range(0, len(address), 6))
        accounts[address_view] = ({'address': address_view,
                                   'public_key': public_key,
                                   'private_key': private_key,
                                   'path': f"m/44'/{path[1]}'/{path[2]}'/0'/0'"})
    return accounts


def account_by_mnemonic(network_type, bip32_coin_id, is_generate=False):
    if is_generate:
        random_char_set = ''
        print('Write something (random character set), the input will be interrupted automatically')
        attempts = list(range(random.randint(3, 5)))
        for i in attempts:
            something = input(f'Something else ({len(attempts) - i}): ')
            if not something:
                print('Only a non-empty line will have to be repeated :(')
                attempts.append(len(attempts))
                continue
            random_char_set += something
        entropy_bytes_hex = blake2b(random_char_set.encode(), digest_size=32).hexdigest().encode()
        mnemonic = Bip39MnemonicGenerator(Bip39Languages.ENGLISH).FromEntropy(binascii.unhexlify(entropy_bytes_hex))
    else:
        mnemonic = stdiomask.getpass('Enter a mnemonic passphrase. Words must be separated by spaces: ')
    accounts = derive_key_by_mnemonic(network_type, bip32_coin_id, mnemonic)
    addresses = [account for account in accounts.keys()]
    questions = [
        inquirer.List(
            "address",
            message="Select an import type?",
            choices=addresses,
        ),
    ]
    answers = inquirer.prompt(questions)
    account = answers['address']
    accounts[account]['mnemonic'] = mnemonic
    return accounts[account]


def account_creation(account, account_path):
    print(repr(account))
    print('Password repeat to show hidden information')
    password = input_pass(3, valid_pass=account.password)
    if password is not None:
        write_account(account_path, password, account)
        print(f'\nAccount created at: {account_path}')
        account = read_account(account_path, password)
        print(account)
        print_warning()


def print_warning():
    print("""
                                !!! Important !!!
Save the mnemonic, it will be needed to restore access to the wallet in case of password loss
Where to store can be found here - https://en.bitcoinwiki.org/wiki/Mnemonic_phrase
!!!Do not share your secret key and mnemonic with anyone, it guarantees access to your funds!!!
    """)


@click.group('profile')
def main():
    """
    Interactive profile creation or importing mode
    :return:
    """
    print('Interactive profile creation mode:')


@main.command('import')
def import_account():
    account_path, name, network_type, bip32_coin_id, node_url = init_general_params()
    password = input_pass(10)
    gen_type = get_gen_type()

    if gen_type == GenerationTypes.MNEMONIC:
        account = account_by_mnemonic(network_type, bip32_coin_id)
    account['password'] = password
    account['name'] = name
    account['node_url'] = node_url
    account = Account(account)
    account_creation(account, account_path)


@main.command('create')
def create_account():
    account_path, name, network_type, bip32_coin_id, node_url = init_general_params()
    password = input_pass(10)
    account = account_by_mnemonic(network_type, bip32_coin_id, is_generate=True)

    account['password'] = password
    account['name'] = name
    account['node_url'] = node_url
    account = Account(account)
    account_creation(account, account_path)


if __name__ == '__main__':
    main()
