import abc
import logging
import os
from enum import Enum
from http import HTTPStatus
from typing import List, Union, Tuple

import stdiomask
from nempy.account import Account
from nempy.sym.constants import BlockchainStatuses

from .sym import api as sym
from .sym import network


logger = logging.getLogger(__name__)


class EngineStatusCode(Enum):
    INVALID_ACCOUNT_INFO = 'There is no information on the network for this account. '


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
    def send_tokens(self, recipient_address: str, mosaics: list[(str, float)], message: [str, bytes] = ''):
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

    def send_tokens(self,
                    recipient_address: str,
                    mosaics: List[Tuple[str, float]],
                    message: [str, bytes] = '',
                    is_encrypted=False,
                    password: str = '',
                    deadline: dict = None):
        mosaics = [sym.Mosaic(mosaic_id=mosaic[0], amount=mosaic[1]) for mosaic in mosaics]
        if is_encrypted:
            address_info = network.get_accounts_info(address=recipient_address)
            if not address_info:
                return EngineStatusCode.INVALID_ACCOUNT_INFO
            public_key = address_info['account']['publicKey']
            message = sym.EncryptMessage(self.account.decrypt(password).private_key, public_key, message)
        else:
            message = sym.PlainMessage(message)
        entity_hash, payload = self.transaction.create(pr_key=self.account.decrypt(password).private_key,
                                                       recipient_address=recipient_address,
                                                       mosaics=mosaics,
                                                       message=message,
                                                       deadline=deadline)
        is_sent = network.send_transaction(payload)
        return entity_hash if is_sent else None

    def check_status(self, is_logging):
        if self.account is None:
            return BlockchainStatuses.NOT_INITIALIZED
        return network.NodeSelector.health(self.node_selector.url)

    def get_balance(self, nem_address, test=False):
        amount = network.get_balance(nem_address)
        return amount

    @staticmethod
    def mosaic_humanization(mosaics: dict[str, float]):
        mosaics_ids = list(mosaics.keys())
        mosaic_names = network.get_mosaic_names(mosaics_ids)
        if mosaic_names is not None:
            mosaic_names = mosaic_names['mosaicNames']
            rf_mosaic_names = {mn.get('mosaicId'): mn.get('names')[0] for mn in mosaic_names if len(mn.get('names'))}
            named_mosaic = {rf_mosaic_names.get(m_id, m_id): mosaics[m_id] for m_id in mosaics_ids}
            return named_mosaic
        else:
            return mosaics

    @staticmethod
    def check_transaction_confirmation(transaction_hash):
        return network.check_transaction_state(transaction_hash)
