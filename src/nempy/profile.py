import configparser
import logging
import os
import pickle
from enum import Enum
from typing import Optional, Dict, Tuple, Any, Union

import bcrypt
import inquirer
import stdiomask
from nempy.account import Account, GenerationType
from nempy.config import C
from nempy.sym.constants import NetworkType
from password_strength import PasswordPolicy
from pydantic import BaseModel
from nempy.sym import network
from tabulate import tabulate

logger = logging.getLogger(__name__)


class PasswordPolicyError(Exception):
    pass


class RepeatPasswordError(Exception):
    pass


class Profile(BaseModel):
    name: str
    network_type: NetworkType
    pass_hash: bytes

    def __eq__(self, other: 'Profile'):
        if other.dict() == self.dict():
            return True
        return False

    def __str__(self):
        prepare = [[key.replace('_', ' ').title(), value]
                   for key, value in self.dict().items() if key not in ['network_type', 'pass_hash']]
        prepare.append(['Network Type', self.network_type.name])
        prepare.append(['Pass Hash', C.OKBLUE + '*' * len(self.pass_hash) + C.END])
        profile = f'Profile - {self.name}'
        indent = (len(self.pass_hash) - len(profile)) // 2
        profile = C.INVERT + ' ' * indent + profile + ' ' * indent + C.END

        table = tabulate(prepare, headers=['', f'{profile}'], tablefmt='grid')
        return table

    def __repr__(self, ):
        return self.name

    @classmethod
    def read(cls, path) -> 'Profile':
        with open(path, 'rb') as opened_file:
            deserialized = cls._deserialize(opened_file.read())
            return deserialized

    def write(self, path):
        pickled = self._serialize()
        with open(path, 'wb') as opened_file:
            opened_file.write(pickled)

    def _serialize(self):
        return pickle.dumps(self.dict())

    @classmethod
    def _deserialize(cls, data) -> 'Profile':
        des_date = pickle.loads(data)
        profile = cls(**des_date)
        return profile

    def check_pass(self, password: str) -> bool:
        """
        Verifies the password from the profile
        :param password: password - if specified, then immediately check and result
        :return: True if password confirmed or False if password is failed
        """
        if password is not None:
            if bcrypt.checkpw(password.encode('utf-8'), self.pass_hash):
                return True
            else:
                logger.error('Incorrect password')
                return False


# -----------------------------------------------------------------------------------------------------------

class UDTypes(Enum):
    PROFILE = 'profile'
    ACCOUNT = 'account'


class UD:

    type_ud: UDTypes
    ud_dir: str
    config = configparser.ConfigParser()

    def __init__(self, config_file: str, profiles_dir: Optional[str], accounts_dir: Optional[str]):
        self.config_file = config_file
        # self.profiles_dir = profiles_dir
        if self.type_ud == UDTypes.PROFILE:
            self.ud_dir = profiles_dir
        elif self.type_ud == UDTypes.ACCOUNT:
            self.ud_dir = accounts_dir

    @property
    def user_data(self) -> Union[Profile, Account]:
        self.config.read(self.config_file)
        ud_name = self.config[self.type_ud.value]['default']
        uds = self.load_uds()
        ud = uds.get(ud_name)
        return ud

    def load_uds(self) -> Union[Dict[str, Profile], Dict[str, Account]]:
        uds = {}
        profiles_paths = os.listdir(self.ud_dir)
        for pp in profiles_paths:
            path = os.path.join(self.ud_dir, pp)
            ud = Profile.read(path)
            uds[os.path.splitext(pp)[0]] = ud
        return uds

    def set_default_ud(self, ud: Union[Account, Profile]):
        self.config.read(self.config_file)
        self.config[self.type_ud.value]['default'] = ud.name
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)


class ProfileIO(UD):

    def __init__(self, config_file: str, profiles_dir: str):
        self.type_ud = UDTypes.PROFILE
        super().__init__(config_file, profiles_dir, None)

    @property
    def profile(self) -> Profile:
        return self.user_data

    def load_profiles(self) -> Dict[str, Profile]:
        return self.load_uds()

    def set_default_profile(self, profile: Profile):
        self.set_default_ud(profile)


