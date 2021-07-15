import abc
from binascii import unhexlify
from collections.abc import Callable
from http import HTTPStatus
from symbolchain.core.CryptoTypes import Hash256
from symbolchain.core.CryptoTypes import PrivateKey
from symbolchain.core.sym.KeyPair import KeyPair

from .sym import api as sym
from .sym import network
from .sym.constants import BlockchainStatuses, DecoderStatus


class NEMEngine:

    def __init__(self,
                 url: str,
                 decryptor: Callable[str, str],
                 wallet_path: str,
                 wallet_pass: str):
        self.url = url
        self.decryptor = decryptor
        self.wallet_path = wallet_path
        self.wallet_pass = wallet_pass

        self._private_key = self.get_private_key()
        self._public_key, self._address = self.build_public(self._private_key)

    def __str__(self):
        return f'URL: {self.url}\nAddress: {self._address}\nPublic Key: {self._public_key}'

    def __iter__(self):
        yield 'url', self.url
        yield 'address', self._address
        yield 'public_key', self._public_key

    @abc.abstractmethod
    def send_tokens(self, recipient_address: str, amount: float):
        pass

    @abc.abstractmethod
    def check_status(self, is_logging):
        pass

    @abc.abstractmethod
    def get_balance(self, nem_address, test=False):
        pass

    @abc.abstractmethod
    def build_public(self, private_key):
        pass

    @property
    def private_key(self):
        if self._private_key is None:
            self._private_key = self.get_private_key()
            self._public_key, self._address = self.build_public(self._private_key)
        return self._private_key

    @property
    def public_key(self):
        if self._public_key is None:
            self._private_key = self.get_private_key()
            self._public_key, self._address = self.build_public(self._private_key)
        return self._public_key

    @property
    def address(self):
        if self._address is None:
            self._private_key = self.get_private_key()
            self._public_key, self._address = self.build_public(self._private_key)
        return self._address

    def get_private_key(self):
        private_key = self.decryptor(self.wallet_path, self.wallet_pass)
        if isinstance(private_key, DecoderStatus):
            if private_key == DecoderStatus.WRONG_PASS:
                print(DecoderStatus.WRONG_PASS.value + ' for wallet')
                return None
            elif private_key == DecoderStatus.NO_DATA:
                print(DecoderStatus.NO_DATA.value + ' wallet')
                return None
        else:
            return private_key


# class XEMEngine(NEMEngine):
#
#     def __init__(self, url: str, wallet_path: str, wallet_pass: str, decryptor: Callable[str, str], namespace: str, mosaic_name: str):
#         self.decryptor: Callable[str, str] = decryptor
#         self.mosaic_name = mosaic_name
#         self.namespace = namespace
#         self.token = f'{namespace}:{mosaic_name}'
#         super().__init__(url, decryptor=decryptor, wallet_path=wallet_path, wallet_pass=wallet_pass)
#
#     def build_public(self, private_key):
#         public_key = address = None
#         if private_key is not None:
#             ed25519 = Ed25519(main_net=False)
#             public_key = ed25519.public_key(private_key).decode("utf-8")
#             address = ed25519.get_address(public_key).decode("utf-8")
#         return public_key, address
#
#     def send_tokens(self, recipient_address: str, amount: float):
#         status_code, message = xem.send_token(self.url, recipient_address,
#                                               self.private_key,
#                                               self._public_key,
#                                               self.namespace,
#                                               self.mosaic_name,
#                                               amount)
#         return message, status_code
#
#     def check_status(self, is_logging):
#         if self.private_key is None:
#             return NISStatuses.S10
#         nis_status = xem.check_status(self.url, is_logging)
#         return nis_status
#
#     def get_balance(self, nem_address, test=False):
#         amount, status_code = xem.get_balance(self.url, nem_address, test)
#         return amount, status_code
#
#     def check_transaction_confirmation(self, nem_address, transaction_hash):
#         return xem.check_transaction_confirmation(self.url,  nem_address, transaction_hash)


class XYMEngine(NEMEngine):

    def __init__(self, wallet_path: str, wallet_pass: str, decryptor: Callable[str, str], namespace: str, mosaic_name: str, mosaic_id: str):
        self.mosaic_name = mosaic_name
        self.token = f'{namespace}:{mosaic_name}'
        self.mosaic_id = mosaic_id
        self.node_selector = network.node_selector
        self.transaction = sym.Transaction()
        self.network_type = self.transaction.network_type
        self.timing = self.transaction.timing
        super().__init__(self.node_selector.url, decryptor=decryptor, wallet_path=wallet_path, wallet_pass=wallet_pass)

    def build_public(self, private_key):
        public_key = address = None
        if private_key is not None:
            key_pair = KeyPair(PrivateKey(unhexlify(private_key)))
            public_key = str(key_pair.public_key)
            address = str(self.transaction.sym_facade.network.public_key_to_address(Hash256(public_key)))
        return public_key, address

    def send_tokens(self, recipient_address: str, amount: float, message: [str, bytes] = ''):
        mosaic = sym.Mosaic(self.mosaic_id, amount=amount)
        message = sym.PlainMessage(message)
        entity_hash, payload = self.transaction.create(pr_key=self.private_key,
                                                       recipient_address=recipient_address,
                                                       mosaics=mosaic,
                                                       message=message)
        text, status_code = network.send_transaction(payload)
        if status_code != HTTPStatus.ACCEPTED:
            return text, status_code
        return entity_hash, status_code

    def check_status(self, is_logging):
        if self.private_key is None:
            return BlockchainStatuses.NOT_INITIALIZED
        return network.NodeSelector.health(self.node_selector.url)

    def get_balance(self, nem_address, test=False):
        amount, status_code = network.get_balance(nem_address)
        return amount, status_code

    @staticmethod
    def check_transaction_confirmation(transaction_hash):
        return network.check_transaction_confirmation(transaction_hash)
