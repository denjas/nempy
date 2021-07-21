import hashlib
import logging
import os
from binascii import unhexlify
from typing import List

from symbolchain.core.CryptoTypes import Hash256
from symbolchain.core.CryptoTypes import PrivateKey
from symbolchain.core.CryptoTypes import Signature, PublicKey
from symbolchain.core.facade.SymFacade import SymFacade

from . import ed25519, network
from .constants import Fees, FM, TransactionTypes, TransactionMetrics

logger = logging.getLogger(os.path.splitext(os.path.basename(__name__))[0])


class Dividers:
    dividers = {}

    def __iter__(self):
        for key in self.dividers:
            yield key

    def set(self, key, value):
        self.dividers[key] = value

    def get(self, key):
        return self.dividers.get(key, None)


# class objects as singleton
dividers = Dividers()


class Message(bytes):

    def __new__(cls, message: [str, bytes], is_encrypted: bool):
        if is_encrypted and not message:
            raise RuntimeError('Message payload cannot be empty for encrypted message')
        if len(message) > ed25519.SignClass.PLAIN_MESSAGE_SIZE:
            raise OverflowError(f'Message length cannot exceed {ed25519.SignClass.PLAIN_MESSAGE_SIZE} bytes. Current length: {len(message)}')
        # # translate into bytes if we sold a string
        if not isinstance(message, bytes):
            message = message.encode()
        return bytes.__new__(bytes, message)


class PlainMessage(bytes):

    def __new__(cls, message: [str, bytes]):
        message = Message(message, True)
        # add the message type code to the beginning of the byte sequence
        payload_message = int(0).to_bytes(1, byteorder='big') + message
        cls.size = len(payload_message)
        return bytes.__new__(PlainMessage, payload_message)


class EncryptMessage(bytes):

    def __new__(cls, sender_private_key: str, recipient_pub: str, message: str):
        #  https://docs.symbolplatform.com/concepts/transfer-transaction.html#encrypted-message
        message = Message(message, True)
        hex_encrypted_message = ed25519.Ed25519.encrypt(sender_private_key, recipient_pub, message)
        if len(hex_encrypted_message) > ed25519.SignClass.PLAIN_MESSAGE_SIZE:
            raise OverflowError(f'Encrypted message length cannot exceed {ed25519.SignClass.PLAIN_MESSAGE_SIZE} bytes. Current length: {len(hex_encrypted_message)}')
        payload_message = int(1).to_bytes(1, byteorder='big') + hex_encrypted_message
        cls.size = len(payload_message)
        return bytes.__new__(EncryptMessage, payload_message)


class Mosaic(tuple):

    def __new__(cls, mosaic_id: str, amount: float):
        cls.size = 16
        divisibility = Mosaic.get_divisibility(mosaic_id)
        if divisibility is None:
            raise ValueError(f'Failed to get divisibility from network')
        divider = 10 ** int(divisibility)
        return tuple.__new__(Mosaic, [int(mosaic_id, 16), int(amount * divider)])

    @staticmethod
    def get_divisibility(mosaic_id: str):
        if mosaic_id in dividers:
            return dividers.get(mosaic_id)
        else:
            divisibility = network.get_divisibility(mosaic_id)
            if divisibility is not None:
                dividers.set(mosaic_id, divisibility)
            return divisibility


