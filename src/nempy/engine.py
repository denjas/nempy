import abc
import logging
import os
from http import HTTPStatus

from nempy.account import Account

from .sym import api as sym
from .sym import network
from .sym.constants import BlockchainStatuses

logger = logging.getLogger(os.path.splitext(os.path.basename(__name__))[0])


class NEMEngine:
    account = None

    def __init__(self, url: str, account: Account):
        self.url = url
        self.account = account

    def __str__(self):
        return f'URL: {self.url}\nAddress: {self.account.address}\nPublic Key: {self.account.public_key}'

    def __iter__(self):
        yield 'url', self.url
        yield 'address', self.account.address
        yield 'public_key', self.account.public_key

    @abc.abstractmethod
    def send_tokens(self, recipient_address: str, mosaic_id, amount: float, message: [str, bytes] = ''):
        pass

    @abc.abstractmethod
    def check_status(self, is_logging):
        pass

    @abc.abstractmethod
    def get_balance(self, nem_address, test=False):
        pass


class XYMEngine(NEMEngine):

    def __init__(self, account: Account):
        self.node_selector = network.node_selector
        self.node_selector.network_type = account.network_type
        self.transaction = sym.Transaction()
        self.timing = self.transaction.timing
        super().__init__(self.node_selector.url, account)

    def send_tokens(self, recipient_address: str, mosaic_id: str, amount: float, message: [str, bytes] = ''):
        mosaic = sym.Mosaic(mosaic_id, amount=amount)
        message = sym.PlainMessage(message)
        entity_hash, payload = self.transaction.create(pr_key=self.account.decode(),
                                                       recipient_address=recipient_address,
                                                       mosaics=mosaic,
                                                       message=message)
        text, status_code = network.send_transaction(payload)
        if status_code != HTTPStatus.ACCEPTED:
            return text, status_code
        return entity_hash, status_code

    def check_status(self, is_logging):
        if self.account is None:
            return BlockchainStatuses.NOT_INITIALIZED
        return network.NodeSelector.health(self.node_selector.url)

    def get_balance(self, nem_address, test=False):
        amount = network.get_balance(nem_address)
        return amount

    @staticmethod
    def check_transaction_confirmation(transaction_hash):
        return network.check_transaction_state(transaction_hash)
