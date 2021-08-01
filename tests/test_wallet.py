import os
import tempfile
from unittest.mock import patch, PropertyMock
import shutil

import stdiomask
from nempy.wallet import Wallet
import profile
from sym.constants import NetworkType


class TestWallet:

    def setup(self):
        self.wallet_dir = tempfile.NamedTemporaryFile().name
        os.makedirs(self.wallet_dir)

    def teardown(self):
        shutil.rmtree(self.wallet_dir)

    def test_init(self):
        wallet = Wallet(self.wallet_dir, skip_checks=True)
