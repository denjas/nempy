import tempfile
from unittest.mock import patch

import stdiomask
from nempy.account import Account
from nempy.sym.constants import NetworkType


@patch.object(Account, 'input_keyprint_entropy', return_value='test')
def test_account(mock_keyprint_entropy):
    network_type = NetworkType.TEST_NET
    bip32_coin_id_test_net = 1

    with patch.object(Account, 'inquirer_account', return_value='TD6HYHFAQPGN3QB5GH46I35RYWM5VMMBOW32RXQ'):
        account0 = Account.account_by_mnemonic(network_type=network_type, bip32_coin_id=bip32_coin_id_test_net,
                                               is_generate=True)
        with patch.object(stdiomask, 'getpass', return_value=account0.mnemonic):
            account0_ = Account.account_by_mnemonic(network_type=network_type, bip32_coin_id=bip32_coin_id_test_net)
            assert account0.address == account0_.address

    with patch.object(Account, 'inquirer_account', return_value='TBR5X6UG3ZT2IIOAP65Y7J7SLPN4UPARKH6HMUI'):
        account1 = Account.account_by_mnemonic(network_type=network_type, bip32_coin_id=bip32_coin_id_test_net,
                                               is_generate=True)

    path = tempfile.NamedTemporaryFile().name
    password = 'pass'
    account0.encrypt(password).write(path)
    account0_.read(path).decrypt(password)
    assert account0.address == account0_.address
    return account0_, account1

