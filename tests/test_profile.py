import os
import shutil
import tempfile
from unittest.mock import patch

import stdiomask
from nempy.profile import Profile
from nempy.sym.constants import NetworkType


class TestProfile:

    def setup(self):
        self.profile_path = tempfile.NamedTemporaryFile().name
        os.makedirs(self.profile_path)

    def teardown(self):
        shutil.rmtree(self.profile_path)

    def test_create_profile_by_input(self):
        profile_name = 'test'
        password = 'pass'
        with patch.object(Profile, 'input_network_type', return_value=NetworkType.TEST_NET.value), \
             patch.object(Profile, 'input_new_pass', return_value=password):
            with patch('nempy.profile.input', return_value=profile_name):
                created_profile, profile_path = Profile.create_profile_by_input(self.profile_path)
            loaded_profile = Profile.loaf_profile(profile_path)
            assert created_profile == loaded_profile
            assert [val in str(loaded_profile) for val in ['Name', 'Network Type', 'Pass Hash']]
            assert loaded_profile.check_pass(password) == password
            assert loaded_profile.check_pass(password + 'random') is None

            with patch.object(stdiomask, 'getpass', return_value=password):
                assert loaded_profile.check_pass() == password
            with patch.object(stdiomask, 'getpass', return_value=password + 'random'):
                assert loaded_profile.check_pass() is None


