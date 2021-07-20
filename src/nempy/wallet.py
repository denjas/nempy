import binascii
import configparser
import logging
import os
import pickle
import random

import bcrypt
from base64 import b64decode
from base64 import b64encode
from enum import Enum
from hashlib import blake2b

import inquirer
import stdiomask
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Util.Padding import unpad
from bip_utils import Bip39MnemonicGenerator, Bip39Languages
from symbolchain.core.Bip32 import Bip32
from nempy.config import CONFIG_FILE, PROFILES_FILES, DEFAULT_ACCOUNTS_DIR
from nempy.sym import network
from nempy.sym.constants import NetworkType
from password_strength import PasswordPolicy
from symbolchain.core.facade.SymFacade import SymFacade
from tabulate import tabulate
from nempy.sym.config import MAIN_NODE_URLs, TEST_NODE_URLs


def print_warning():
    print("""
                                !!! Important !!!
Save the mnemonic, it will be needed to restore access to the wallet in case of password loss
Where to store can be found here - https://en.bitcoinwiki.org/wiki/Mnemonic_phrase
!!!Do not share your secret key and mnemonic with anyone, it guarantees access to your funds!!!
    """)


def input_new_pass(n_attempts: int):
    policy = PasswordPolicy.from_names(
        length=8,  # min length: 8
        uppercase=1,  # need min. 1 uppercase letters
        numbers=2,  # need min. 2 digits
        special=1,  # need min. 1 special characters
        nonletters=2,  # need min. 2 non-letter characters (digits, specials, anything)
    )
    new_password = None
    for i in range(n_attempts):
        new_password = stdiomask.getpass(f'Enter your new account password {policy.test("")}: ')
        in_policies = policy.test(new_password)
        if in_policies:
            print(in_policies)
        else:
            break
    if new_password is None:
        return None
    for i in range(n_attempts):
        repeat_password = stdiomask.getpass(f'Repeat password: ')
        if repeat_password != new_password:
            print(f'Try again, attempts left {n_attempts-i}')
        else:
            return new_password
    return None


def input_network_type() -> NetworkType:
    questions = [
        inquirer.List(
            "type",
            message="Select an network type?",
            choices=["TEST_NET", "MAIN_NET"],
        ),
    ]
    answers = inquirer.prompt(questions)
    network_type = answers['type']
    if network_type == 'MAIN_NET':
        network_type = NetworkType.MAIN_NET
    elif network_type == 'TEST_NET':
        network_type = NetworkType.TEST_NET
    else:
        raise TypeError('Unknown network type')
    return network_type


def input_profile_name():
    while True:
        name = input('Enter profile name: ')
        path = os.path.join(PROFILES_FILES, f'{name}.profile')
        if name == '':
            print('The name cannot be empty')
        elif os.path.exists(path):
            print(f'A profile named `{name}` already exists')
        else:
            return name, path


class DecoderStatus(Enum):
    DECRYPTED = None
    NO_DATA = 'Missing data to decode'
    WRONG_PASS = 'Wrong password'


class GenerationTypes(Enum):
    MNEMONIC = 0
    PRIVATE_KEY = 1


class Account:
    name = None
    address = None
    public_key = None
    private_key = None
    path = None
    mnemonic = None
    network_type: NetworkType = None
    secret = None
    profile = None

    def __init__(self, account: dict = None):
        if account is not None:
            [setattr(self, key, value) for key, value in account.items()]
            if self.secret is None:
                raise AttributeError('The private key is required for the account')

    # def __repr__(self):
    #     prepare = list()
    #     for key, value in self.__dict__.items():
    #         if key == 'secret':
    #             value = '****************************************************************'
    #         key = key.replace('_', ' ').title()
    #         prepare.append([key, value])
    #     table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
    #     return table

    def __str__(self):
        prepare = list()
        for key, value in self.__dict__.items():
            if key in ['secret', 'network_type']:
                continue
            if key == 'address':
                value = '-'.join(value[i:i + 6] for i in range(0, len(value), 6))
            key = key.replace('_', ' ').title()
            prepare.append([key, value])
        for key, value in self.__dict__['secret'].items():
            if key == 'mnemonic':
                positions = [pos for pos, char in enumerate(value) if char == ' ']
                value = value[:positions[8]] + '\n' + value[positions[8] + 1:positions[16]] + '\n' + value[positions[16] + 1:]
            key = key.replace('_', ' ').title()
            prepare.append([key, value])
        prepare.append(['Network Type', self.network_type.name])
        table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
        return table

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
        if network_type == NetworkType.MAIN_NET:
            bip32_coin_id = 4343
        elif network_type == NetworkType.TEST_NET:
            bip32_coin_id = 1
        else:
            raise ValueError('Invalid URL or network not supported')
        return account_path, name, bip32_coin_id

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
        accounts[account]['secret'].update({'mnemonic': mnemonic})
        accounts[account]['network_type'] = network_type
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
                                  'secret': {'private_key': private_key},
                                  'path': f"m/44'/{path[1]}'/{path[2]}'/0'/0'"})
        return accounts

    def account_creation(self, account_path, password):
        self.write_account(account_path, password)
        print(f'\nAccount created at: {account_path}')
        account = Account.read_account(account_path, password)
        print(account)
        print_warning()

    def write_account(self, path, password):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        secret = pickle.dumps(self.secret)
        enc_secret = encryption(password=password, data=secret)
        self.secret = enc_secret
        pickled_data = self.serialize()
        with open(path, 'wb') as opened_file:
            opened_file.write(pickled_data)
        logging.debug(f'Wallet saved along the way: {path}')

    @staticmethod
    def read_account(path: str, password: str = None):
        if not os.path.exists(path):
            logging.error(DecoderStatus.NO_DATA.value)
            return DecoderStatus.NO_DATA
        account = Account.deserialize(open(path, 'rb').read())
        if password is None:
            account.secret = {}
            return account
        account.secret = pickle.loads(decryption(password, account.secret))
        if account.secret is None:
            logging.error(DecoderStatus.WRONG_PASS.value)
            return DecoderStatus.WRONG_PASS
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

    @staticmethod
    def get_default_account():
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        return config['account']['default']

    @staticmethod
    def set_default_account(name):

        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        config['account']['default'] = name
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)


