import os
import tempfile
from unittest.mock import patch, PropertyMock
import shutil

import stdiomask
from nempy.profile import Profile
from nempy.config import PROFILES_DIR
from sym.constants import NetworkType


class TestProfile:

    def setup(self):
        self.profile_path = tempfile.NamedTemporaryFile().name
        os.makedirs(self.profile_path)

    def teardown(self):
        shutil.rmtree(self.profile_path)

    def test_create_profile_by_input(self):
        profile_name = 'test'
        password = 'pass'
        profile_path = os.path.join(self.profile_path, f'{profile_name}.profile')
        with patch.object(Profile, 'input_profile_name', return_value=tuple([profile_name, profile_path])), \
             patch.object(Profile, 'input_network_type', return_value=NetworkType.TEST_NET.value), \
             patch.object(Profile, 'input_new_pass', return_value=password):
            created_profile = Profile.create_profile_by_input()
            loaded_profile = Profile.loaf_profile(profile_path)
            assert created_profile == loaded_profile
            assert [val in str(loaded_profile) for val in ['Name', 'Network Type', 'Pass Hash']]
            assert loaded_profile.check_pass(password) == password
            assert loaded_profile.check_pass(password + 'random') is None

            with patch.object(stdiomask, 'getpass', return_value=password):
                assert loaded_profile.check_pass() == password
            with patch.object(stdiomask, 'getpass', return_value=password + 'random'):
                assert loaded_profile.check_pass() is None


