import abc
import asyncio
import logging
from enum import Enum
from typing import List, Tuple, Union, Dict, Optional

from symbolchain.core.facade.SymbolFacade import SymbolFacade, PublicKey

from nempy.sym.constants import BlockchainStatuses, Fees, TransactionStatus
from nempy.user_data import AccountData
from .sym import api as sym
from .sym import network
from .sym.node_selector import node_selector, NodeSelector


logger = logging.getLogger(__name__)


class EngineStatusCode(Enum):
    """Contains status for sending transactions"""

    INVALID_ACCOUNT_INFO = "There is no information on the network for this account."
    """There is no information on the network for this account."""
    ANNOUNCE_ERROR = "Transaction announce error"
    """Transaction announce error"""
    ACCEPTED = "Request accepted, processing continues off-line"
    """Request accepted"""
    INVALID_PASSWORD = "Incorrect or not set account password"
    """Wrong account password"""


class NEMEngine:
    account: Optional[AccountData] = None
    _password: Optional[str] = None
    _is_active: bool = False  # Indicates whether the account can make outgoing transactions with founds

    def __init__(self, account: AccountData, password: Optional[str] = None):
        self.account = account
        if not self.account.is_encrypted():
            msg = 'Only work with encrypted accounts is supported'
            logger.error('msg')
            raise RuntimeError(msg)
        if password is not None:
            self.decrypt(password)

    def __str__(self):
        return f"Address: {self.account.address}\nPublic Key: {self.account.public_key}"

    def __iter__(self):
        yield "address", self.account.address
        yield "public_key", self.account.public_key

    def decrypt(self, password: str):
        self._password = password
        if self.account.is_encrypted():
            self.account = self.account.decrypt(self._password)
            self._is_active = True
        else:
            logger.warning('Account does not need decryption')


    @property
    def is_active(self):
        return self._is_active

    @abc.abstractmethod
    async def send_tokens(
        self,
        recipient_address: str,
        mosaics: List[Tuple[str, float]],
        message: Union[str, bytes] = "",
        is_encrypted=False,
        deadline: Optional[dict] = None,
    ):
        raise NotImplementedError

    @abc.abstractmethod
    async def check_status(self):
        raise NotImplementedError

    @abc.abstractmethod
    async def get_balance(self, nem_address, test=False):
        raise NotImplementedError


