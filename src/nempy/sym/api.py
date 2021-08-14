import hashlib
import logging
import re

from binascii import unhexlify
from typing import Union, Optional, List, Tuple

from symbolchain.core.CryptoTypes import Hash256
from symbolchain.core.CryptoTypes import PrivateKey
from symbolchain.core.CryptoTypes import Signature, PublicKey
from symbolchain.core.facade.SymFacade import SymFacade
from symbolchain.core.sym.IdGenerator import generate_namespace_id

from . import ed25519, network
from .constants import Fees, FM, TransactionTypes, TransactionMetrics, HexSequenceSizes, NetworkType

logger = logging.getLogger(__name__)


class Dividers:
    """Accumulates information about dividers for offline work"""
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
    """Base class for messages, does the necessary checks"""
    def __new__(cls, message: Union[str, bytes], is_encrypted: bool) -> bytes:
        if is_encrypted and not message:
            raise RuntimeError('Message payload cannot be empty for encrypted message')
        if len(message) > ed25519.SignClass.PLAIN_MESSAGE_SIZE:
            raise OverflowError(f'Message length cannot exceed {ed25519.SignClass.PLAIN_MESSAGE_SIZE} bytes. Current length: {len(message)}')
        # # translate into bytes if we sold a string
        if not isinstance(message, bytes):
            message = message.encode()
        return bytes.__new__(bytes, message)


class PlainMessage(bytes):
    """Plain messages
    Returns the message as bytes with the necessary flags at the beginning"""
    def __new__(cls, message: Union[str, bytes]):
        message = Message(message, False)
        # add the message type code to the beginning of the byte sequence
        if message:
            payload_message = b'\x00' + message
        else:
            payload_message = message
        cls.size = len(payload_message)
        return bytes.__new__(PlainMessage, payload_message)


class EncryptMessage(bytes):
    """Encrypted messages requiring additional arguments
    Returns the message as encrypted bytes with the necessary flags at the beginning"""
    def __new__(cls, message: Union[str, bytes], sender_private_key: str, recipient_pub: str):
        #  https://docs.symbolplatform.com/concepts/transfer-transaction.html#encrypted-message
        message = Message(message, True)
        hex_encrypted_message = ed25519.Ed25519.encrypt(sender_private_key, recipient_pub, message)
        if len(hex_encrypted_message) > ed25519.SignClass.PLAIN_MESSAGE_SIZE:
            raise OverflowError(f'Encrypted message length cannot exceed {ed25519.SignClass.PLAIN_MESSAGE_SIZE} bytes. Current length: {len(hex_encrypted_message)}')
        payload_message = b'\x01' + hex_encrypted_message
        cls.size = len(payload_message)
        return bytes.__new__(EncryptMessage, payload_message)


class Namespace(str):
    """Building namespace hashes"""
    def __new__(cls, name: str) -> str:
        ns_sns = name.split('.')
        if len(ns_sns) > 3:
            raise ValueError(f'Invalid name for namespace `{name}` - namespaces can have up to 3 levels—a namespace and its two levels of subnamespace domains')
        namespace_id = 0
        for ns in ns_sns:
            result = re.match('^[a-z0-9][a-z0-9_-]+$', ns)
            if len(ns) > 64:
                raise ValueError(f'Invalid name for namespace `{name}` - maximum length of 64 characters')
            if result is None:
                raise ValueError(f'Invalid name for namespace `{name}` - start with number or letter allowed characters are a, b, c, …, z, 0, 1, 2, …, 9, _ , -')
            namespace_id = generate_namespace_id(ns, namespace_id)
        return str.__new__(Namespace, hex(namespace_id).upper()[2:])


class Mosaic(tuple):
    """Builds a mosaic. Gets additional data by divisor and mosaic ID by name"""
    def __new__(cls, mosaic_id: str, amount: float):
        cls.size = 16
        if mosaic_id.startswith('@'):
            mosaic_id = Mosaic.alias_to_mosaic_id(mosaic_id[1:])
        divisibility = Mosaic.get_divisibility(mosaic_id)
        if divisibility is None:
            raise ValueError(f'Failed to get divisibility from network')
        divider = 10 ** int(divisibility)
        return tuple.__new__(Mosaic, [int(mosaic_id, 16), int(amount * divider)])

    @staticmethod
    def get_divisibility(mosaic_id: str):
        """Gets the divisibility by mosaic ID"""
        if mosaic_id in dividers:
            return dividers.get(mosaic_id)
        else:
            divisibility = network.get_divisibility(mosaic_id)
            if divisibility is not None:
                dividers.set(mosaic_id, divisibility)
            return divisibility

    @staticmethod
    def alias_to_mosaic_id(alis):
        """Translates aliases to mosaic id"""
        namespace_id = Namespace(alis)
        namespace_info = network.get_namespace_info(namespace_id)
        if namespace_info is None or namespace_info == {}:
            raise ValueError(f'Failed to get mosaic_id by name `{alis}`')
        mosaic_id = namespace_info['namespace']['alias']['mosaicId']
        return mosaic_id


