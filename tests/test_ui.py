import tempfile

from nempy.ui import UD, UDTypes
from nempy.wallet import Wallet


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

