import os
import tempfile
from unittest.mock import patch

import pytest
import stdiomask
from nempy import ui
from nempy.sym.constants import NetworkType
from nempy.ui import UD, UDTypes, ProfileI, AccountI, AccountUI, PasswordPolicyError, RepeatPasswordError
from nempy.user_data import GenerationType
from nempy.wallet import Wallet

from .test_user_data import TestAccountData, TestProfileData


class TestUD:

    def setup(self):
        self.wallet_dir = tempfile.TemporaryDirectory()
        self.wallet = Wallet(self.wallet_dir.name, init_only=True)

        class TUD(UD):
            type_ud = UDTypes.PROFILE
        self.ud = TUD(self.wallet.config_file, self.wallet.profiles_dir, self.wallet.accounts_dir)

    def teardown(self):
        self.wallet_dir.cleanup()

    def test_user_data(self):
        assert self.ud.user_data is None

    def test_load_uds(self):
        assert self.ud.load_uds() == {}

    def test_set_get_default_ud(self):
        class Tmp:
            name = 'test'
        self.ud.set_default_ud(Tmp())
        assert Tmp.name == self.ud.get_default_ud_name()


class TestAccountI:

    def setup(self):
        self.wallet_dir = tempfile.TemporaryDirectory()
        self.wallet = Wallet(self.wallet_dir.name, init_only=True)

        self.account_i = AccountI(self.wallet.config_file, self.wallet.accounts_dir)
        self.account_data, _ = TestAccountData().setup()
        self.account_data.encrypt('pass')
        self.account_data.name = 'test'
        self.account_data.write(os.path.join(self.wallet.accounts_dir, self.account_data.name))

    def teardown(self):
        self.wallet_dir.cleanup()

    def test_set_default_account(self):
        self.account_i.set_default_account(self.account_data)
        assert self.account_i.get_default_ud_name() == self.account_data.name

    def test_data(self):
        self.account_i.set_default_account(self.account_data)
        account_data = self.account_i.data
        assert account_data == self.account_data

    def test_load_accounts(self):
        self.account_i.set_default_account(self.account_data)
        self.account_data.name = 'test-1'
        self.account_data.write(os.path.join(self.wallet.accounts_dir, self.account_data.name))
        self.account_i.set_default_account(self.account_data)
        accounts = self.account_i.load_accounts()
        assert len(accounts) == 2


class TestProfileI:

    def setup(self):
        self.wallet_dir = tempfile.TemporaryDirectory()
        self.wallet = Wallet(self.wallet_dir.name, init_only=True)

        profile_name = 'profile-name'
        self.profile_i = ProfileI(self.wallet.config_file, self.wallet.profiles_dir, self.wallet.accounts_dir)
        self.profile_data = TestProfileData().setup()
        self.profile_data.name = profile_name

        self.profile_data.write(os.path.join(self.wallet.profiles_dir, self.profile_data.name))

        self.account_data, _ = TestAccountData().setup()
        self.account_data.encrypt('pass')
        self.account_data.name = 'test'
        self.account_data.profile = profile_name
        self.account_data.write(os.path.join(self.wallet.accounts_dir, self.account_data.name))

    def teardown(self):
        self.wallet_dir.cleanup()

    def test_set_default_profile(self):
        self.profile_i.set_default_profile(self.profile_data)
        assert self.profile_i.get_default_ud_name() == self.profile_data.name

    def test_data(self):
        self.profile_i.set_default_profile(self.profile_data)
        profile_data = self.profile_i.data
        assert profile_data == self.profile_data

    def test_load_profiles(self):
        self.profile_i.set_default_profile(self.profile_data)
        self.profile_data.name = 'test-1'
        self.profile_data.write(os.path.join(self.wallet.profiles_dir, self.profile_data.name))
        self.profile_i.set_default_profile(self.profile_data)
        profiles = self.profile_i.load_profiles()
        assert len(profiles) == 2

    def test_account(self):
        self.profile_i.set_default_account(self.account_data)
        assert self.profile_i.account.data.name == self.account_data.name

    def test_load_accounts(self):
        self.profile_i.set_default_profile(self.profile_data)
        self.account_data.name = 'test-1'
        self.account_data.write(os.path.join(self.wallet.accounts_dir, self.account_data.name))
        self.profile_i.set_default_account(self.account_data)
        assert len(self.profile_i.load_accounts()) == 2

    def test_set_default_account(self):
        self.profile_i.set_default_account(self.account_data)
        assert self.profile_i.account.data.name == self.account_data.name