class AccountIO(UD):

    def __init__(self, config_file: str, accounts_dir: str):
        self.type_ud = UDTypes.ACCOUNT
        super().__init__(config_file, None, accounts_dir)

    @property
    def account(self) -> Account:
        return self.user_data

    def load_account(self) -> Dict[str, Account]:
        return self.load_uds()

    def set_default_profile(self, account: Account):
        self.set_default_ud(account)


class AccountUI:
    # ACCOUNT -------------------------------------------------------------------------------------------

    @staticmethod
    def ui_init_general_params(network_type: NetworkType, accounts_dir: str) -> Tuple[str, str, int, bool]:
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
    def iu_create_account(profile, accounts_dir, is_import: bool = False):
        account_path, name, bip32_coin_id, is_default = AccountUI.ui_init_general_params(profile.network_type, accounts_dir)
        password = ProfileUI.ui_check_pass(name, profile.network_type, profile.pass_hash, attempts=3)
        if password is not None:
            if is_import:
                gen_type = Account.get_generation_type()
                if gen_type == GenerationType.MNEMONIC:
                    account = Account.account_by_mnemonic(profile.network_type, bip32_coin_id, is_import=True)
                elif gen_type == GenerationType.PRIVATE_KEY:
                    raise NotImplementedError(
                        'The functionality of building an account from a private key is not implemented')
                else:
                    raise NotImplementedError(
                        f'The functionality of building an account from a {gen_type.name} key is not implemented')
            else:
                account = Account.account_by_mnemonic(profile.network_type, bip32_coin_id, is_import=is_import)
            account.name = name
            account.profile = profile.name
            account.account_creation(account_path, password)
            return account, is_default

    @staticmethod
    def ui_default_account(accounts: Dict[str, Account]):
        questions = [inquirer.List("name", message="Select default account", choices=accounts.keys(), ), ]
        answers = inquirer.prompt(questions)
        if answers is None:
            exit(1)
        account = accounts[answers['name']]
        return account  # -> set_default_account(account)


class ProfileUI:
    # PROFILE -------------------------------------------------------------------------------------------

    @staticmethod
    def ui_default_profile(profiles: Dict[str, Profile]) -> Profile:
        names = {profile.name + f' [{profile.network_type.name}]': profile.name for profile in profiles.values()}
        questions = [inquirer.List("name", message="Select default profile", choices=names.keys(),), ]
        answers = inquirer.prompt(questions)
        if answers is None:
            exit(1)
        name = names[answers['name']]
        profile = profiles[name]
        network.node_selector.network_type = profile.network_type
        return profile  # -> set_default_profile(profile)

    @classmethod
    def ui_create_profile(cls, profiles_dir: str, config_file: str) -> Tuple['Profile', str]:
        name, path = cls.ui_profile_name(profiles_dir)
        network_type = cls.ui_network_type()
        new_pass = cls.ui_new_pass(10)
        pass_hash = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt(12))
        accounts_dir = os.path.join(os.path.dirname(profiles_dir), 'accounts')
        profile = Profile(name=name,
                          network_type=network_type,
                          pass_hash=pass_hash,
                          accounts_dir=accounts_dir,
                          config_file=config_file)
        return profile, path

    @staticmethod
    def ui_check_pass(name: str, network_type: NetworkType, pass_hash: bytes, attempts: int = 1) -> Optional[str]:
        """
        Verifies the password from the profile
        :param password: password - if specified, then immediately check and result
        :param attempts: if no password is specified, you are prompted to input with the number of attempts
        :return: password or None if password is failed
        """
        for i in range(attempts):
            password = stdiomask.getpass(f'Enter your `{name} [{network_type.name}]` profile password: ')
            if bcrypt.checkpw(password.encode('utf-8'), pass_hash):
                return password
            print(f'Incorrect password. Try again ({attempts - 1 - i})')
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
