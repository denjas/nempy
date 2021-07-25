import binascii
import logging
import os
import copy
import pickle
import random
from base64 import b64decode, b32encode
from base64 import b64encode
from enum import Enum
from hashlib import blake2b
from typing import List

import inquirer
import stdiomask
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Util.Padding import unpad
from bip_utils import Bip39MnemonicGenerator, Bip39Languages
from nempy.config import DEFAULT_ACCOUNTS_DIR
from nempy.sym import network
from nempy.sym.api import Mosaic
from nempy.sym.network import TransactionResponse
from nempy.sym.constants import NetworkType, TransactionStatus, TransactionTypes
from symbolchain.core.Bip32 import Bip32
from symbolchain.core.CryptoTypes import Hash256
from symbolchain.core.facade.SymFacade import SymFacade
from tabulate import tabulate
from binascii import unhexlify, hexlify

logger = logging.getLogger(__name__)


def print_warning():
    print("""
                                !!! Important !!!
 Save the mnemonic, it will be needed to restore access to the wallet in case of password loss
       Where to store can be found here - https://en.bitcoinwiki.org/wiki/Mnemonic_phrase
!!!Do not share your secret key and mnemonic with anyone, it guarantees access to your funds!!!
                                       !!!
    """)


def encryption(password: str, data: bytes) -> bytes:
    key = blake2b(password.encode(), digest_size=16).hexdigest().encode()
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(data, AES.block_size))
    iv = b64encode(cipher.iv)
    ct = b64encode(ct_bytes)
    result = iv + ct
    return result


def decryption(password: str, encrypted_data: bytes) -> [bytes, None]:
    encrypted_data = encrypted_data.decode('utf-8')
    key = blake2b(password.encode(), digest_size=16).hexdigest().encode()
    try:
        iv = b64decode(encrypted_data[0:24])
        ct = b64decode(encrypted_data[24:])
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt
    except (ValueError, KeyError):
        return None


class GenerationTypes(Enum):
    MNEMONIC = 0
    PRIVATE_KEY = 1


class DecoderStatus(Enum):
    DECRYPTED = None
    NO_DATA = 'Missing data to decode'
    WRONG_PASS = 'Wrong password'


