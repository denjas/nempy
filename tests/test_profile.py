import os
import shutil
import tempfile
from unittest.mock import patch

import bcrypt
import pytest
import stdiomask
from nempy.user_data import GenerationType
from nempy.wallet import Wallet
from nempy.ui import Profile, RepeatPasswordError, PasswordPolicyError
from nempy.sym.constants import NetworkType
from .test_account import test_account


class TestProfile:

    def setup(self):
        self.profile_context = tempfile.TemporaryDirectory()
        self.wallet = Wallet(self.profile_context.name, init_only=True)
        self.password = 'pass'
        self.params = {
            'name': 'profile-name',
            'network_type': NetworkType.TEST_NET,
            'pass_hash': bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt(12)),
            'accounts_dir': self.wallet.accounts_dir,
            'config_file': self.wallet.config_file
        }
        self.profile_path = os.path.join(self.wallet.profiles_dir, f'{self.params["name"]}.profile')
        with patch('nempy.profile.input', return_value='n'):
            self.profile = Profile(**self.params)
            self.profile.save_profile(self.profile_path)
        self.account0, self.account1 = test_account()
        self.account0.encrypt(self.password)
        self.account1.encrypt(self.password)
        self.account0.profile = self.account1.profile = self.profile.name
        self.account0.write(os.path.join(self.wallet.accounts_dir, self.account0.name + '.account'))
        self.profile.set_default_account(self.account0)
        self.account1.write(os.path.join(self.wallet.accounts_dir, self.account1.name + '.account'))

    def teardown(self):
        self.profile_context.cleanup()

    def test_init(self):
        real_value = self.profile.load_accounts()
        with patch('nempy.profile.Profile.load_accounts', side_effect=[{}, {}]):
            profile = Profile(**self.params)
            assert profile == self.profile

        with patch('nempy.profile.Profile.inquirer_default_account', return_value=None), \
             patch('nempy.profile.Profile.load_accounts', side_effect=[{}, real_value]):
            profile = Profile(**self.params)
            assert profile == self.profile

        account = self.profile.account
        self.profile.account_ = None
        assert account == self.profile.account

    def test_load_profile(self):
        with patch('nempy.profile.input', return_value='n'):
            loaded = Profile.loaf_profile(self.profile_path)
            assert loaded == self.profile

    def test_check_pass(self):
        assert self.profile.check_pass(self.password) == self.password
        assert self.profile.check_pass(self.password+'random') is None
        with patch.object(stdiomask, 'getpass', return_value=self.password):
            assert self.profile.check_pass() == self.password
        with patch.object(stdiomask, 'getpass', return_value=self.password + 'random'):
            assert self.profile.check_pass() is None
            
    def test_serialize_deserialize(self):
        data = self.profile.serialize()
        assert Profile.deserialize(data) == self.profile

    def test_set_default_account(self):
        assert self.profile.account == self.account0
        self.profile.set_default_account(self.account1)
        assert self.profile.account == self.account1

    def test_str_repr(self):
        assert [val in str(self.profile) for val in ['Name', 'Network Type', 'Pass Hash']]
        assert self.profile.name == repr(self.profile)

    def test_input_is_default(self):
        with patch('nempy.profile.input', return_value='y'):
            assert True is Profile.input_is_default(self.profile.name)
        with patch('nempy.profile.input', return_value='n'):
            assert False is Profile.input_is_default(self.profile.name)

    def test_input_profile_name(self):
        with patch('nempy.profile.input', return_value=''):
            with pytest.raises(ValueError):
                Profile.input_profile_name(self.wallet.profiles_dir)
        with patch('nempy.profile.input', return_value=self.profile.name):
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

    def test_create_import_account(self):
        account_path = os.path.join(self.wallet.accounts_dir, self.account1.name + '.account')
        # create
        with patch('nempy.account.Account.init_general_params', return_value=(account_path, self.account1.name, 1, True)), \
             patch('nempy.profile.Profile.check_pass', return_value=self.password), \
             patch('nempy.account.Account.account_by_mnemonic', return_value=self.account1.decrypt(self.password)):
            account1, _ = self.profile.create_account()
        # import
        with patch('nempy.account.Account.init_general_params', return_value=(account_path, self.account1.name, 1, True)), \
             patch('nempy.profile.Profile.check_pass', return_value=self.password), \
             patch('nempy.account.Account.get_generation_type', return_value=GenerationType.MNEMONIC), \
             patch('stdiomask.getpass', return_value=self.account1.decrypt(self.password).mnemonic), \
             patch('nempy.account.Account.inquirer_account', return_value='TBR5X6UG3ZT2IIOAP65Y7J7SLPN4UPARKH6HMUI'):
            account0, _ = self.profile.create_account(is_import=True)
            assert account0 == account1

            with patch('nempy.account.Account.get_generation_type', return_value=GenerationType.PRIVATE_KEY):
                with pytest.raises(NotImplementedError):
                    self.profile.create_account(is_import=True)

            class NewGenerationType:
                name = 'UNKNOWN'
            with patch('nempy.account.Account.get_generation_type', return_value=NewGenerationType()):
                with pytest.raises(NotImplementedError):
                    self.profile.create_account(is_import=True)

    def test_inquirer_default_account(self):
        # and test_load_accounts
        with patch('nempy.profile.inquirer.prompt', return_value={'name': 'account-1'}):
            self.profile.inquirer_default_account()
            assert self.account1.dict() == self.profile.account.dict()

        real_value = self.profile.load_accounts()

        assert self.profile.account.name == 'account-1'

        with patch('nempy.profile.input', return_value='y'), \
             patch('nempy.profile.Profile.create_account', return_value=(self.profile.account, True)), \
             patch('nempy.profile.Profile.load_accounts') as mocked_load_accounts, \
             patch('nempy.profile.inquirer.prompt', return_value={'name': 'account-0'}):
            mocked_load_accounts.side_effect = [{}, real_value, real_value, real_value]
            account = self.profile.inquirer_default_account()
        assert account.name == 'account-1'

        with patch('nempy.profile.input', return_value='y'), \
             patch('nempy.profile.Profile.create_account', return_value=(self.profile.account, False)), \
             patch('nempy.profile.Profile.load_accounts') as mocked_load_accounts, \
             patch('nempy.profile.inquirer.prompt', return_value={'name': 'account-0'}):
            mocked_load_accounts.side_effect = [{}, real_value, real_value, real_value]
            account = self.profile.inquirer_default_account()
        assert account.name == 'account-0'

        with patch('nempy.profile.Profile.load_accounts', return_value={}), \
                patch('nempy.profile.input', return_value='n'):
            profile = self.profile.inquirer_default_account()
            assert profile is None
