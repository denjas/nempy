import tempfile

import bcrypt
import pytest
from nempy.user_data import AccountData, DecoderStatus, ProfileData, UserData
from nempy.sym.network import NetworkType
import os


class TestUserData:

    def setup(self):
        self.profile_data = ProfileData(nane='', network_type=NetworkType.TEST_NET, pass_hash=b'')

    def test_str(self):
        UserData.__str__(self.profile_data)


class TestAccountData:

    def setup(self):
        self.name = 'test'
        self.password = 'pass'
        bip32_coin_id_test_net = 1
        mnemonic = 'stick quantum ensure tower inner useless butter base ' \
                   'glance craft upset danger cheese pet dilemma soda sound ' \
                   'question autumn theory garden ceiling height taxi'
        network_type = NetworkType.TEST_NET
        accounts = AccountData.accounts_pool_by_mnemonic(network_type, bip32_coin_id_test_net, mnemonic)
        self.account_data = accounts['TBTCYCIDRQ7TJBEAYDZLDPHOTGIRKZHO5CH2SMQ']  #  'TCULT7R63UUSG2NTE3FJTWJD3U2JEOWPOFYEQQA' - second account
        pass

    def test_repr(self):
        assert repr(self.account_data) == '<class `AccountData`>'

    def test_str(self):
        assert not [val for val in ['Name', 'Network Type', 'Address', 'Public Key', 'Private Key', 'Path', 'Profile'] if val not in str(self.account_data)]
        self.account_data.encrypt(self.password)
        assert '*' * 64 in str(self.account_data)
        assert '******* **** **********' in str(self.account_data)
        self.account_data.decrypt(self.password)

    def test_serialize_deserialize_eu(self):
        data = self.account_data.serialize()
        assert AccountData.deserialize(data) == self.account_data

    def test_validate_address(self):
        with pytest.raises(ValueError):
            self.account_data.address = 'ADDRESS'

    def test_write_read(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, self.name)

            with pytest.raises(ValueError):
                self.account_data.write(path)

            self.account_data.encrypt(self.password).write(path)

            no_data = AccountData.read(path + 'random')
            assert no_data == DecoderStatus.NO_DATA

            account_data = AccountData.read(path)
            assert account_data == self.account_data

            self.account_data.decrypt(self.password)

    def test_encrypt_decrypt_is_encrypted(self):
        self.account_data.encrypt(self.password)
        assert self.account_data.is_encrypted()

        with pytest.raises(ValueError):
            self.account_data.decrypt(self.password + 'random')

        self.account_data = self.account_data.decrypt(self.password)
        assert not self.account_data.is_encrypted()
        with pytest.raises(ValueError):
            self.account_data.decrypt(self.password)


class TestProfileData:

    def setup(self):
        self.name = 'test'
        self.password = 'pass'
        self.params = {
            'name': 'profile-name',
            'network_type': NetworkType.TEST_NET,
            'pass_hash': bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt(12))
        }
        self.profile_data = ProfileData(**self.params)

    def test_repr(self):
        assert repr(self.profile_data) == '<class `ProfileData`>'

    def test_str(self):
        assert not [val for val in ['Name', 'Network Type', 'Pass Hash'] if val not in str(self.profile_data)]

    def test_serialize_deserialize_eu(self):
        data = self.profile_data.serialize()
        assert ProfileData.deserialize(data) == self.profile_data

    def test_write_read(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, self.name)

            self.profile_data.write(path)
            profile_data = ProfileData.read(path)
            assert profile_data == self.profile_data
            profile_data.name = 'new_name'
            assert profile_data != self.profile_data

    def test_check_pass(self):
        assert self.profile_data.check_pass(self.password) is True
        assert self.profile_data.check_pass(self.password + 'random') is False


