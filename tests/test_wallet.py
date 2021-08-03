import os
import shutil
import tempfile
from unittest.mock import patch

from nempy.wallet import Wallet
from nempy.sym.constants import NetworkType


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
            with patch('nempy.wallet.input', return_value='n'):
                wallet = Wallet(self.wallet_dir.name)
                # assert wallet.profile is None

            with patch('nempy.wallet.input', return_value='y'):
                wallet = Wallet(self.wallet_dir.name)
                assert wallet.profile is not None
                wallet.print_profiles()
                # os.remove(os.path.join(wallet.profiles_dir, profile_name + '.profile'))
                self.wallet = wallet

    def teardown(self):
        self.wallet_dir.cleanup()

    def test_inquirer_default_profile(self):
        with patch('inquirer.prompt', return_value={'name': 'test [TEST_NET]'}):
            profile = self.wallet.profile
            _profile = self.wallet.inquirer_default_profile()
            assert str(profile) == str(_profile)

    def test_load_profiles(self):
        profiles = self.wallet.load_profiles()
        print(profiles)



