from binascii import hexlify

import pytest
from nempy.sym import ed25519, network
from nempy.sym.api import Message, PlainMessage, EncryptMessage, Namespace, Mosaic, Transaction, dividers
from nempy.sym.constants import NetworkType, Fees, TransactionTypes
from nempy.sym.network import Timing

from unittest.mock import patch

from ..test_user_data import TestAccountData


class TestMessage:

    @staticmethod
    @pytest.mark.parametrize('is_encrypted', [True, False])
    @pytest.mark.parametrize('messages', ['Hello NEM!', '', '#' * 1024])
    def test_message(messages, is_encrypted):
        if messages == 'Hello NEM!':
            message = Message(messages, is_encrypted=is_encrypted)
            assert message == b'Hello NEM!'
        if is_encrypted and messages == '':
            with pytest.raises(RuntimeError):
                Message(messages, is_encrypted=is_encrypted)
        if messages == '#' * 1024:
            with pytest.raises(OverflowError):
                Message(messages, is_encrypted=is_encrypted)

    @staticmethod
    def test_plain_message():
        _messages = 'Hello NEM!'
        message = PlainMessage(_messages)
        assert message == b'\x00Hello NEM!'
        assert message.size == len(_messages) + 1
        message = PlainMessage('')
        assert message == b''

    @staticmethod
    def test_encrypt_message():
        _message = 'Hello NEM!'
        account0, account1 = TestAccountData().setup()
        sender_private_key = account0.private_key
        recipient_pub = account1.public_key

        enc_message = EncryptMessage(_message, sender_private_key, recipient_pub)
        with pytest.raises(OverflowError):
            EncryptMessage('#' * 1023, sender_private_key, recipient_pub)

        assert enc_message.size == 77
        recipient_priv = account1.private_key
        sender_pub = account0.public_key

        message = ed25519.Ed25519.decrypt(recipient_priv, sender_pub, enc_message[1:])
        assert message == b'Hello NEM!'


class TestNamespace:

    @staticmethod
    def test_namespace():
        namespace = Namespace('gtns.gt.gt-')
        assert namespace == '93EB2CE4539AB443'
        with pytest.raises(ValueError):
            Namespace('')
        with pytest.raises(ValueError):
            Namespace('test@')
        with pytest.raises(ValueError):
            Namespace('t' * 65)
        with pytest.raises(ValueError):
            Namespace('gtns.gt.gt.gt')


class TestMosaic:

    @staticmethod
    @patch(__name__ + '.Mosaic.get_divisibility', return_value=6)
    @patch(__name__ + '.Mosaic.alias_to_mosaic_id', return_value='091F837E059AE13C')
    @pytest.mark.asyncio
    async def test_new(mock_alias, mock_div):
        mosaic = await Mosaic.create('091F837E059AE13C', 0.123)
        assert mosaic == (657388647902535996, 123000)
        mosaic = await Mosaic.create('@symbol.xym', 0.123)
        assert mosaic == (657388647902535996, 123000)
        mock_div.return_value = None
        with pytest.raises(ValueError):
            await Mosaic.create('', 0.123)
        with pytest.raises(ValueError):
            await Mosaic('', 0.123)

    @staticmethod
    @pytest.mark.asyncio
    async def test_alias_to_mosaic_id():
        mosaic_id = '.'.join(['eh434g57dz6sd76fogs76sd6fsd65f'] * 3)
        is_joke = False
        try:
            await Mosaic.alias_to_mosaic_id(mosaic_id)
        except ValueError:
            #  if someone has created namespace named eh434g57dz6sd76fogs76sd6fsd65f * 3
            is_joke = True
        if not is_joke:
            with pytest.raises(ValueError):
                await Mosaic.alias_to_mosaic_id(mosaic_id)
        mosaic_id = await Mosaic.alias_to_mosaic_id('symbol.xym')
        assert mosaic_id == '091F837E059AE13C'


class TestDividers:

    def test_dividers(self):
        mosaic = 'symbol-.xym'
        div = 6
        dividers.set(mosaic, div)
        assert dividers.get(mosaic) == div
        for key in dividers:
            if key == mosaic:
                assert dividers.get(mosaic) == div


class TestTransaction:

    def setup(self):
        self.transaction = Transaction()
        # self.transaction.network_type = NetworkType.TEST_NET
        # self.transaction.timing = Timing(self.transaction.network_type)
        self.account0, self.account1 = TestAccountData().setup()

    @pytest.mark.asyncio
    async def test_create(self):
        await self.transaction.create(pr_key=self.account0.private_key,
                                      recipient_address=self.account1.address)

        with pytest.raises(ValueError):
            await self.transaction.create(pr_key=self.account0.private_key,
                                          recipient_address=self.account1.address,
                                          mosaics=('symbol.xym', 0000))

        await self.transaction.create(pr_key=self.account0.private_key,
                                      recipient_address=self.account1.address,
                                      mosaics=[await Mosaic.create('63BD920B6562A692', 0.0001),
                                               await Mosaic.create('091F837E059AE13C', 0.00001)])

        await self.transaction.create(pr_key=self.account0.private_key,
                                      recipient_address=self.account1.address,
                                      mosaics=await Mosaic.create('63BD920B6562A692', 0.0001))

    @pytest.mark.asyncio
    async def test_calc_max_fee(self):
        fast = await Transaction.calc_max_fee(160, Fees.FAST)
        average = await Transaction.calc_max_fee(160, Fees.AVERAGE)
        slow = await Transaction.calc_max_fee(160, Fees.SLOW)
        slowest = await Transaction.calc_max_fee(160, Fees.SLOWEST)
        zero = await Transaction.calc_max_fee(160, Fees.ZERO)
        print(zero, slowest, slow, average, fast)
        assert zero < slowest < slow < average < fast

        with patch.object(network, 'get_fee_multipliers', return_value=None):
            with pytest.raises(ValueError):
                await Transaction.calc_max_fee(160, Fees.FAST)

    def test_entity_hash_gen(self):
        class T:
            type = TransactionTypes.AGGREGATE_BONDED

            def serialize(self):
                return None
        with pytest.raises(NotImplementedError):
            Transaction.entity_hash_gen(None, None, T(), None)

