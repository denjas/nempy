import configparser
import logging
import os
import pickle

import bcrypt
import inquirer
import stdiomask
from nempy.account import Account
from nempy.config import CONFIG_FILE, PROFILES_FILES, DEFAULT_ACCOUNTS_DIR, C
from nempy.sym.constants import NetworkType
from password_strength import PasswordPolicy
from tabulate import tabulate


logger = logging.getLogger(__name__)


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
        profile = f'Profile - {self.name}'
        indent = (len(self.pass_hash) - len(profile)) // 2
        profile = C.INVERT + ' ' * indent + profile + ' ' * indent + C.END
        table = tabulate(prepare, headers=['', f'{profile}'], tablefmt='grid')
        return table

    def __repr__(self):
        return self.name

    @property
    def account(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        account_name = config['account']['default']
        accounts = self.load_accounts()
        return accounts.get(account_name)

    def load_accounts(self) -> dict:
        accounts = {}
        accounts_paths = os.listdir(DEFAULT_ACCOUNTS_DIR)
        for account_path in accounts_paths:
            path = os.path.join(DEFAULT_ACCOUNTS_DIR, account_path)
            account = Account.read_account(path)
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
    def set_default_account(name):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        config['account']['default'] = name
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

    def check_pass(self, password: str = None, attempts: int = 1):
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

    def create_profile(self):
        self.name, path = Profile.input_profile_name()
        self.network_type = Profile.input_network_type()
        new_pass = Profile.input_new_pass(10)
        if new_pass is None:
            exit(1)
        self.pass_hash = bcrypt.hashpw(new_pass.encode('utf-8'), bcrypt.gensalt(12))
        self.save_profile(path)
        print(f'Profile {self.name} successful created by path: {path}')
        print(self)
        return path

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