class TestAccountUI:

    def setup(self):
        self.wallet_dir = tempfile.TemporaryDirectory()
        self.wallet = Wallet(self.wallet_dir.name, init_only=True)

        self.profile_data = TestProfileData().setup()

        self.password = 'pass'
        self.account_data, _ = TestAccountData().setup()
        self.account_data.encrypt(self.password)
        self.account_data.name = 'test'
        self.account_data.profile = self.profile_data.name

    def teardown(self):
        self.wallet_dir.cleanup()

    def test_init_general_params(self):
        with tempfile.TemporaryDirectory() as accounts_dir:
            tmp_test_account = 'test.account'
            with patch('nempy.ui.input', side_effect=['', 'test_exist', 'test', 'y']):
                #  emulate exist account
                open(os.path.join(accounts_dir, 'test_exist.account'), 'a').close()
                account_path, name, is_default = AccountUI.ui_init_general_params(accounts_dir)
                bip32_coin_id = NetworkType.TEST_NET.bip32_coin_id
                assert account_path == os.path.join(accounts_dir, tmp_test_account)
                assert bip32_coin_id == 1
                assert is_default is True
                assert name == 'test'

            with patch('nempy.ui.input', side_effect=['test', 'n']):
                account_path, name, is_default = AccountUI.ui_init_general_params(accounts_dir)
                bip32_coin_id = NetworkType.TEST_NET.bip32_coin_id
                assert account_path == os.path.join(accounts_dir, tmp_test_account)
                assert bip32_coin_id == 1
                assert is_default is False
                assert name == 'test'

            with patch('nempy.ui.input', side_effect=['test', 'y']):
                account_path, name, is_default = AccountUI.ui_init_general_params(accounts_dir)
                bip32_coin_id = NetworkType.MAIN_NET.bip32_coin_id
                assert account_path == os.path.join(accounts_dir, tmp_test_account)
                assert bip32_coin_id == 4343
                assert is_default is True
                assert name == 'test'

    def test_iu_create_import_account(self):
        account_path = os.path.join(self.wallet.accounts_dir, self.account_data.name)
        # create
        with patch('nempy.ui.AccountUI.ui_init_general_params', return_value=(account_path, self.account_data.name, 1, True)), \
             patch('nempy.ui.ProfileUI.ui_check_pass', return_value=self.password), \
             patch('nempy.ui.AccountUI.ui_account_by_mnemonic', return_value=self.account_data):
            account1, _ = ui.AccountUI.iu_create_account(self.profile_data, self.wallet.accounts_dir, is_default=False)
            assert account1 == self.account_data
            # import
            with patch('nempy.ui.AccountUI.ui_generation_type_inquirer', return_value=GenerationType.MNEMONIC):
                account1, _ = ui.AccountUI.iu_create_account(self.profile_data, self.wallet.accounts_dir, is_default=True, is_import=True)

            with patch('nempy.ui.AccountUI.ui_generation_type_inquirer', return_value=GenerationType.PRIVATE_KEY):
                with pytest.raises(NotImplementedError):
                    ui.AccountUI.iu_create_account(self.profile_data, self.wallet.accounts_dir, is_default=True, is_import=True)

            class NewGenerationType:
                name = 'UNKNOWN'
            with patch('nempy.ui.AccountUI.ui_generation_type_inquirer', return_value=NewGenerationType()):
                with pytest.raises(NotImplementedError):
                    ui.AccountUI.iu_create_account(self.profile_data, self.wallet.accounts_dir, is_default=True, is_import=True)

            with patch('nempy.ui.ProfileUI.ui_check_pass', return_value=None):
                account1, _ = ui.AccountUI.iu_create_account(self.profile_data, self.wallet.accounts_dir,
                                                             is_default=False)
                assert account1 is None

    def test_save_and_check(self):
        account_path = os.path.join(self.wallet.accounts_dir, self.account_data.name)
        account_data = ui.AccountUI.save_and_check(self.account_data, account_path, self.password)
        assert self.account_data.decrypt(self.password) == account_data

    def test_ui_default_account(self):
        accounts = {self.account_data.name: self.account_data}

        with patch('inquirer.prompt', return_value={'name': self.account_data.name}):
            account_data = ui.AccountUI.ui_default_account(accounts)
            assert self.account_data == account_data

        with patch('inquirer.prompt', return_value=None):
            with pytest.raises(SystemExit):
                ui.AccountUI.ui_default_account(accounts)

    def test_ui_generation_type_inquirer(self):
        with patch('inquirer.prompt', return_value={'type': 'Mnemonic'}):
            assert ui.AccountUI.ui_generation_type_inquirer() == GenerationType.MNEMONIC
        with patch('inquirer.prompt', return_value={'type': 'Private Key'}):
            assert ui.AccountUI.ui_generation_type_inquirer() == GenerationType.PRIVATE_KEY

    def test_inquirer_history(self):
        with patch('inquirer.prompt', return_value={'transaction': 'Exit'}):
            with pytest.raises(SystemExit):
                ui.AccountUI.ui_history_inquirer(page_size=1)
            with pytest.raises(SystemExit):
                ui.AccountUI.ui_history_inquirer(page_size=1, address='TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')

    def test_ui_keyprint_entropy(self):
        value = 'test'
        with patch('nempy.ui.input', side_effect=[value, '', value, value, value, value]):
            assert value * 3 in ui.AccountUI.ui_keyprint_entropy()

    def test_ui_account_inquirer(self):
        accounts = [self.account_data.name]
        with patch('inquirer.prompt', return_value={'address': self.account_data.name}):
            name = ui.AccountUI.ui_account_inquirer(accounts)
            assert self.account_data.name == name

    def test_ui_account_by_mnemonic(self):
        mnemonic = 'myth flip assault spoon dilemma fitness dutch stuff ' \
                   'attitude imitate neutral fame sample rookie negative ' \
                   'oyster forward glimpse crystal alone agent cream marine frog'
        with patch('nempy.ui.AccountUI.ui_account_inquirer', return_value='TD6HYHFAQPGN3QB5GH46I35RYWM5VMMBOW32RXQ'), \
             patch('nempy.ui.AccountUI.ui_keyprint_entropy', return_value='test'):
            account_data = ui.AccountUI.ui_account_by_mnemonic(NetworkType.TEST_NET, 1)
            assert account_data.address == 'TD6HYHFAQPGN3QB5GH46I35RYWM5VMMBOW32RXQ'
            assert account_data.mnemonic == mnemonic

            with patch('stdiomask.getpass', return_value=mnemonic):
                account_data = ui.AccountUI.ui_account_by_mnemonic(NetworkType.TEST_NET, 1, is_import=True)
                assert account_data.address == 'TD6HYHFAQPGN3QB5GH46I35RYWM5VMMBOW32RXQ'
                assert account_data.mnemonic == mnemonic