class XYMEngine(NEMEngine):
    """
    An interface that combines a user account of the transaction and work with the network
    """
    def __init__(self, account: AccountData, password: Optional[str] = None):
        """
        Inits SampleClass with AccountData

        Parameters
        ----------
        account
            User account data
        password
            Account password
        """
        self.transaction = sym.Transaction()
        super().__init__(account, password)

    async def send_tokens(
        self,
        recipient_address: str,
        mosaics: List[Tuple[str, float]],
        message: Union[str, bytes] = "",
        is_encrypted=False,
        fee_type: Fees = Fees.SLOWEST,
        deadline: Optional[Dict[str, float]] = None,
    ) -> Tuple[Optional[str], EngineStatusCode]:
        """
        Allows you to send funds or a message to the specified account

        Parameters
        ----------
        recipient_address
            Beneficiary address of funds or message
        mosaics
            Funds in the form of mosaics
        message
            Plain or encrypted messages
        is_encrypted
            Indication for encrypting a message or sending in plain text
        fee_type
            One of the types of fee that affects the speed and cost of
            confirming a transaction by the blockchain network. The following types are available:
            .. admonition::
                ZERO | SLOWEST | SLOW | AVERAGE | FAST
        deadline
            A transaction has a time window to be accepted before it reaches its deadline.
            The transaction expires when the deadline is reached and all the nodes reject the transaction.
            Maximum expiration time 6 hours. The default is 2 minutes. To install a custom deadline,
            pass a dictionary specifying the type / types and their duration. For example:
        ```py
        {
            "minutes": 2.0,
            "seconds": 30.0
        }
        ```
         Which corresponds to 2 minutes and 30 seconds. Keys available:
        .. admonition::
            days | seconds | milliseconds | minutes | hours | weeks
        Returns
        -------
        A hash of the transaction or None and status
        Notes
        -----
        **_Attention!_**
        The example below is intended to demonstrate ease of use, but it is **_not secure_**!
        Use this code only on the `NetworkType.TEST_NET`

        Example:
        ```py
        from nempy.user_data import AccountData
        from nempy.engine import XYMEngine
        from nempy.sym.network import NetworkType
        from nempy.sym.constants import Fees

        PRIVATE_KEY = '<YOUR_PRIVATE_KEY>'
        PASSWORD = '<YOUR_PASS>'
        account = AccountData.create(PRIVATE_KEY, NetworkType.TEST_NET).encrypt(PASSWORD)

        engine = XYMEngine(account)
        entity_hash, status = engine.send_tokens(recipient_address='TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ',
                                                 mosaics=[('@symbol.xym', 0.1), ],
                                                 message='Hallo NEM!',
                                                 password=PASSWORD,
                                                 fee_type=Fees.SLOWEST)
        print(status.name, status.value)
        ```
        """
        if not self._is_active:
            logger.error('Unable to send funds without a password set for the account')
            return None, EngineStatusCode.INVALID_PASSWORD
        recipient_address = recipient_address.replace("-", "")
        mosaics = [
            await sym.Mosaic.create(mosaic_id=mosaic[0], amount=mosaic[1]) for mosaic in mosaics
        ]
        if is_encrypted:
            address_info = await network.get_accounts_info(address=recipient_address)
            if address_info is None:
                return None, EngineStatusCode.INVALID_ACCOUNT_INFO
            public_key = address_info["account"]["publicKey"]
            message = sym.EncryptMessage(
                message, self.account.private_key, public_key
            )
        else:
            message = sym.PlainMessage(message)
        entity_hash, payload = await self.transaction.create(
            pr_key=self.account.private_key,
            recipient_address=recipient_address,
            mosaics=mosaics,
            message=message,
            deadline=deadline,
            fee_type=fee_type,
        )
        is_sent = await network.send_transaction(payload)
        if is_sent:
            return entity_hash, EngineStatusCode.ACCEPTED
        return None, EngineStatusCode.ANNOUNCE_ERROR

    async def check_status(self) -> BlockchainStatuses:
        """ Checking the status of a blockchain node

        Returns:
            BlockchainStatuses with detailed status description
        """
        if self.account is None:
            return BlockchainStatuses.NOT_INITIALIZED
        return await NodeSelector.health(await node_selector.url)

    async def get_balance(self, nem_address: Optional[str] = None, humanization: bool = False) -> Dict[str, float]:
        """
        Gets account balance

        Parameters
        ----------
        nem_address
            If the account address is specified, then the balance of this account is returned.
            Otherwise, the balance of the current account is returned
        humanization
            Specifies whether to translate mosaic IDs into friendly names (linked namespaces)
        Returns
        -------
        Dict[str, float]
            A dictionary with the name or identifier of the mosaic and its amount . For example:
        ```py
        {
            "symbol.xym": "100.00"
        }
        ```
        """
        if nem_address is None:
            nem_address = self.account.address
        amount = await network.get_balance(nem_address)
        if humanization:
            amount = await XYMEngine.mosaic_humanization(amount)
        return amount

    @staticmethod
    async def mosaic_humanization(mosaics: Dict[str, float]) -> Dict[str, float]:
        """Translates mosaic IDs into friendly names (linked namespaces)

        Parameters
        ----------
        mosaics
            A dictionary in which the key is the identifier of the mosaic and the value is its number. For example:
        ```py
        {
            "091F837E059AE13C": "100.00"
        }
        ```
        Returns
        -------
        Dict[str, float]
            A dictionary with the name or identifier of the mosaic and its amount . For example:
        ```py
        {
            "symbol.xym": "100.00"
        }
        ```

        """
        mosaics_ids = list(mosaics.keys())
        mosaic_names: dict = await network.get_mosaic_names(mosaics_ids)
        if mosaic_names is not None:
            mosaic_names = mosaic_names["mosaicNames"]
            rf_mosaic_names = {
                mn.get("mosaicId"): mn.get("names")[0]
                for mn in mosaic_names
                if len(mn.get("names"))
            }
            named_mosaic = {
                rf_mosaic_names.get(m_id, m_id): mosaics[m_id] for m_id in mosaics_ids
            }
            return named_mosaic
        else:
            return mosaics

    @staticmethod
    async def check_transaction_confirmation(transaction_hash) -> TransactionStatus:
        """
        Determines the current status of a transaction by its hash

        Parameters
        ----------
        transaction_hash
            Transaction hash as string hexadecimal representation

        Returns
        -------
        TransactionStatus
            One of the transaction statuses
        ```py
        TransactionStatus.NOT_FOUND
        TransactionStatus.UNCONFIRMED_ADDED
        TransactionStatus.CONFIRMED_ADDED
        TransactionStatus.PARTIAL_ADDED
        ```
        """
        return await network.check_transaction_state(transaction_hash)

    @staticmethod
    async def account_bu_pub_key(public_key: str):
        sym_facade: SymbolFacade = SymbolFacade(await node_selector.network_type)
        address = str(sym_facade.network.public_key_to_address(PublicKey(public_key))).upper()
        return address

