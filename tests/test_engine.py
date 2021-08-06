# from unittest.mock import patch, PropertyMock
#
# import pytest
# from nempy.engine import XYMEngine, EngineStatusCode, NEMEngine
# from nempy.sym import network
# from nempy.sym.constants import BlockchainStatuses, TransactionStatus
#
# from .test_account import test_account
#
#
# class TestEngine:
#
#     def setup(self):
#         self.pw = 'pass'
#         self.account0, self.account1 = test_account()
#         self.account0 = self.account0.encrypt(self.pw)
#         self.engine = XYMEngine(self.account0)
#
#     def test_send_tokens(self):
#         result = self.engine.send_tokens(self.account1.address, [('@symbol.xym', 0.001)], 'Hello NEM!', True, self.pw)
#         assert result == EngineStatusCode.INVALID_ACCOUNT_INFO
#         param = {'account': {'publicKey': self.account1.public_key}}
#         with patch.object(network, 'get_accounts_info', return_value=param):
#             result = self.engine.send_tokens(self.account1.address, [('@symbol.xym', 0.001)], 'Hello NEM!', True, self.pw)
#             assert not isinstance(result, EngineStatusCode)
#         result = self.engine.send_tokens(self.account1.address, [('@symbol.xym', 0.001)], 'Hello NEM!', False, self.pw)
#         assert not isinstance(result, EngineStatusCode)
#         self.entity_hash = result
#         tr_conf = XYMEngine.check_transaction_confirmation(self.entity_hash)
#         assert tr_conf == TransactionStatus.NOT_FOUND
#
#     def test_check_status(self):
#         result = self.engine.check_status()
#         assert result == BlockchainStatuses.OK
#         with patch(__name__ + '.XYMEngine.account', new_callable=PropertyMock, return_value=None):
#             result = self.engine.check_status()
#             assert result == BlockchainStatuses.NOT_INITIALIZED
#
#     def test_get_balance(self):
#         balance1 = self.engine.get_balance(humanization=True)
#         balance2 = self.engine.get_balance(self.engine.account.address, humanization=True)
#         assert balance1 == balance2
#         with patch.object(network, 'get_mosaic_names', return_value=None), \
#              patch.object(network, 'get_balance', return_value={'091F837E059AE13C': .1}):
#             balance = self.engine.get_balance(humanization=True)
#             assert balance == {'091F837E059AE13C': .1}
#
#     def test_base_methods(self):
#         engine_as_str = str(self.engine)
#         assert 'Address' in engine_as_str and 'URL' in engine_as_str and 'Public Key' in engine_as_str
#         for val in dict(self.engine).values():
#             assert val in engine_as_str
#
#         nem_engine = NEMEngine('', None)
#         with pytest.raises(NotImplementedError):
#             nem_engine.check_status()
#         with pytest.raises(NotImplementedError):
#             nem_engine.get_balance(None, None)
#         with pytest.raises(NotImplementedError):
#             nem_engine.send_tokens(None, None, None, None, None, None)
#
#
