from unittest.mock import patch, PropertyMock

from nempy.sym import network
from nempy.sym.constants import BlockchainStatuses

from .test_account import test_account
from nempy.engine import XYMEngine, EngineStatusCode
from nempy.sym.api import PlainMessage, Mosaic


class TestEngine:

    def setup(self):
        self.pw = 'pass'
        self.account0, self.account1 = test_account()
        self.account0 = self.account0.encrypt(self.pw)
        self.engine = XYMEngine(self.account0)

    def test_send_tokens(self):
        result = self.engine.send_tokens(self.account1.address, [('@symbol.xym', 0.001)], 'Hello NEM!', True, self.pw)
        assert result == EngineStatusCode.INVALID_ACCOUNT_INFO
        param = {'account': {'publicKey': self.account1.public_key}}
        with patch.object(network, 'get_accounts_info', return_value=param):
            result = self.engine.send_tokens(self.account1.address, [('@symbol.xym', 0.001)], 'Hello NEM!', True, self.pw)
            assert not isinstance(result, EngineStatusCode)
        result = self.engine.send_tokens(self.account1.address, [('@symbol.xym', 0.001)], 'Hello NEM!', False, self.pw)
        assert not isinstance(result, EngineStatusCode)

    def test_check_status(self):
        result = self.engine.check_status()
        assert result == BlockchainStatuses.OK
        with patch(__name__ + '.XYMEngine.account', new_callable=PropertyMock, return_value=None):
            result = self.engine.check_status()
            assert result == BlockchainStatuses.NOT_INITIALIZED
