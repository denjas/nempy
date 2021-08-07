import copy
import os
import shutil
import tempfile
from unittest.mock import patch

import pytest
import ui
from nempy.wallet import Wallet
from nempy.sym.constants import NetworkType
from nempy.ui import PasswordPolicyError, ProfileUI

from .test_user_data import TestProfileData, TestAccountData


class TestWallet:

    def setup(self):
        self.wallet_dir = tempfile.TemporaryDirectory()
        wallet = Wallet(self.wallet_dir.name, init_only=True)

        self.profile_data = TestProfileData().setup()

        self.account_data = TestAccountData().setup()
        self.account_data.name = 'test'
        self.account_data.profile = self.profile_data.name

        with patch('nempy.wallet.Wallet.create_profile', return_value=self.profile_data), \
             patch('nempy.ui.AccountUI.iu_create_account', return_value=(self.account_data, True)):
            with patch('nempy.wallet.input', return_value='n'):
                with pytest.raises(SystemExit):
                    Wallet(self.wallet_dir.name)

            with patch('nempy.wallet.input', side_effect=['y', 'n']):
                with pytest.raises(SystemExit):
                    Wallet(self.wallet_dir.name)

            with patch('nempy.wallet.input', side_effect=['y', 'y']):
                profile = ui.ProfileI(wallet.config_file, wallet.profiles_dir, wallet.accounts_dir)
                self.profile_data.write(os.path.join(wallet.profiles_dir, self.profile_data.name + '.profile'))
                profile.set_default_profile(self.profile_data)

                self.wallet = Wallet(self.wallet_dir.name)
                self.account_data.encrypt('pass').write(os.path.join(wallet.accounts_dir, self.account_data.name + '.account'))
                pass

    def teardown(self):
        self.wallet_dir.cleanup()

    def test_init(self):
        assert self.wallet.profile.data == self.profile_data
        assert self.wallet.profile.account.data == self.account_data

    def test_profile(self):
        assert self.wallet.profile.data == self.profile_data
        self.wallet.profile = ui.ProfileI(self.wallet.config_file, self.wallet.profiles_dir, self.wallet.accounts_dir)

    def test_print_profiles(self):
        self.wallet.print_profiles(self.profile_data.name)
        
    def test_init_config_file(self):
        assert os.path.exists(self.wallet.config_file) is True

    def test_create_profile(self):
        with patch('nempy.ui.ProfileUI.ui_create_profile', return_value=(self.wallet.profile.data, 'path')), \
             patch('nempy.ui.ProfileUI.ui_is_default', return_value=True):
            self.wallet.create_profile()

        with patch('nempy.ui.ProfileUI.ui_create_profile') as mocked_create_profile_by_input:
            mocked_create_profile_by_input.side_effect = PasswordPolicyError
            with pytest.raises(SystemExit):
                self.wallet.create_profile()






