import configparser
import logging
import os
from typing import Optional

from nempy.config import WALLET_DIR, C
from nempy.ui import PasswordPolicyError, RepeatPasswordError, ProfileUI, AccountUI
from nempy.user_data import ProfileData

logger = logging.getLogger(__name__)


class Wallet:

    def __init__(self, wallet_dir: str = WALLET_DIR, init_only=False):
        self.wallet_dir = wallet_dir
        self.profiles_dir = os.path.join(self.wallet_dir, 'profiles')
        self.accounts_dir = os.path.join(self.wallet_dir, 'accounts')
        self.config_file = os.path.join(wallet_dir, os.path.expanduser('config.ini'))

        os.makedirs(self.wallet_dir, exist_ok=True)
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(self.accounts_dir, exist_ok=True)
        self.init_config_file()
        if init_only:
            return
        self._profile = ProfileUI(self.config_file, self.profiles_dir, self.accounts_dir)

        if self.profile.data is None:
            profiles_data = self.profile.load_profiles()
            if not profiles_data:
                print('No profiles have been created')
                answer = input('Create new profile? [Y/n]') or 'y'
                if answer.lower() != 'y':
                    raise SystemExit('There is no way to get account information without an profile')
                profile_data = self.create_profile(is_default=True)
                print(profile_data)

        if self.profile.account.data is None:
            accounts_data = self.profile.load_accounts()
            if not accounts_data:
                print('No account have been created')
                answer = input('Create new account? [Y/n]') or 'y'
                if answer.lower() != 'y':
                    raise SystemExit('There is no way to continue working without an account')
                account_data, _ = AccountUI.iu_create_account(self.profile.data, self.accounts_dir, is_default=True)
                self.profile.set_default_account(account_data)

    @property
    def profile(self) -> ProfileUI:
        if self._profile.data is None and (profiles := self._profile.load_profiles()):
            profile_data = ProfileUI.ui_default_profile(profiles)
            self._profile.set_default_profile(profile_data)
        return self._profile

    @profile.setter
    def profile(self, profile: ProfileUI):
        self._profile = profile

    def create_profile(self, is_default: bool = False) -> ProfileData:
        try:
            profile_data, path = ProfileUI.ui_create_profile(self.profiles_dir, self.config_file)
            profile_data.write(path)
            print(f'Profile {profile_data.name} successful created by path: {path}')
            if not is_default:
                is_default = ProfileUI.ui_is_default(profile_data.name)
            if is_default:
                self.profile.set_default_profile(profile_data)
            return profile_data
        except (PasswordPolicyError, RepeatPasswordError) as e:
            logger.error(e)
            exit(1)

    def print_profiles(self, name):
        for profile_data in self.profile.load_profiles().values():
            # skip printing if name is specified
            if name != profile_data.name and name:
                continue
            # add default label
            if self.profile.data is not None and profile_data == self.profile.data:
                profile_data = str(profile_data).replace('|              |', f'|  >{C.OKGREEN}DEFAULT{C.END}<   |', 1)
            print(profile_data)
            print(f'{C.GREY}#################################################################################{C.END}')

    def init_config_file(self):
        if not os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config['profile'] = {}
            config['account'] = {}
            config['profile']['default'] = ''
            config['account']['default'] = ''
            with open(self.config_file, 'w') as configfile:
                config.write(configfile)






