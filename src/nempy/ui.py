import abc
import binascii
import configparser
import logging
import os
import random
from enum import Enum
from hashlib import blake2b
from typing import Optional, Dict, Tuple, Union, List, Type

import bcrypt
import inquirer
import stdiomask
from bip_utils import Bip39MnemonicGenerator, Bip39Languages
from nempy.config import C
from nempy.sym import network
from nempy.sym.constants import NetworkType, TransactionStatus
from nempy.sym.network import TransactionResponse
from nempy.user_data import AccountData, GenerationType, UserData
from nempy.user_data import ProfileData
from password_strength import PasswordPolicy


logger = logging.getLogger(__name__)


class PasswordPolicyError(Exception):
    pass


class RepeatPasswordError(Exception):
    pass


class UDTypes(Enum):
    PROFILE = 'profile'
    ACCOUNT = 'account'


def print_warning():
    print(f""" {C.ORANGE}
                                !!! Important !!!
 Save the mnemonic, it will be needed to restore access to the wallet in case of password loss
       Where to store can be found here - https://en.bitcoinwiki.org/wiki/Mnemonic_phrase
!!!Do not share your secret key and mnemonic with anyone, it guarantees access to your funds!!!
                                       !!!{C.END}
    """)


class UD:

    cls: Type[UserData]
    type_ud: UDTypes
    ud_dir: str
    config = configparser.ConfigParser()

    def __init__(self, config_file: str, profiles_dir: Optional[str], accounts_dir: Optional[str]):
        self.config_file = config_file
        if self.type_ud == UDTypes.PROFILE:
            self.ud_dir = profiles_dir
            self.cls = ProfileData
        elif self.type_ud == UDTypes.ACCOUNT:
            self.ud_dir = accounts_dir
            self.cls = AccountData

    @property
    def user_data(self) -> Optional[UserData]:
        self.config.read(self.config_file)
        ud_name = self.config[self.type_ud.value]['default']
        uds = self.load_uds()
        ud = uds.get(ud_name)
        return ud

    def load_uds(self) -> Dict[str, UserData]:
        uds = {}
        profiles_paths = os.listdir(self.ud_dir)
        for pp in profiles_paths:
            path = os.path.join(self.ud_dir, pp)
            ud = self.cls.read(path)
            uds[os.path.splitext(pp)[0]] = ud
        return uds

    def set_default_ud(self, ud: UserData):
        self.config.read(self.config_file)
        self.config[self.type_ud.value]['default'] = ud.name
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    def get_default_ud_name(self) -> str:
        self.config.read(self.config_file)
        ud_name = self.config[self.type_ud.value]['default']
        return ud_name


class AccountI(UD):

    def __init__(self, config_file: str, accounts_dir: str):
        self.type_ud = UDTypes.ACCOUNT
        super().__init__(config_file, None, accounts_dir)

    @property
    def data(self) -> Optional[AccountData]:
        return self.user_data

    def load_accounts(self) -> Dict[str, AccountData]:
        return self.load_uds()

    def set_default_account(self, account: AccountData):
        self.set_default_ud(account)


class ProfileI(UD):

    def __init__(self, config_file: str, profiles_dir: str, accounts_dir: str):
        self.type_ud = UDTypes.PROFILE
        self.account_i = AccountI(config_file, accounts_dir)
        super().__init__(config_file, profiles_dir, None)
        accounts_data = self.load_accounts()
        if (self.account.data is None and accounts_data) \
                or (self.account.data is not None and self.account.data.name not in accounts_data):
            account_data = AccountUI.ui_default_account(accounts_data)
            self.set_default_account(account_data)

    @property
    def data(self) -> Optional[ProfileData]:
        return self.user_data

    def load_profiles(self) -> Dict[str, ProfileData]:
        return self.load_uds()

    def set_default_profile(self, profile: ProfileData):
        self.set_default_ud(profile)

    @property
    def account(self) -> AccountI:
        return self.account_i

    def load_accounts(self) -> Dict[str, AccountData]:
        accounts_data = self.account_i.load_accounts()
        accounts_data = {key: account for key, account in accounts_data.items() if account.profile == self.data.name}
        return accounts_data

    def set_default_account(self, account: AccountData):
        self.account_i.set_default_account(account)


