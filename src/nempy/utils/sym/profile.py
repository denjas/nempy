import click
import logging
from pprint import pprint
import inquirer
from nempy.sym import network
import stdiomask
from symbolchain.core.Bip32 import Bip32
from symbolchain.core.facade.SymFacade import SymFacade


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

        accounts[address] = ({'Public Key': public_key, 'Private Key': private_key, 'Path': f"m/44'/{path[1]}'/{path[2]}'/0'/0'"})
    return accounts


@click.group('profile')
def main():
    print('profile')


@main.command('import')
def import_account():
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
    # password = stdiomask.getpass('Enter your wallet password: ')
    questions = [
        inquirer.List(
            "type",
            message="Select an import type?",
            choices=["Mnemonic", "Private Key"],
        ),
    ]

    answers = inquirer.prompt(questions)
    import_type = answers['type']

    if import_type == 'Mnemonic':
        mnemonic = stdiomask.getpass('Enter a mnemonic passphrase. Words must be separated by spaces: ')
        accounts = derive_key_by_mnemonic(network_type, bip32_coin_id, mnemonic)
        addresses = ['-'.join(account[i:i+6] for i in range(0, len(account), 6)) for account in accounts.keys()]
        questions = [
            inquirer.List(
                "address",
                message="Select an import type?",
                choices=addresses,
            ),
        ]
        answers = inquirer.prompt(questions)
        import_type = answers['address'].replace('-', '')
        pprint(accounts[import_type])


if __name__ == '__main__':
    main()
