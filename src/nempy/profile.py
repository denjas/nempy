import configparser
import logging
import os
import pickle
from typing import Optional

import bcrypt
import inquirer
import stdiomask
from nempy.account import Account
from nempy.config import CONFIG_FILE, PROFILES_DIR, ACCOUNTS_DIR, C
from nempy.sym.constants import NetworkType
from password_strength import PasswordPolicy
from pydantic import BaseModel
from tabulate import tabulate

logger = logging.getLogger(__name__)


class Profile(BaseModel):
    name: str
    network_type: NetworkType
    pass_hash: bytes

    # def __init__(self, profile: dict = None):
    #     os.makedirs(PROFILES_DIR, exist_ok=True)
    #     if profile is not None:
    #         [setattr(self, key, value) for key, value in profile.items()]

    def __str__(self):
        prepare = [[key.replace('_', ' ').title(), value]
                   for key, value in self.__dict__.items() if key not in ['network_type', 'pass_hash']]
        prepare.append(['Network Type', self.network_type.name])
        prepare.append(['Pass Hash', C.OKBLUE + '*' * len(self.pass_hash) + C.END ])
        profile = f'Profile - {self.name}'
        indent = (len(self.pass_hash) - len(profile)) // 2
        profile = C.INVERT + ' ' * indent + profile + ' ' * indent + C.END

        table = tabulate(prepare, headers=['', f'{profile}'], tablefmt='grid')
        return table

    def __repr__(self):
        return self.name

    @property
    def account(self) -> Optional[Account]:
        """
        Get the default account
        :return: Account
        """
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        account_name = config['account']['default']
        accounts = self.load_accounts()
        return accounts.get(account_name)

    def load_accounts(self) -> dict[str: Account]:
        accounts = {}
        accounts_paths = os.listdir(ACCOUNTS_DIR)
        for account_path in accounts_paths:
            path = os.path.join(ACCOUNTS_DIR, account_path)
            account = Account.read(path)
            # select all accounts of the current profile
            if account.profile == self.name:
                accounts[os.path.splitext(account_path)[0]] = account
        return accounts

    def input_default_account(self):
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
        Profile.set_default_account(account.name)

    @staticmethod
    def set_default_account(name: str):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        config['account']['default'] = name
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

    def check_pass(self, password: str = None, attempts: int = 1) -> Optional[str]:
        """
        Verifies the password from the profile
        :param password: password - if specified, then immediately check and result
        :param attempts: if no password is specified, you are prompted to input with the number of attempts
        :return: password or None if password is failed
        """
        if password is not None:
            if bcrypt.checkpw(password.encode('utf-8'), self.pass_hash):
                return password
            else:
                logger.error('Incorrect password')
                return None

        for i in range(attempts):
            password = stdiomask.getpass(f'Enter your `{self.name} [{self.network_type.name}]` profile password: ')
            if bcrypt.checkpw(password.encode('utf-8'), self.pass_hash):
                return password
            print(f'Incorrect password. Try again ({attempts - 1 - i})')
        logger.error('Incorrect password')
        return None

    @staticmethod
    def create_profile() -> tuple['Profile', bool]:
        name, path = Profile.input_profile_name()
        network_type = Profile.input_network_type()
        new_pass = Profile.input_new_pass(10)
        if new_pass is None:
            exit(1)
        pass_hash = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt(12))
        is_default = False
        answer = input(f'Set `{name}` profile as default? Y/n: ') or 'y'
        if answer.lower() == 'y':
            is_default = True
        profile = Profile(name=name, network_type=network_type, pass_hash=pass_hash)
        profile.save_profile(path)
        print(f'Profile {profile.name} successful created by path: {path}')
        print(profile)
        return profile, is_default

    @staticmethod
    def input_profile_name():
        while True:
            name = input('Enter profile name: ')
            path = os.path.join(PROFILES_DIR, f'{name}.profile')
            if name == '':
                print('The name cannot be empty')
            elif os.path.exists(path):
                print(f'A profile named `{name}` already exists')
            else:
                return name, path

    @staticmethod
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

    @staticmethod
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
            repeat_password = stdiomask.getpass(f'Repeat password for confirmation: ')
            if repeat_password != new_password:
                print(f'Try again, attempts left {n_attempts - i}')
            else:
                return new_password
        return None

    def save_profile(self, path):
        pickled = self.serialize()
        with open(path, 'wb') as opened_file:
            opened_file.write(pickled)

    @staticmethod
    def loaf_profile(path) -> 'Profile':
        with open(path, 'rb') as opened_file:
            return Profile.deserialize(opened_file.read())

    def serialize(self):
        return pickle.dumps(self.__dict__)

    @staticmethod
    def deserialize(data) -> 'Profile':
        des_date = pickle.loads(data)
        return Profile(**des_date)
