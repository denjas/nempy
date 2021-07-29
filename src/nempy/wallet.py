import configparser
import logging
import os

import inquirer
from nempy.config import CONFIG_FILE, PROFILES_DIR, WALLET_DIR, C, ACCOUNTS_DIR
from nempy.profile import Profile
from nempy.sym import network

logger = logging.getLogger(__name__)


class Wallet:

    profiles = dict()
    _profile: Profile = None

    def __init__(self, skip_checks: bool = False):
        os.makedirs(WALLET_DIR, exist_ok=True)
        os.makedirs(PROFILES_DIR, exist_ok=True)
        os.makedirs(ACCOUNTS_DIR, exist_ok=True)
        Wallet.init_config_file()
        if not skip_checks:
            self.load_profiles()
            if not self.profiles:
                print('No profiles have been created. To create a profile, run the command `nempy-cli.py profile create`')
                exit(1)
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
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

    def load_profiles(self):
        profiles_paths = os.listdir(PROFILES_DIR)
        for pp in profiles_paths:
            path = os.path.join(PROFILES_DIR, pp)
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
        config.read(CONFIG_FILE)
        self.profile = profile
        config['profile']['default'] = self.profile.name
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)

    @staticmethod
    def init_config_file():
        if not os.path.exists(CONFIG_FILE):
            config = configparser.ConfigParser()
            config['profile'] = {}
            config['account'] = {}
            config['profile']['default'] = ''
            config['account']['default'] = ''
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)






