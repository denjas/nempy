import configparser
import logging
import os

import inquirer
from nempy.config import CONFIG_FILE, PROFILES_DIR
from nempy.profile import Profile
from nempy.sym import network

logger = logging.getLogger(__name__)


class Wallet:

    profiles = dict()
    _profile: Profile = None

    def __init__(self):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        self.load_profiles()
        if not self.profiles:
            print('No profiles have been created. To create a profile, run the command `nempy-cli.py profile create`')
            exit(1)
        self.init_default_profile()

    @property
    def profile(self):
        return self._profile

    @profile.setter
    def profile(self, profile: Profile):
        self._profile = profile

    def load_profiles(self):
        profiles_paths = os.listdir(PROFILES_DIR)
        for pp in profiles_paths:
            path = os.path.join(PROFILES_DIR, pp)
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
            self.profile = default_profile
        network.node_selector.network_type = self.profile.network_type

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
        self.profile = profile
        self.profile.input_default_account()





