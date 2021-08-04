import binascii
import copy
import json
import logging
import os
import pickle
import random
from base64 import b64decode
from base64 import b64encode
from enum import Enum
from hashlib import blake2b
from typing import List, Union, Tuple, Dict, _GenericAlias, Optional

import inquirer
import stdiomask
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Util.Padding import unpad
from bip_utils import Bip39MnemonicGenerator, Bip39Languages
from nempy.config import C
from nempy import config
from nempy.sym import network
from nempy.sym.constants import NetworkType, TransactionStatus, AccountValidationState
from nempy.sym.network import TransactionResponse
from symbolchain.core.Bip32 import Bip32
from symbolchain.core.facade.SymFacade import SymFacade
from tabulate import tabulate
from pydantic import BaseModel, validator, StrictStr, StrictBytes
from pydantic.dataclasses import dataclass
from nempy.sym.ed25519 import check_address

logger = logging.getLogger(__name__)


def print_warning():
    print(f""" {C.ORANGE}
                                !!! Important !!!
 Save the mnemonic, it will be needed to restore access to the wallet in case of password loss
       Where to store can be found here - https://en.bitcoinwiki.org/wiki/Mnemonic_phrase
!!!Do not share your secret key and mnemonic with anyone, it guarantees access to your funds!!!
                                       !!!{C.END}
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


class GenerationType(Enum):
    MNEMONIC = 0
    PRIVATE_KEY = 1


class DecoderStatus(Enum):
    DECRYPTED = None
    NO_DATA = 'Missing data to decode'
    WRONG_DATA = 'Wrong data format, expected `bytes`'
    WRONG_PASS = 'Wrong password'


class Account(BaseModel):
    name: Optional[str] = None
    address: StrictStr
    public_key: StrictStr
    private_key: Union[StrictStr, StrictBytes]
    path: Optional[StrictStr] = None
    mnemonic: Union[StrictStr, StrictBytes] = None
    network_type: NetworkType
    profile: Optional[str] = None

    class Config:
        pass
        validate_assignment = True
        # require_by_default = False

    @validator('address')
    def validate_address(cls, address):
        address = address.replace('-', '')
        if (avs := check_address(address)) != AccountValidationState.OK:
            raise ValueError(avs.value)
        return address

    def __str__(self):
        prepare = list()
        for key, value in self.__dict__.items():
            if key == 'address':
                value = '-'.join(value[i:i + 6] for i in range(0, len(value), 6))
            if key == 'mnemonic' and not isinstance(value, bytes):
                positions = [pos for pos, char in enumerate(value) if char == ' ']
                value = C.OKBLUE + value[:positions[8]] + f'{C.END}\n' + C.OKBLUE + value[positions[8] + 1:positions[16]] + f'{C.END}\n' + C.OKBLUE + value[positions[16] + 1:] + C.END
            elif key == 'mnemonic' and isinstance(value, bytes):
                value = f'{C.OKBLUE}******* **** ********** ******* ***** *********** ******** *****{C.END}'
            if key == 'private_key' and isinstance(value, bytes):
                value = '*' * 64
            if key == 'private_key' and isinstance(value, str):
                value = C.OKBLUE + value + C.END
            if isinstance(value, NetworkType):
                value = value.name
            key = key.replace('_', ' ').title()
            prepare.append([key, value])
        account = f'Account - {self.name}'
        indent = (len(self.public_key) - len(account)) // 2
        account = C.INVERT + ' ' * indent + account + ' ' * indent + C.END
        table = tabulate(prepare, headers=['', f'{account}'], tablefmt='grid')
        return table

    def __eq__(self, other: 'Account'):
        if self.name == other.name and \
                self.path == other.path and \
                self.address == other.address and \
                self.network_type == other.network_type and \
                self.public_key == other.public_key and \
                self.profile == other.profile and \
                isinstance(self.private_key, type(other.private_key)) and \
                isinstance(self.mnemonic, type(other.mnemonic)):
            return True
        return False

    def serialize(self) -> bytes:
        sdate = pickle.dumps(self.dict())
        return sdate

    @classmethod
    def deserialize(cls, data) -> 'Account':
        ddate = pickle.loads(data)
        return cls(**ddate)

    def decrypt(self, password: str) -> 'Account':
        if not isinstance(self.private_key, bytes):
            logger.error('Unencrypted account?')
            raise ValueError(DecoderStatus.WRONG_DATA.value)
        decrypted_account = copy.deepcopy(self)
        decrypted_key = decryption(password, self.private_key)
        if decrypted_key is None:
            logger.error(DecoderStatus.WRONG_PASS.value)
            raise ValueError(DecoderStatus.WRONG_PASS.value)
        decrypted_account.private_key = pickle.loads(decrypted_key)
        if decrypted_account.mnemonic is not None:
            decrypted_account.mnemonic = pickle.loads(decryption(password, self.mnemonic))
        return decrypted_account

    @classmethod
    def read(cls, path: str) -> Union['Account', DecoderStatus]:
        if not os.path.exists(path):
            logger.error(DecoderStatus.NO_DATA.value)
            return DecoderStatus.NO_DATA
        account = cls.deserialize(open(path, 'rb').read())
        return account

    def encrypt(self, password: str) -> 'Account':
        pickle_private_key = pickle.dumps(self.private_key)
        # encrypt the private key
        self.private_key = encryption(password=password, data=pickle_private_key)
        if self.mnemonic is not None:
            pickle_mnemonic = pickle.dumps(self.mnemonic)
            # encrypt the mnemonic
            self.mnemonic = encryption(password=password, data=pickle_mnemonic)
        return self

    def is_encrypted(self):
        return isinstance(self.private_key, bytes)

    def write(self, path: str):
        if not isinstance(self.private_key, bytes):
            raise ValueError('Account data is recorded unencrypted')
        os.makedirs(os.path.dirname(path), exist_ok=True)

        pickled_data = self.serialize()
        with open(path, 'wb') as opened_file:
            opened_file.write(pickled_data)
        logger.debug(f'Wallet saved along the way: {path}')

    @classmethod
    def init_general_params(cls, network_type: NetworkType, accounts_dir: str) -> Tuple[str, str, int, bool]:
        while True:
            name = input('Enter the account name: ')
            if name != '':
                account_path = os.path.join(accounts_dir, name + '.account')
                if os.path.exists(account_path):
                    print('An account with the same name already exists, please select a different name')
                    continue
                break
            print('The name cannot be empty.')
        is_default = False
        answer = input(f'Set `{name}` account as default? [Y/n]: ') or 'y'
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
    def input_keyprint_entropy():
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
        return random_char_set

    @staticmethod
    def inquirer_account(accounts_names):
        addresses = [account for account in accounts_names]
        questions = [
            inquirer.List(
                "address",
                message="Select an import type?",
                choices=addresses,
            ),
        ]
        answers = inquirer.prompt(questions)
        account_name = answers['address']
        return account_name

    @classmethod
    def account_by_mnemonic(cls, network_type: NetworkType, bip32_coin_id: int, is_import: bool = False) -> 'Account':
        if is_import:
            mnemonic = stdiomask.getpass('Enter a mnemonic passphrase. Words must be separated by spaces: ')
        else:
            random_char_set = cls.input_keyprint_entropy()
            entropy_bytes_hex = blake2b(random_char_set.encode(), digest_size=32).hexdigest().encode()
            mnemonic = Bip39MnemonicGenerator(Bip39Languages.ENGLISH).FromEntropy(binascii.unhexlify(entropy_bytes_hex))

        accounts = cls._accounts_pool_by_mnemonic(network_type, bip32_coin_id, mnemonic)
        account_name = cls.inquirer_account(accounts.keys())
        return accounts[account_name]

    @classmethod
    def _accounts_pool_by_mnemonic(cls, network_type: NetworkType, bip32_coin_id: int, mnemonic: str) -> Dict[str, 'Account']:
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
            accounts[address] = cls(**{'address': address,
                                       'public_key': public_key,
                                       'private_key': private_key,
                                       'mnemonic': mnemonic,
                                       'path': f"m/44'/{path[1]}'/{path[2]}'/0'/0'",
                                       'network_type': network_type})
        return accounts

    def account_creation(self, account_path: str, password: str):
        self.encrypt(password).write(account_path)
        print(f'\nAccount created at: {account_path}')
        # checking the ability to read and display information about the account
        account = Account.read(account_path).decrypt(password)
        print(account)
        print_warning()

    @staticmethod
    def get_generation_type() -> GenerationType:
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
            return GenerationType.PRIVATE_KEY
        return GenerationType.MNEMONIC

    def inquirer_history(self, address: str = None, page_size: int = 10):
        if address is None:
            address = self.address
        conf_transactions: List[TransactionResponse] = network.search_transactions(address=address,
                                                                                   page_size=page_size,
                                                                                   transaction_status=TransactionStatus.CONFIRMED_ADDED)
        unconf_transactions: List[TransactionResponse] = network.search_transactions(address=address,
                                                                                     page_size=page_size,
                                                                                     transaction_status=TransactionStatus.UNCONFIRMED_ADDED)
        transactions = unconf_transactions + conf_transactions
        short_names = {}
        for transaction in transactions:
            is_mosaic = '∴' if len(transaction.transaction.mosaics) > 1 else ''
            message = '🖂' if transaction.transaction.message is not None else ' '
            direction = '+' if transaction.transaction.recipientAddress == address else '−'
            status = '🗸' if transaction.status == TransactionStatus.CONFIRMED_ADDED.value else '?'
            mosaic = next(iter(transaction.transaction.mosaics), '')
            short_name = f'{status} {transaction.transaction.recipientAddress} | {transaction.meta.height} | {transaction.transaction.deadline} |{message} |{direction}{mosaic} {is_mosaic}'
            short_names[short_name] = transaction
        _short_names = list(short_names.keys())
        _short_names.append('Exit')
        while True:
            questions = [
                inquirer.List(
                    "transaction",
                    message="Select an transaction?",
                    choices=_short_names,
                    carousel=True
                ),
            ]
            answers = inquirer.prompt(questions)
            transaction = answers['transaction']
            if transaction == 'Exit':
                exit(0)
            print(short_names[transaction])
