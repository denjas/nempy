import os
import shutil
import tempfile
from unittest.mock import patch

from nempy.wallet import Wallet


class TestWallet:

    def setup(self):
        self.wallet_dir = tempfile.NamedTemporaryFile().name
        os.makedirs(self.wallet_dir)

    def teardown(self):
        shutil.rmtree(self.wallet_dir)

    def test_init(self):
        Wallet(self.wallet_dir, skip_checks=True)
        with patch('nempy.wallet.input', return_value='y'):
            wallet = Wallet(self.wallet_dir, skip_checks=True)
            print(wallet)
