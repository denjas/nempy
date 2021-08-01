import os
import shutil
import tempfile
from unittest.mock import patch

import bcrypt
import pytest
import stdiomask
from nempy.wallet import Wallet
from nempy.profile import Profile, RepeatPasswordError, PasswordPolicyError
from nempy.sym.constants import NetworkType
from .test_account import test_account


class TestProfile:

    def setup(self):
        self.wallet_path = tempfile.NamedTemporaryFile().name
        self.wallet = Wallet(wallet_dir=self.wallet_path, init_only=True)
        name = 'init'
        self.password = 'pass'
        pass_hash = bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt(12))
        self.profile = Profile(name=name,
                               network_type=NetworkType.TEST_NET,
                               pass_hash=pass_hash,
                               accounts_dir=self.wallet.accounts_dir,
                               config_file=self.wallet.config_file)
        path = os.path.join(self.wallet.profiles_dir, f'{name}.profile')
        self.profile.save_profile(path)
        self.account0, self.account1 = test_account()
        self.account0.encrypt(self.password)
        self.account1.encrypt(self.password)
        self.account0.profile = self.account1.profile = name
        self.account0.write(os.path.join(self.wallet.accounts_dir, self.account0.name + '.account'))
        self.profile.set_default_account(self.account0.name)
        self.account1.write(os.path.join(self.wallet.accounts_dir, self.account1.name + '.account'))

    def teardown(self):
        shutil.rmtree(self.wallet_path)

    def test_create_account(self):
        account_path = os.path.join(self.wallet.accounts_dir, self.account1.name + '.account')
        with patch('nempy.account.Account.init_general_params', return_value=(account_path, self.account1.name, 1, True)), \
             patch('nempy.profile.Profile.check_pass', return_value=self.password), \
             patch('nempy.account.Account.account_by_mnemonic', return_value=self.account1.decrypt(self.password)):
            self.profile.create_account()

    def test_str_repr(self):
        assert [val in str(self.profile) for val in ['Name', 'Network Type', 'Pass Hash']]
        assert 'init' == repr(self.profile)

    def test_create_profile_by_input(self):
        profile_name = 'test'
        password = 'pass'
        with patch.object(Profile, 'input_network_type', return_value=NetworkType.TEST_NET.value), \
             patch.object(Profile, 'input_new_pass', return_value=password):
            with patch('nempy.profile.input', return_value=profile_name):
                created_profile, profile_path = Profile.create_profile_by_input(self.wallet.profiles_dir,
                                                                                self.wallet.config_file)
            loaded_profile = Profile.loaf_profile(profile_path)
            assert created_profile == loaded_profile
            assert loaded_profile.check_pass(password) == password
            assert loaded_profile.check_pass(password + 'random') is None

            with patch.object(stdiomask, 'getpass', return_value=password):
                assert loaded_profile.check_pass() == password
            with patch.object(stdiomask, 'getpass', return_value=password + 'random'):
                assert loaded_profile.check_pass() is None

    def test_inquirer_default_account(self):
        # and test_load_accounts
        with patch('inquirer.prompt', return_value={'name': 'account-1'}):
            self.profile.inquirer_default_account()
            assert self.account1.__dict__ == self.profile.account.__dict__
        real_value = self.profile.load_accounts(self.profile.accounts_dir)
        with patch('nempy.profile.input', return_value='y'), \
             patch('nempy.profile.Profile.create_account', return_value=None), \
             patch('nempy.profile.Profile.load_accounts') as mocked_load_accounts, \
             patch('inquirer.prompt', return_value={'name': 'account-0'}):
            mocked_load_accounts.side_effect = [{}, real_value, real_value]
            self.profile.inquirer_default_account()
        assert self.profile.account.name == 'account-0'
        with patch('nempy.profile.Profile.load_accounts', return_value={}), \
                patch('nempy.profile.input', return_value='n'):
            profile = self.profile.inquirer_default_account()
            assert profile is None

    def test_input_is_default(self):
        with patch('nempy.profile.input', return_value='y'):
            assert True is Profile.input_is_default('init')
        with patch('nempy.profile.input', return_value='n'):
            assert False is Profile.input_is_default('init')

    def test_input_profile_name(self):
        with patch('nempy.profile.input', return_value=''):
            with pytest.raises(ValueError):
                Profile.input_profile_name(self.wallet.profiles_dir)
        with patch('nempy.profile.input', return_value='init'):
            with pytest.raises(ValueError):
                Profile.input_profile_name(self.wallet.profiles_dir)

    def test_input_network_type(self):
        with patch('inquirer.prompt', return_value={'type': 'TEST_NET'}):
            assert NetworkType.TEST_NET == Profile.input_network_type()
        with patch('inquirer.prompt', return_value={'type': 'MAIN_NET'}):
            assert NetworkType.MAIN_NET == Profile.input_network_type()
        with patch('inquirer.prompt', return_value={'type': 'UNKNOWN_NET'}):
            with pytest.raises(TypeError):
                Profile.input_network_type()

    def test_input_new_pass(self):
        with patch('stdiomask.getpass', return_value='pass'):
            with pytest.raises(PasswordPolicyError):
                Profile.input_new_pass(n_attempts=1)

        password = '-P@s5w0rd+1.'
        with patch('stdiomask.getpass', return_value=password):
            assert password == Profile.input_new_pass(n_attempts=1)

    def test_repeat_password(self):
        password = '-P@s5w0rd+1.'
        with patch('stdiomask.getpass', return_value=password):
            assert password == Profile.repeat_password(n_attempts=1, password='-P@s5w0rd+1.')

        with patch('stdiomask.getpass', return_value=password + 'random'):
            with pytest.raises(RepeatPasswordError):
                assert password == Profile.repeat_password(n_attempts=1, password='-P@s5w0rd+1.')