class Transaction:
    """Class for working with transfer transactions"""

    MIN_TRANSACTION_SIZE = 160  #: Size of transaction with empty message

    def __init__(self):
        self.size: int = -1  #: transaction size
        self.max_fee: int = -1  #: The maximum amount of network currency that the sender of the transaction is willing to pay to get the transaction accepted

        self.network_type: NetworkType = network.get_node_network()
        self.timing: network.Timing = network.Timing(self.network_type)
        self.sym_facade: SymFacade = SymFacade(self.network_type.value)

    def create(self,
               pr_key: str,
               recipient_address: str,
               mosaics: Union[Mosaic, List[Mosaic], None] = None,
               message: Union[PlainMessage, EncryptMessage] = PlainMessage(''),
               fee_type: Fees = Fees.SLOWEST,
               deadline: Optional[dict] = None) -> Tuple[str, bytes]:
        """Create a transaction"""

        if deadline is None:
            deadline = {'minutes': 2}
        if mosaics is None:
            mosaics = []
        if not isinstance(mosaics, list) and isinstance(mosaics, Mosaic):
            mosaics = [mosaics]
        if not isinstance(mosaics, list) and not isinstance(mosaics, Mosaic):
            raise ValueError(f'Expected type of `Mosaic` for mosaic got `{type(mosaics)}`')
        if len(mosaics) > 1:
            # sorting mosaic by ID (blockchain requirement)
            mosaics = sorted(mosaics, key=lambda tup: tup[0])

        key_pair = self.sym_facade.KeyPair(PrivateKey(unhexlify(pr_key)))

        deadline = self.timing.calc_deadline(**deadline)

        descriptor = {
            'type': 'transfer',
            'recipient_address': SymFacade.Address(recipient_address.replace('-', '')).bytes,
            'signer_public_key': key_pair.public_key,
            'mosaics': mosaics,
            'fee': self.max_fee,
            'deadline': deadline,
            'message': message
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
        """Calculation of the transaction fee"""
        # network fee multipliers
        nfm = network.get_fee_multipliers()
        if nfm is None:
            raise ValueError(f'Failed to get fee multipliers from network. Unable to calculate fee')
        # https://github.com/nemgrouplimited/symbol-desktop-wallet/blob/507d4694a0ff55b0b039be0b5d061b47b2386fde/src/services/TransactionCommand.ts#L200
        fast_fee_multiplier = nfm[FM.min] if nfm[FM.average] < nfm[FM.min] else nfm[FM.average]
        average_fee_multiplier = nfm[FM.min] + nfm[FM.average] * 0.65
        slow_fee_multiplier = nfm[FM.min] + nfm[FM.average] * 0.35
        slowest_fee_multiplier = nfm[FM.min]
        # sometimes the average is less than fast
        slowest_fee_multiplier, slow_fee_multiplier, average_fee_multiplier, fast_fee_multiplier = sorted(
            [slowest_fee_multiplier, slow_fee_multiplier, average_fee_multiplier, fast_fee_multiplier])

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
        # TODO whether restrictions are needed for too high a fee, can this be?
        return max_fee

    @staticmethod
    def entity_hash_gen(signature: Signature, public_key: PublicKey, transaction, generation_hash: Hash256):
        """Calculate the transaction hash by applying SHA3-256 hashing algorithm to the first 32 bytes of signature,
        the signer public key, nemesis block generation hash, and the remaining transaction payload."""
        # https://symbol-docs.netlify.app/concepts/transaction.html
        tr_sr = transaction.serialize()
        is_aggregate = transaction.type in [TransactionTypes.AGGREGATE_BONDED, TransactionTypes.AGGREGATE_COMPLETE]
        # TODO check if it works correctly on aggregated transactions
        if is_aggregate:
            raise NotImplementedError('Working with aggregated transactions has not been tested !!!')
            transaction_body = tr_sr[TransactionMetrics.TRANSACTION_HEADER_SIZE:TransactionMetrics.TRANSACTION_BODY_INDEX + 32]
        else:
            transaction_body = tr_sr[TransactionMetrics.TRANSACTION_HEADER_SIZE:]
        # https://symbol-docs.netlify.app/concepts/transaction.html#signing-a-transaction
        entity_hash_bytes = b''.join([signature.bytes, public_key.bytes, generation_hash.bytes, transaction_body])
        # entity_hash = Hash256(hashlib.sha3_256(entity_hash_bytes).digest())
        entity_hash = hashlib.sha3_256(entity_hash_bytes).hexdigest().upper()
        return entity_hash