class TestProfileUI:

    def setup(self):
        self.password = 'pass'
        self.wallet_dir = tempfile.TemporaryDirectory()
        self.wallet = Wallet(self.wallet_dir.name, init_only=True)

        self.profile_data = TestProfileData().setup()

    def test_ui_default_profile(self):
        params = {self.profile_data.name: self.profile_data}
        with patch('inquirer.prompt', return_value={'name': self.profile_data.name + f' [{self.profile_data.network_type.name}]'}):
            profile_data = ui.ProfileUI.ui_default_profile(params)
            assert profile_data == self.profile_data

    def test_ui_create_profile(self):
        path = os.path.join(self.wallet.accounts_dir, self.profile_data.name)
        with patch('nempy.ui.ProfileUI.ui_profile_name', return_value=(self.profile_data.name, path)), \
             patch('nempy.ui.ProfileUI.ui_network_type', return_value=self.profile_data.network_type), \
             patch('nempy.ui.ProfileUI.ui_new_pass', return_value=self.password):
            profile_data, path = ui.ProfileUI.ui_create_profile(self.wallet.profiles_dir, self.wallet.config_file)
            assert profile_data.name == self.profile_data.name

    def test_ui_check_pass(self):
        with patch.object(stdiomask, 'getpass', return_value=self.password):
            assert ui.ProfileUI.ui_check_pass(self.profile_data) == self.password
        with patch.object(stdiomask, 'getpass', return_value=self.password + 'random'):
            assert ui.ProfileUI.ui_check_pass(self.profile_data) is None

    def test_ui_is_default(self):
        with patch('nempy.ui.input', return_value='y'):
            assert ui.ProfileUI.ui_is_default(self.profile_data.name) is True

        with patch('nempy.ui.input', return_value='n'):
            assert ui.ProfileUI.ui_is_default(self.profile_data.name) is False

    def test_ui_profile_name(self):
        with patch('nempy.ui.input', return_value=''):
            with pytest.raises(ValueError):
                ui.ProfileUI.ui_profile_name(self.wallet.profiles_dir, attempts=1)
        with patch('nempy.ui.input', return_value='name.name'):
            with pytest.raises(ValueError):
                ui.ProfileUI.ui_profile_name(self.wallet.profiles_dir, attempts=1)

        with patch('nempy.ui.input', return_value=self.profile_data.name):
            _name, _path = ui.ProfileUI.ui_profile_name(self.wallet.profiles_dir, attempts=1)
            assert self.profile_data.name == _name
        path = os.path.join(self.wallet.profiles_dir, f'{self.profile_data.name}.profile')
        assert path == _path
        open(path, 'a').close()
        with patch('nempy.ui.input', return_value=self.profile_data.name):
            with pytest.raises(ValueError):
                ui.ProfileUI.ui_profile_name(self.wallet.profiles_dir, attempts=1)

    def test_ui_network_type(self):
        with patch('inquirer.prompt', return_value={'type': 'TEST_NET'}):
            assert NetworkType.TEST_NET == ui.ProfileUI.ui_network_type()
        with patch('inquirer.prompt', return_value={'type': 'MAIN_NET'}):
            assert NetworkType.MAIN_NET == ui.ProfileUI.ui_network_type()
        with patch('inquirer.prompt', return_value={'type': 'UNKNOWN_NET'}):
            with pytest.raises(TypeError):
                ui.ProfileUI.ui_network_type()

    def test_ui_new_pass(self):
        with patch('stdiomask.getpass', return_value='pass'):
            with pytest.raises(PasswordPolicyError):
                ui.ProfileUI.ui_new_pass(n_attempts=1)

        password = '-P@s5w0rd+1.'
        with patch('stdiomask.getpass', return_value=password):
            assert password == ui.ProfileUI.ui_new_pass(n_attempts=1)

    def test_ui_repeat_password(self):
        password = '-P@s5w0rd+1.'
        with patch('stdiomask.getpass', return_value=password):
            assert password == ui.ProfileUI.ui_repeat_password(n_attempts=1, password='-P@s5w0rd+1.')

        with patch('stdiomask.getpass', return_value=password + 'random'):
            with pytest.raises(RepeatPasswordError):
                assert password == ui.ProfileUI.ui_repeat_password(n_attempts=1, password='-P@s5w0rd+1.')