class AccountUI(AccountI):

    @staticmethod
    def ui_init_general_params(network_type: NetworkType, accounts_dir: str, is_default: bool = False) -> Tuple[str, str, int, bool]:
        while True:
            name = input('Enter the account name: ')
            if name != '':
                account_path = os.path.join(accounts_dir, name + '.account')
                if os.path.exists(account_path):
                    print('An account with the same name already exists, please select a different name')
                    continue
                break
            print('The name cannot be empty.')
        if not is_default:
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
    def iu_create_account(profile_data: ProfileData,
                          accounts_dir: str,
                          is_default: bool = False,
                          is_import: bool = False) -> Tuple[Optional[AccountData], bool]:
        account_path, name, bip32_coin_id, is_default = AccountUI.ui_init_general_params(profile_data.network_type, accounts_dir, is_default)
        password = ProfileUI.ui_check_pass(profile_data, attempts=3)
        if password is not None:
            if is_import:
                gen_type = AccountUI.ui_generation_type_inquirer()
                if gen_type == GenerationType.MNEMONIC:
                    account_data = AccountUI.ui_account_by_mnemonic(profile_data.network_type, bip32_coin_id, is_import=True)
                elif gen_type == GenerationType.PRIVATE_KEY:
                    raise NotImplementedError(
                        'The functionality of building an account from a private key is not implemented')
                else:
                    raise NotImplementedError(
                        f'The functionality of building an account from a {gen_type.name} key is not implemented')
            else:
                account_data = AccountUI.ui_account_by_mnemonic(profile_data.network_type, bip32_coin_id, is_import=is_import)
            account_data.name = name
            account_data.profile = profile_data.name
            AccountUI.save_and_check(account_data, account_path, password)
            return account_data, is_default
        else:
            return None, is_default

    @staticmethod
    def save_and_check(account_data: AccountData, account_path: str, password: str):
        account_data.encrypt(password).write(account_path)
        print(f'\nAccount created at: {account_path}')
        # checking the ability to read and display information about the account
        account_data = AccountData.read(account_path).decrypt(password)
        print(account_data)
        print_warning()
        return account_data

    @staticmethod
    def ui_default_account(accounts: Dict[str, AccountData]):
        questions = [inquirer.List("name", message="Select default account", choices=accounts.keys(), ), ]
        answers = inquirer.prompt(questions)
        if answers is None:
            exit(1)
        account = accounts[answers['name']]
        return account  # -> set_default_account(account)

    @staticmethod
    def ui_generation_type_inquirer() -> GenerationType:
        questions = [inquirer.List("type", message="Select an import type?", choices=["Mnemonic", "Private Key"], ), ]
        answers = inquirer.prompt(questions)
        import_type = answers['type']
        if import_type == 'Private Key':
            return GenerationType.PRIVATE_KEY
        return GenerationType.MNEMONIC

    @staticmethod
    def ui_history_inquirer(address: str = None, page_size: int = 10):
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

    @staticmethod
    def ui_keyprint_entropy():
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
    def ui_account_inquirer(accounts_names):
        addresses = [account for account in accounts_names]
        questions = [inquirer.List("address", message="Select an import type?", choices=addresses,), ]
        answers = inquirer.prompt(questions)
        account_name = answers['address']
        return account_name

    @classmethod
    def ui_account_by_mnemonic(cls, network_type: NetworkType, bip32_coin_id: int, is_import: bool = False) -> 'AccountData':
        if is_import:
            mnemonic = stdiomask.getpass('Enter a mnemonic passphrase. Words must be separated by spaces: ')
        else:
            random_char_set = cls.ui_keyprint_entropy()
            entropy_bytes_hex = blake2b(random_char_set.encode(), digest_size=32).hexdigest().encode()
            mnemonic = Bip39MnemonicGenerator(Bip39Languages.ENGLISH).FromEntropy(binascii.unhexlify(entropy_bytes_hex))

        accounts = AccountData.accounts_pool_by_mnemonic(network_type, bip32_coin_id, mnemonic)
        account_name = cls.ui_account_inquirer(accounts.keys())
        return accounts[account_name]


