import copy
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest
from nempy.wallet import Wallet
from nempy.sym.constants import NetworkType
from nempy.ui import PasswordPolicyError


class TestWallet:

    def setup(self):
        self.wallet_dir = tempfile.TemporaryDirectory()
        profile_name = 'test'
        password = 'pass'
        Wallet(self.wallet_dir.name, init_only=True)
        with patch('nempy.profile.input', return_value=profile_name), \
                patch('nempy.profile.Profile.input_network_type', return_value=NetworkType.TEST_NET.value), \
                patch('nempy.profile.Profile.input_new_pass', return_value=password), \
                patch('inquirer.prompt', return_value={'name': 'test [TEST_NET]'}):
            with patch('nempy.wallet.input', return_value='y'):
                wallet = Wallet(self.wallet_dir.name)
                assert wallet.profile is not None
                wallet.print_profiles()
                self.wallet = wallet

    def teardown(self):
        self.wallet_dir.cleanup()

    def test_inquirer_default_profile(self):
        with patch('inquirer.prompt', return_value={'name': 'test [TEST_NET]'}):
            profile = self.wallet.profile
            _profile = self.wallet.inquirer_default_profile()
            assert profile == _profile
            _profile = copy.deepcopy(_profile)
            _profile.name = 'test1'
            assert profile != _profile

    def test_load_profiles(self):
        profiles = self.wallet.load_profiles()
        assert len(profiles) == 1

    def test_create_profile(self):
        with patch('nempy.profile.Profile.create_profile_by_input', return_value=(self.wallet.profile, 'path')), \
             patch('nempy.profile.Profile.input_is_default', return_value=True):
            self.wallet.create_profile()

        with patch('nempy.profile.Profile.create_profile_by_input') as mocked_create_profile_by_input:
            mocked_create_profile_by_input.side_effect = PasswordPolicyError
            with pytest.raises(SystemExit):
                self.wallet.create_profile()