class Profile:
    name = None
    network_type: NetworkType = None
    pass_hash = None

    def __init__(self, profile: dict = None):
        os.makedirs(PROFILES_FILES, exist_ok=True)
        if profile is not None:
            [setattr(self, key, value) for key, value in profile.items()]

    def __str__(self):
        prepare = [[key.replace('_', ' ').title(), value]
                   for key, value in self.__dict__.items() if key != 'network_type']
        prepare.append(['Network Type', self.network_type.name])
        table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
        return table

    def __repr__(self):
        return self.name

    def load_accounts(self, password=None) -> dict:
        accounts = {}
        accounts_paths = os.listdir(DEFAULT_ACCOUNTS_DIR)
        for account_path in accounts_paths:
            path = os.path.join(DEFAULT_ACCOUNTS_DIR, account_path)
            account = Account.read_account(path, password)
            if account.profile == self.name:
                accounts[os.path.splitext(account_path)[0]] = account
        return accounts

    def set_default_account(self):
        accounts = self.load_accounts()
        if not accounts:
            print(f'There are no accounts for the {self.name} profile. To create an account, run the command: `nempy-cli.py account create`')
            exit(1)
        questions = [
            inquirer.List(
                "name",
                message="Select default account",
                choices=accounts.keys(),
            ),
        ]
        answers = inquirer.prompt(questions)
        account = accounts[answers['name']]
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        config['account']['default'] = account.name
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

    def check_pass(self, password: str = None, attempts: int = 1):
        if password is not None:
            if bcrypt.checkpw(password.encode('utf-8'), self.pass_hash):
                return password
            else:
                logging.error('Incorrect password')
                return None

        for i in range(attempts):
            password = stdiomask.getpass(f'Enter your `{self.name} [{self.network_type.name}]` profile password: ')
            if bcrypt.checkpw(password.encode('utf-8'), self.pass_hash):
                return password
            print(f'Incorrect password. Try again ({attempts - 1 - i})')
        logging.error('Incorrect password')
        return None

    def create_profile(self):
        self.name, path = input_profile_name()
        self.network_type = input_network_type()
        new_pass = input_new_pass(10)
        if new_pass is None:
            exit(1)
        self.pass_hash = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt(12))
        self.save_profile(path)
        print(f'Profile {self.name} successful created by path: {path}')
        print(self)
        return path

    def save_profile(self, path):
        pickled = self.serialize()
        with open(path, 'wb') as opened_file:
            opened_file.write(pickled)

    def loaf_profile(self, path):
        with open(path, 'rb') as opened_file:
            return self.deserialize(opened_file.read())

    def serialize(self):
        return pickle.dumps(self.__dict__)

    @staticmethod
    def deserialize(data):
        des_date = pickle.loads(data)
        return Profile(des_date)


class Wallet:

    profiles = dict()
    default_profile: Profile = None

    def __init__(self):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        self.load_profiles()
        if not self.profiles:
            print('No profiles have been created. To create a profile, run the command `nempy-cli.py profile create`')
            exit(1)
        self.init_default_profile()

    def load_profiles(self):
        profiles_paths = os.listdir(PROFILES_FILES)
        for pp in profiles_paths:
            path = os.path.join(PROFILES_FILES, pp)
            profile = Profile().loaf_profile(path)
            self.profiles[os.path.splitext(pp)[0]] = profile

    def print_profiles(self):
        for profile in self.profiles.values():
            print(profile)
            print('#############################################################################################')

    def init_default_profile(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        default_profile = self.profiles.get(config['profile']['default'])
        if default_profile is None:
            self.set_default_profile()
        else:
            self.default_profile = default_profile
        network.node_selector.network_type = self.default_profile.network_type

    def set_default_profile(self):
        names = {profile.name + f' [{profile.network_type.name}]': profile.name for profile in self.profiles.values()}
        questions = [
            inquirer.List(
                "name",
                message="Select default profile",
                choices=names.keys(),
            ),
        ]
        answers = inquirer.prompt(questions)
        name = names[answers['name']]
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        profile = self.profiles[name]
        config['profile']['default'] = profile.name
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        self.default_profile = profile


def encryption(password: str, data: bytes) -> str:
    key = blake2b(password.encode(), digest_size=16).hexdigest().encode()
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(data, AES.block_size))
    iv = b64encode(cipher.iv).decode('utf-8')
    ct = b64encode(ct_bytes).decode('utf-8')
    result = iv + ct
    return result


def decryption(password: str, encrypted_data: str) -> [bytes, None]:
    key = blake2b(password.encode(), digest_size=16).hexdigest().encode()
    try:
        iv = b64decode(encrypted_data[0:24])
        ct = b64decode(encrypted_data[24:])
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt
    except (ValueError, KeyError):
        return None