class ProfileUI(ProfileI):

    @staticmethod
    def ui_default_profile(profiles: Dict[str, ProfileData]) -> ProfileData:
        names = {profile.name + f' [{profile.network_type.name}]': profile.name for profile in profiles.values()}
        questions = [inquirer.List("name", message="Select default profile", choices=names.keys(),), ]
        answers = inquirer.prompt(questions)
        if answers is None:
            exit(1)
        name = names[answers['name']]
        profile_data = profiles[name]
        network.node_selector.network_type = profile_data.network_type
        return profile_data  # -> set_default_profile(profile)

    @classmethod
    def ui_create_profile(cls, profiles_dir: str, config_file: str) -> Tuple[ProfileData, str]:
        name, path = cls.ui_profile_name(profiles_dir)
        network_type = cls.ui_network_type()
        new_pass = cls.ui_new_pass(10)
        pass_hash = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt(12))
        accounts_dir = os.path.join(os.path.dirname(profiles_dir), 'accounts')
        profile = ProfileData(name=name,
                              network_type=network_type,
                              pass_hash=pass_hash,
                              accounts_dir=accounts_dir,
                              config_file=config_file)
        return profile, path

    @staticmethod
    def ui_check_pass(profile_data: ProfileData, attempts: int = 1) -> Optional[str]:
        """
        Verifies the password from the profile
        :return: password or None if password is failed
        """
        for i in range(attempts):
            password = stdiomask.getpass(f'({attempts - i}) Enter your `{profile_data.name} [{profile_data.network_type.name}]` profile password: ')
            if bcrypt.checkpw(password.encode('utf-8'), profile_data.pass_hash):
                return password
            if i != attempts - 1:
                print(f'Incorrect password. Try again)')
        logger.error('Incorrect password')
        return None

    @staticmethod
    def ui_is_default(name):
        answer = input(f'Set `{name}` profile as default? [Y/n]: ') or 'y'
        if answer.lower() == 'y':
            return True
        return False

    @staticmethod
    def ui_profile_name(profiles_dir, attempts: int = 5):
        name = None
        for i in range(attempts):
            name = input(f'({attempts - i}) Enter profile name: ')
            if '.' in name:
                print('Dot is not a valid character for filename')
                continue
            path = os.path.join(profiles_dir, f'{name}.profile')
            if name == '':
                print('The name cannot be empty')
            elif os.path.exists(path):
                print(f'A profile named `{name}` already exists')
            else:
                return name, path
        raise ValueError(f'Incorrect name for new profile - `{name}`')

    @staticmethod
    def ui_network_type() -> NetworkType:
        questions = [inquirer.List("type", message="Select an network type?", choices=["TEST_NET", "MAIN_NET"],), ]
        answers = inquirer.prompt(questions)
        network_type = answers['type']
        if network_type == 'MAIN_NET':
            network_type = NetworkType.MAIN_NET
        elif network_type == 'TEST_NET':
            network_type = NetworkType.TEST_NET
        else:
            raise TypeError('Unknown network type')
        return network_type

    @staticmethod
    def ui_new_pass(n_attempts: int):
        policy = PasswordPolicy.from_names(
            length=8,  # min length: 8
            uppercase=1,  # need min. 1 uppercase letters
            numbers=2,  # need min. 2 digits
            special=1,  # need min. 1 special characters
            nonletters=2,  # need min. 2 non-letter characters (digits, specials, anything)
        )
        new_password = None
        not_in_policies = True
        for i in range(n_attempts):
            new_password = stdiomask.getpass(f'Enter your new account password {policy.test("")}: ')
            not_in_policies = policy.test(new_password)
            if not_in_policies:
                print(not_in_policies)
            else:
                break
        if not_in_policies:
            raise PasswordPolicyError(not_in_policies)
        return ProfileUI.ui_repeat_password(n_attempts, new_password)

    @staticmethod
    def ui_repeat_password(n_attempts: int, password):
        for i in range(n_attempts):
            repeat_password = stdiomask.getpass(f'Repeat password for confirmation: ')
            if repeat_password != password:
                print(f'Try again, attempts left {n_attempts - i}')
            else:
                return password
        raise RepeatPasswordError('Failed to confirm password on re-entry')