class Transaction:
    # Size of transaction with empty message
    MIN_TRANSACTION_SIZE = 160
    XYM_ID = int('091F837E059AE13C', 16)

    def __init__(self):
        self.size = None
        self.max_fee = None

        self.network_type = network.get_node_network()
        self.timing = network.Timing(self.network_type)
        self.sym_facade = SymFacade(self.network_type)

    def create(self,
               pr_key: str,
               recipient_address: str,
               mosaics: [Mosaic, List[Mosaic]] = None,
               message: [PlainMessage, EncryptMessage, None] = None,
               fee_type: Fees = Fees.SLOWEST,
               deadline: [dict, None] = None) -> (Hash256, bytes):

        if deadline is None:
            deadline = {'minutes': 2}
        if mosaics is None:
            mosaics = []
        if not isinstance(mosaics, list):
            mosaics = [mosaics]

        if len(mosaics) > 1:
            for i, mosaic in enumerate(mosaics):
                if mosaic[0] == self.XYM_ID:
                    # Mosaic XYM should be in the first place in the list
                    mosaics.insert(0, mosaics.pop(i))

        key_pair = self.sym_facade.KeyPair(PrivateKey(unhexlify(pr_key)))

        deadline = self.timing.calc_deadline(**deadline)

        descriptor = {
            'type': 'transfer',
            'recipient_address': SymFacade.Address(recipient_address.replace('-', '')).bytes,
            'signer_public_key': key_pair.public_key,
            'mosaics': mosaics,
            'fee': self.max_fee,
            'deadline': deadline,
            'message': message if message is not None else b''
        }

        self.size = self.MIN_TRANSACTION_SIZE + descriptor['message'].size + sum(mosaic.size for mosaic in descriptor['mosaics'])
        self.max_fee = Transaction.calc_max_fee(self.size, fee_type)
        descriptor['fee'] = self.max_fee

        transaction = self.sym_facade.transaction_factory.create(descriptor)

        signature = self.sym_facade.sign_transaction(key_pair, transaction)
        entity_hash = Transaction.entity_hash_gen(signature, key_pair.public_key, transaction,
                                                  self.sym_facade.network.generation_hash_seed)

        payload_bytes = self.sym_facade.transaction_factory.attach_signature(transaction, signature)

        # print(transaction)
        # print(hexlify(transaction.serialize()))
        # print(answer.status_code, answer.text)
        logger.debug(f'Transaction hash: {entity_hash}')

        return entity_hash, payload_bytes

    @staticmethod
    def calc_max_fee(transaction_size: int, fee_type: Fees):
        # network fee multipliers
        nfm = network.get_fee_multipliers()
        if nfm is None:
            raise ValueError(f'Failed to get fee multipliers from network. Unable to calculate fee')
        # https://github.com/nemgrouplimited/symbol-desktop-wallet/blob/507d4694a0ff55b0b039be0b5d061b47b2386fde/src/services/TransactionCommand.ts#L200
        fast_fee_multiplier = nfm[FM.min] if nfm[FM.average] < nfm[FM.min] else nfm[FM.average]
        average_fee_multiplier = nfm[FM.min] + nfm[FM.average] * 0.65
        slow_fee_multiplier = nfm[FM.min] + nfm[FM.average] * 0.35
        slowest_fee_multiplier = nfm[FM.min]

        div = 1000000
        logger.debug(f'Fees.FAST.name: {fast_fee_multiplier * transaction_size / div}')
        logger.debug(f'Fees.AVERAGE.name: {average_fee_multiplier * transaction_size / div}')
        logger.debug(f'Fees.SLOW.name: {slow_fee_multiplier * transaction_size / div}')
        logger.debug(f'Fees.SLOWEST.name: {slowest_fee_multiplier * transaction_size / div}')

        fee_multiplier = None
        if fee_type == Fees.FAST:
            fee_multiplier = fast_fee_multiplier
        if fee_type == Fees.AVERAGE:
            fee_multiplier = average_fee_multiplier
        if fee_type == Fees.SLOW:
            fee_multiplier = slow_fee_multiplier
        if fee_type == Fees.SLOWEST:
            fee_multiplier = slowest_fee_multiplier
        if fee_type == Fees.ZERO:
            fee_multiplier = 0

        max_fee = int(fee_multiplier * transaction_size)
        # ограничение при получении при просчёте слишком высокой комисии
        # TODO более детально рассмотреть регулирование комисси для транзакций
        return max_fee

    @staticmethod
    def entity_hash_gen(signature: Signature, public_key: PublicKey, transaction, generation_hash: Hash256):
        # https://symbol-docs.netlify.app/concepts/transaction.html
        tr_sr = transaction.serialize()
        is_aggregate = transaction.type in [TransactionTypes.AGGREGATE_BONDED, TransactionTypes.AGGREGATE_COMPLETE]
        # TODO проверить правильность работы на агрегированных транзакциях
        if is_aggregate:
            raise RuntimeError('Working with aggregated transactions has not been tested !!!')
        if is_aggregate:
            transaction_body = tr_sr[
                               TransactionMetrics.TRANSACTION_HEADER_SIZE:TransactionMetrics.TRANSACTION_BODY_INDEX + 32]
        else:
            transaction_body = tr_sr[TransactionMetrics.TRANSACTION_HEADER_SIZE:]
        # https://symbol-docs.netlify.app/concepts/transaction.html#signing-a-transaction
        entity_hash_bytes = b''.join([signature.bytes, public_key.bytes, generation_hash.bytes, transaction_body])
        # entity_hash = Hash256(hashlib.sha3_256(entity_hash_bytes).digest())
        entity_hash = hashlib.sha3_256(entity_hash_bytes).hexdigest().upper()
        return entity_hash