class Account:
    name = None
    _address = None
    public_key = None
    private_key = None
    path = None
    mnemonic = None
    network_type: NetworkType = None
    profile = None

    def __init__(self, account: dict = None):
        if account is not None:
            [setattr(self, key, value) for key, value in account.items()]
            if self.private_key is None:
                raise AttributeError('The private key is required for the account')

    def __str__(self):
        prepare = list()
        for key, value in self.__dict__.items():
            if key == '_address':
                value = '-'.join(value[i:i + 6] for i in range(0, len(value), 6))
            if key == 'mnemonic' and not isinstance(value, bytes):
                positions = [pos for pos, char in enumerate(value) if char == ' ']
                value = value[:positions[8]] + '\n' + value[positions[8] + 1:positions[16]] + '\n' + value[positions[16] + 1:]
            elif key == 'mnemonic' and isinstance(value, bytes):
                value = '******* **** ********** ******* ***** *********** ******** *****'
            if key == 'private_key' and isinstance(value, bytes):
                value = '*' * 64
            if isinstance(value, NetworkType):
                value = value.name
            key = key.replace('_', ' ').title()
            prepare.append([key, value])
        table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
        return table

    @property
    def address(self):
        return self._address

    @address.setter
    def address(self, address: str):
        self._address = address.replace('-', '')

    def serialize(self):
        return pickle.dumps(self.__dict__)

    @staticmethod
    def deserialize(data):
        des_date = pickle.loads(data)
        return Account(des_date)

    @staticmethod
    def build_account_path(name):
        account_path = os.path.join(DEFAULT_ACCOUNTS_DIR, name + '.account')
        return account_path

    @staticmethod
    def init_general_params(network_type) -> (str, str, NetworkType, int, str):
        while True:
            name = input('Enter the account name: ')
            if name != '':
                account_path = Account.build_account_path(name)
                if os.path.exists(account_path):
                    print('An account with the same name already exists, please select a different name')
                    continue
                break
            print('The name cannot be empty.')
        is_default = False
        answer = input(f'Set `{name}` account as default? Y/n: ') or 'y'
        if answer.lower() == 'y':
            is_default = True
        if network_type == NetworkType.MAIN_NET:
            bip32_coin_id = 4343
        elif network_type == NetworkType.TEST_NET:
            bip32_coin_id = 1
        else:
            raise ValueError('Invalid URL or network not supported')
        return account_path, name, bip32_coin_id, is_default

    @staticmethod
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
        accounts = Account.derive_key_by_mnemonic(network_type, bip32_coin_id, mnemonic)
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
        return accounts[account]

    @staticmethod
    def derive_key_by_mnemonic(network_type, bip32_coin_id, mnemonic):
        facade = SymFacade(network_type.value)

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
            accounts[address] = ({'address': address,
                                  'public_key': public_key,
                                  'private_key': private_key,
                                  'mnemonic': mnemonic,
                                  'path': f"m/44'/{path[1]}'/{path[2]}'/0'/0'",
                                  'network_type': network_type})
        return accounts

    def account_creation(self, account_path, password):
        self.write_account(account_path, password)
        print(f'\nAccount created at: {account_path}')
        account = Account.read_account(account_path).decode(password)
        print(account)
        print_warning()

    def write_account(self, path, password):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pickle_private_key = pickle.dumps(self.private_key)
        self.private_key = encryption(password=password, data=pickle_private_key)
        if self.mnemonic is not None:
            pickle_mnemonic = pickle.dumps(self.mnemonic)
            self.mnemonic = encryption(password=password, data=pickle_mnemonic)
        pickled_data = self.serialize()
        with open(path, 'wb') as opened_file:
            opened_file.write(pickled_data)
        logger.debug(f'Wallet saved along the way: {path}')

    def decode(self, password):
        decoded_account = copy.deepcopy(self)
        decrypted_key = decryption(password, self.private_key)
        if decrypted_key is None:
            logger.error(DecoderStatus.WRONG_PASS.value)
            raise SystemExit(DecoderStatus.WRONG_PASS.value)
        decoded_account.private_key = pickle.loads(decrypted_key)
        if decoded_account.mnemonic is not None:
            decoded_account.mnemonic = pickle.loads(decryption(password, self.mnemonic))
        return decoded_account

    @staticmethod
    def read_account(path: str):
        if not os.path.exists(path):
            logger.error(DecoderStatus.NO_DATA.value)
            return DecoderStatus.NO_DATA
        account = Account.deserialize(open(path, 'rb').read())
        return account


    # @staticmethod
    # def read_accounts(profile: str, password: str = None):
    #     accounts_dir = os.listdir(DEFAULT_ACCOUNTS_DIR)
    #     accounts = list()
    #     for account in accounts_dir:
    #         path = os.path.join(DEFAULT_ACCOUNTS_DIR, account)
    #         _account = Account.read_account(path, password)
    #         if _account.profile == profile:
    #             accounts.append(_account)
    #     return accounts

    @staticmethod
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

    def history(self, page_size):
        conf_transactions: List[TransactionResponse] = network.search_transactions(address=self.address,
                                                                                   page_size=page_size,
                                                                                   transaction_status=TransactionStatus.CONFIRMED_ADDED)
        unconf_transactions: List[TransactionResponse] = network.search_transactions(address=self.address,
                                                                                     page_size=page_size,
                                                                                     transaction_status=TransactionStatus.UNCONFIRMED_ADDED)
        transactions = unconf_transactions + conf_transactions
        short_names = {}
        for transaction in transactions:
            mosaic = '∴' if len(transaction.transaction.mosaics) > 1 else ''
            message = '🖂' if transaction.transaction.message is not None else ' '
            direction = '➕' if transaction.transaction.recipientAddress == self.address else '➖'
            status = '🗸' if transaction.status == TransactionStatus.CONFIRMED_ADDED.value else '?'
            short_name = f'{status} {direction} {transaction.transaction.recipientAddress} | {transaction.meta.height} | {transaction.transaction.deadline} |{message} |{transaction.transaction.mosaics[0]} {mosaic}'
            short_names[short_name] = transaction
        _short_names = list(short_names.keys())
        _short_names.append('Exit')
        while True:
            questions = [
                inquirer.List(
                    "transaction",
                    message="Select an transaction?",
                    choices=_short_names,
                ),
            ]
            answers = inquirer.prompt(questions)
            transaction = answers['transaction']
            if transaction == 'Exit':
                exit(0)
            print(short_names[transaction])


    # @staticmethod
    # def set_default_account(name):
    #
    #     config = configparser.ConfigParser()
    #     config.read(CONFIG_FILE)
    #     config['account']['default'] = name
    #     with open(CONFIG_FILE, 'w') as configfile:
    #         config.write(configfile)
