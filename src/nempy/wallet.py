import configparser
import logging
import os
from typing import Optional

from nempy.config import WALLET_DIR, C
from nempy.profile import Profile, PasswordPolicyError, RepeatPasswordError, ProfileIO, ProfileUI

logger = logging.getLogger(__name__)


class Wallet:

    profiles = dict()
    _profile: Optional[Profile] = None

    def __init__(self,
                 wallet_dir: str = WALLET_DIR):
        self.wallet_dir = wallet_dir
        self.profiles_dir = os.path.join(self.wallet_dir, 'profiles')
        self.accounts_dir = os.path.join(self.wallet_dir, 'accounts')
        self.config_file = os.path.join(wallet_dir, os.path.expanduser('config.ini'))

        os.makedirs(self.wallet_dir, exist_ok=True)
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(self.accounts_dir, exist_ok=True)
        self.init_config_file()

        self.profile_io = ProfileIO(self.config_file, self.profiles_dir)
        self._profile = self.profile_io.profile
        if self._profile is None:
            self.profiles = self.profile_io.load_profiles()
            if not self.profiles:
                print('No profiles have been created')
                answer = input('Create new profile? [Y/n]') or 'y'
                if answer.lower() != 'y':
                    raise SystemExit('There is no way to get account information without an profile')
                self.profile = self.create_profile(is_default=True)

    @property
    def profile(self):
        return self._profile

    @profile.setter
    def profile(self, profile: Profile):
        if profile.name not in self.profiles:
            self.profiles[profile.name] = profile
        self._profile = profile

    def create_profile(self, is_default: bool = False):
        try:
            profile, path = ProfileUI.ui_create_profile(self.profiles_dir, self.config_file)
            profile.write(path)
            print(f'Profile {profile.name} successful created by path: {path}')
            if not is_default:
                is_default = ProfileUI.ui_is_default(profile.name)
            if is_default:
                self.profile_io.set_default_profile(profile)
            return profile
        except (PasswordPolicyError, RepeatPasswordError) as e:
            logger.error(e)
            exit(1)

    def print_profiles(self):
        for profile in self.profile_io.load_profiles().values():
            # add default label
            if profile == self.profile:
                profile = str(profile).replace('|              |', '|  >DEFAULT<   |')
            print(profile)
            print(f'{C.GREY}###################################################################################{C.END}')

    def init_config_file(self):
        if not os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config['profile'] = {}
            config['account'] = {}
            config['profile']['default'] = ''
            config['account']['default'] = ''
            with open(self.config_file, 'w') as configfile:
                config.write(configfile)






