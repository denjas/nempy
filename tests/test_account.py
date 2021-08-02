import os
import tempfile
from unittest.mock import patch

import pytest
import stdiomask
from nempy.account import Account, GenerationType
from nempy.sym.constants import NetworkType


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
    with patch('nempy.account.input', return_value=value):
        assert value*3 in Account.input_keyprint_entropy()


def test_init_general_params():
    accounts_dir = tempfile.NamedTemporaryFile().name
    with patch('nempy.account.input', side_effect=['test', 'y']):
        account_path, name, bip32_coin_id, is_default = Account.init_general_params(NetworkType.TEST_NET, accounts_dir)
        assert account_path == os.path.join(accounts_dir, 'test.account')
        assert bip32_coin_id == 1
        assert is_default is True
        assert name == 'test'

    with patch('nempy.account.input', side_effect=['test', 'n']):
        account_path, name, bip32_coin_id, is_default = Account.init_general_params(NetworkType.TEST_NET, accounts_dir)
        assert account_path == os.path.join(accounts_dir, 'test.account')
        assert bip32_coin_id == 1
        assert is_default is False
        assert name == 'test'

    with patch('nempy.account.input', side_effect=['test', 'y']):
        account_path, name, bip32_coin_id, is_default = Account.init_general_params(NetworkType.MAIN_NET, accounts_dir)
        assert account_path == os.path.join(accounts_dir, 'test.account')
        assert bip32_coin_id == 4343
        assert is_default is True
        assert name == 'test'

    with patch('nempy.account.input', side_effect=['test', 'n']):
        with pytest.raises(ValueError):
            Account.init_general_params('MAIN_NET', accounts_dir)




