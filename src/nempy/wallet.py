import configparser
import logging
import os
from typing import Optional

import inquirer
from nempy.config import WALLET_DIR, C
from nempy.profile import Profile, PasswordPolicyError, RepeatPasswordError
from nempy.sym import network

logger = logging.getLogger(__name__)


class Wallet:

    profiles = dict()
    _profile: Optional[Profile] = None

    def __init__(self,
                 wallet_dir: str = WALLET_DIR,
                 init_only: bool = False):
        self.wallet_dir = wallet_dir
        self.profiles_dir = os.path.join(self.wallet_dir, 'profiles')
        self.accounts_dir = os.path.join(self.wallet_dir, 'accounts')
        self.config_file = os.path.join(wallet_dir, os.path.expanduser('config.ini'))

        os.makedirs(self.wallet_dir, exist_ok=True)
        os.makedirs(self.profiles_dir, exist_ok=True)
        os.makedirs(self.accounts_dir, exist_ok=True)

        self.init_config_file()
        if not init_only:
            self.load_profiles()
            if not self.profiles:
                print('No profiles have been created')
                answer = input('Create new profile? [Y/n]') or 'y'
                if answer.lower() != 'y':
                    return
                self.create_profile(is_default=True)
            config = configparser.ConfigParser()
            config.read(self.config_file)
            default_profile = self.profiles.get(config['profile']['default'])
            if default_profile is None:
                self.profile = self.inquirer_default_profile()
            else:
                self.profile = default_profile

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
            profile, _ = Profile.create_profile_by_input(self.profiles_dir, self.config_file)
            if not is_default:
                is_default = Profile.input_is_default(profile.name)
            if is_default:
                self.set_default_profile(profile)
            return profile
        except (PasswordPolicyError, RepeatPasswordError) as e:
            logger.error(e)
            exit(1)

    def load_profiles(self):
        profiles_paths = os.listdir(self.profiles_dir)
        for pp in profiles_paths:
            path = os.path.join(self.profiles_dir, pp)
            profile = Profile.loaf_profile(path)
            self.profiles[os.path.splitext(pp)[0]] = profile

    def print_profiles(self):
        for profile in self.profiles.values():
            print(profile)
            print(f'{C.GREY}###################################################################################{C.END}')

    def inquirer_default_profile(self):
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
        profile = self.profiles[name]
        self.set_default_profile(profile)
        network.node_selector.network_type = self.profile.network_type
        return profile

    def set_default_profile(self, profile: Profile):
        config = configparser.ConfigParser()
        config.read(self.config_file)
        self.profile = profile
        config['profile']['default'] = self.profile.name
        with open(self.config_file, 'w') as configfile:
            config.write(configfile)

    def init_config_file(self):
        if not os.path.exists(self.config_file):
            config = configparser.ConfigParser()
            config['profile'] = {}
            config['account'] = {}
            config['profile']['default'] = ''
            config['account']['default'] = ''
            with open(self.config_file, 'w') as configfile:
                config.write(configfile)






