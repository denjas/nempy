import copy
import os
import tempfile
from unittest.mock import patch

import pytest
import stdiomask
from nempy.account import Account, GenerationType
from nempy.sym.constants import NetworkType

from nempy import account


@patch.object(Account, 'input_keyprint_entropy', return_value='test')
def test_account(mock_keyprint_entropy):
    network_type = NetworkType.TEST_NET
    bip32_coin_id_test_net = 1

    with patch.object(Account, 'inquirer_account', return_value='TD6HYHFAQPGN3QB5GH46I35RYWM5VMMBOW32RXQ'):
        account0 = Account.account_by_mnemonic(network_type=network_type, bip32_coin_id=bip32_coin_id_test_net)
        with patch.object(stdiomask, 'getpass', return_value=account0.mnemonic):
            account0_ = Account.account_by_mnemonic(network_type=network_type, bip32_coin_id=bip32_coin_id_test_net,
                                                    is_import=True)
            assert account0.address == account0_.address

    with patch.object(Account, 'inquirer_account', return_value='TBR5X6UG3ZT2IIOAP65Y7J7SLPN4UPARKH6HMUI'):
        account1 = Account.account_by_mnemonic(network_type=network_type, bip32_coin_id=bip32_coin_id_test_net)

    path = tempfile.NamedTemporaryFile().name
    password = 'pass'
    account0.encrypt(password).write(path)
    assert '*' * 64 in str(account0)
    address = '-'.join(account0.address[i:i + 6] for i in range(0, len(account0.address), 6))
    account0.address = address
    assert account0.address == address.replace('-', '')
    account0_.read(path).decrypt(password)
    assert account0.address == account0_.address
    account0_.name = 'account-0'
    account1.name = 'account-1'
    return account0_, account1


def test_get_generation_type():
    with patch('inquirer.prompt', return_value={'type': 'Private Key'}):
        assert GenerationType.PRIVATE_KEY == Account.get_generation_type()

    with patch('inquirer.prompt', return_value={'type': 'Mnemonic'}):
        assert GenerationType.MNEMONIC == Account.get_generation_type()


def test_inquirer_account():
    with patch('inquirer.prompt', return_value={'address': 'Address2'}):
        assert 'Address2' == Account.inquirer_account(['Address1', 'Address2'])


def test_input_keyprint_entropy():
    value = 'test'
    with patch('nempy.account.input', side_effect=[value, '', value, value, value, value]):
        assert value*3 in Account.input_keyprint_entropy()


def test_init_general_params():
    with tempfile.TemporaryDirectory() as accounts_dir:
        tmp_test_account = 'test.account'
        with patch('nempy.account.input', side_effect=['', 'test_exist', 'test', 'y']):
            #  emulate exist account
            open(os.path.join(accounts_dir, 'test_exist.account'), 'a').close()
            account_path, name, bip32_coin_id, is_default = Account.init_general_params(NetworkType.TEST_NET, accounts_dir)
            assert account_path == os.path.join(accounts_dir, tmp_test_account)
            assert bip32_coin_id == 1
            assert is_default is True
            assert name == 'test'

        with patch('nempy.account.input', side_effect=['test', 'n']):
            account_path, name, bip32_coin_id, is_default = Account.init_general_params(NetworkType.TEST_NET, accounts_dir)
            assert account_path == os.path.join(accounts_dir, tmp_test_account)
            assert bip32_coin_id == 1
            assert is_default is False
            assert name == 'test'

        with patch('nempy.account.input', side_effect=['test', 'y']):
            account_path, name, bip32_coin_id, is_default = Account.init_general_params(NetworkType.MAIN_NET, accounts_dir)
            assert account_path == os.path.join(accounts_dir, tmp_test_account)
            assert bip32_coin_id == 4343
            assert is_default is True
            assert name == 'test'

        with patch('nempy.account.input', side_effect=['test', 'n']):
            with pytest.raises(ValueError):
                Account.init_general_params('MAIN_NET', accounts_dir)


def test_account_init():
    params = {'name': 'name'}
    with pytest.raises(TypeError):
        Account(params)
    params = {'name1': 'name'}
    with pytest.raises(TypeError):
        Account(params)
    params = {'private_key': 1}
    with pytest.raises(TypeError):
        Account(params)


def test_encryption_decryption():
    data = b'data'
    password = 'pass'
    enc_data = account.encryption(password, data)
    _data = account.decryption(password, enc_data)
    assert data == _data
    assert account.decryption(password+'random', enc_data) is None


class TestAccount:
    account = None

    @patch.object(Account, 'input_keyprint_entropy', return_value='test')
    def setup(self, mock_ike):
        network_type = NetworkType.TEST_NET
        bip32_coin_id_test_net = 1

        with patch.object(Account, 'inquirer_account', return_value='TD6HYHFAQPGN3QB5GH46I35RYWM5VMMBOW32RXQ'):
            self.account = Account.account_by_mnemonic(network_type=network_type, bip32_coin_id=bip32_coin_id_test_net)

    def test_encrypt(self):
        assert isinstance(self.account.private_key, str)
        assert isinstance(self.account.mnemonic, str)
        self.account.encrypt('pass')
        assert isinstance(self.account.private_key, bytes)
        assert isinstance(self.account.mnemonic, bytes)

    def test_decrypt(self):
        if not self.account.is_encrypted():
            self.account.encrypt('pass')
        decrypted = self.account.decrypt('pass')
        assert isinstance(decrypted.private_key, str)
        assert isinstance(decrypted.mnemonic, str)
        with pytest.raises(ValueError):
            self.account.decrypt('pass'+'random')
        tmp_account = copy.deepcopy(self.account)
        tmp_account.private_key = 'KEY'
        with pytest.raises(ValueError):
            tmp_account.decrypt('pass')

    def test_write_read(self):
        if not self.account.is_encrypted():
            self.account.encrypt('pass')
        with tempfile.TemporaryDirectory() as temporary:
            path = os.path.join(temporary, 'test.account')
            self.account.write(path)
            _account = self.account.read(path)
            assert self.account == _account
            tmp_account = copy.deepcopy(self.account)
            with pytest.raises(ValueError):
                tmp_account.address = 'ADDRES'
            with pytest.raises(ValueError):
                _account.decrypt('pass').write(path)
            _account = self.account.read(path + 'random')
            assert account.DecoderStatus.NO_DATA == _account

    def test_inquirer_history(self):
        with patch('inquirer.prompt', return_value={'transaction': 'Exit'}):
            with pytest.raises(SystemExit):
                self.account.inquirer_history(page_size=1)
            with pytest.raises(SystemExit):
                self.account.inquirer_history(page_size=1, address='TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ')







