import os
import tempfile

from nempy.ui import UD, UDTypes, ProfileI, AccountI
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
        self.account_data = TestAccountData().setup().encrypt('pass')
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

        self.account_data = TestAccountData().setup().encrypt('pass')
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
