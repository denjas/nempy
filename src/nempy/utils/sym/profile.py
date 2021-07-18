import random
from enum import Enum
from hashlib import blake2b

import click
import logging
from tabulate import tabulate
import binascii
from pprint import pprint
import inquirer
from nempy.sym import network
import stdiomask
from symbolchain.core.Bip32 import Bip32
from symbolchain.core.facade.SymFacade import SymFacade
from bip_utils import Bip39MnemonicGenerator, Bip39WordsNum, Bip39Languages
from password_strength import PasswordPolicy


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
    node_url = input('Enter the Symbol node URL. (Example: http://localhost:3000): ') or 'http://192.168.0.103:3000'
    network.node_selector.url = node_url
    network_type = network.get_node_network()
    print(network_type.upper())
    if network_type == 'public':
        bip32_coin_id = 4343
    elif network_type == 'public_test':
        bip32_coin_id = 1
    else:
        raise ValueError('Invalid URL or network not supported')
    policy = PasswordPolicy.from_names(
        length=8,  # min length: 8
        uppercase=1,  # need min. 1 uppercase letters
        numbers=2,  # need min. 2 digits
        special=1,  # need min. 1 special characters
        nonletters=2,  # need min. 2 non-letter characters (digits, specials, anything)
    )
    is_good_pass = False
    while not is_good_pass:
        password = stdiomask.getpass(f'Enter your wallet password {policy.test("")}: ')
        in_policies = policy.test(password)
        if in_policies:
            print(in_policies)
        else:
            is_good_pass = True
    return network_type, bip32_coin_id, password


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
        accounts[address_view] = ({'Address': address_view,
                                   'Public Key': public_key,
                                   'Private Key': private_key,
                                   'Path': f"m/44'/{path[1]}'/{path[2]}'/0'/0'"})
    return accounts


def get_by_mnemonic(network_type, bip32_coin_id, is_generate=False):
    if is_generate:
        random_char_set = ''
        print('Write something (random character set), the input will be interrupted automatically')
        attempts = list(range(random.randint(4, 7)))
        for i in attempts:
            something = input(f'Something else ({len(attempts) - i}): ')
            if not something:
                print('Only a non-empty line will have to be repeated :(')
                attempts.append(len(attempts))
                continue
            random_char_set += something
        print(random_char_set)
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
    accounts[account]['Mnemonic'] = mnemonic
    return accounts[account]


def print_account(account, is_hidden=True):
    prepare = []
    for key, value in account.items():
        if key == 'Mnemonic':
            positions = [pos for pos, char in enumerate(value) if char == ' ']
            value = value[:positions[8]] + '\n' + value[positions[8] + 1:positions[16]] + '\n' + value[positions[16] + 1:]
        if is_hidden:
            if key in ['Private Key', 'Password', 'Mnemonic']:
                value = ''.join('*' for e in value if e.isalnum())
        prepare.append([key, value])
    table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
    print(table)


@click.group('profile')
def main():
    print('profile')


@main.command('import')
def import_account():
    network_type, bip32_coin_id, password = init_general_params()
    gen_type = get_gen_type()

    if gen_type == GenerationTypes.MNEMONIC:
        account = get_by_mnemonic(network_type, bip32_coin_id)
    account['Password'] = password
    print_account(account)


@main.command('create')
def create_account():
    network_type, bip32_coin_id, password = init_general_params()
    account = get_by_mnemonic(network_type, bip32_coin_id, is_generate=True)
    account['Password'] = password
    print_account(account)


if __name__ == '__main__':
    main()
