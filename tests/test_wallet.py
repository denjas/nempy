import os
import shutil
import tempfile
from unittest.mock import patch

from nempy.wallet import Wallet
from nempy.sym.constants import NetworkType


class TestWallet:

    def setup(self):
        self.wallet_dir = tempfile.NamedTemporaryFile().name
        os.makedirs(self.wallet_dir)

    def teardown(self):
        shutil.rmtree(self.wallet_dir)

    def test_init(self):
        profile_name = 'test'
        password = 'pass'
        Wallet(self.wallet_dir, init_only=True)
        with patch('nempy.profile.input', return_value=profile_name), \
             patch('nempy.profile.Profile.input_network_type', return_value=NetworkType.TEST_NET.value), \
             patch('nempy.profile.Profile.input_new_pass', return_value=password):
            with patch('nempy.wallet.input', return_value='n'):
                wallet = Wallet(self.wallet_dir)
                assert wallet.profile is None

            with patch('nempy.wallet.input', return_value='y'):
                wallet = Wallet(self.wallet_dir)
                assert wallet.profile is not None


