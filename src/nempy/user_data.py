import abc
import copy
import logging
import os
import pickle
from base64 import b64decode
from base64 import b64encode
from binascii import unhexlify
from enum import Enum
from hashlib import blake2b
from typing import Union, Dict, Optional

import bcrypt
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Util.Padding import unpad
from nempy.config import C
from nempy.sym.constants import NetworkType, AccountValidationState
from nempy.sym.ed25519 import check_address
from pydantic import BaseModel, validator, StrictStr, StrictBytes
from symbolchain.core.Bip32 import Bip32
from symbolchain.core.CryptoTypes import PrivateKey
from symbolchain.core.facade.SymFacade import SymFacade
from symbolchain.core.sym.KeyPair import KeyPair
from tabulate import tabulate

logger = logging.getLogger(__name__)


def encryption(password: str, data: bytes) -> bytes:
    key = blake2b(password.encode(), digest_size=16).hexdigest().encode()
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(data, AES.block_size))
    iv = b64encode(cipher.iv)
    ct = b64encode(ct_bytes)
    result = iv + ct
    return result


def decryption(password: str, encrypted_data: bytes) -> [bytes, None]:
    encrypted_data = encrypted_data.decode('utf-8')
    key = blake2b(password.encode(), digest_size=16).hexdigest().encode()
    try:
        iv = b64decode(encrypted_data[0:24])
        ct = b64decode(encrypted_data[24:])
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt
    except (ValueError, KeyError):
        return None


class GenerationType(Enum):
    MNEMONIC = 0
    PRIVATE_KEY = 1


class DecoderStatus(Enum):
    DECRYPTED = None
    NO_DATA = 'Missing data to decode'
    WRONG_DATA = 'Wrong data format, expected `bytes`'
    WRONG_PASS = 'Wrong password'


class UserData(BaseModel):
    name: Optional[str] = None
    network_type: NetworkType

    def __repr__(self, ):
        return f'<class `{type(self).__name__}`>'

    @abc.abstractmethod
    def __str__(self): pass

    def __eq__(self, other: 'UserData'):
        if other.dict() == self.dict():
            return True
        return False

    @classmethod
    @abc.abstractmethod
    def read(cls, path: str) -> 'UserData': pass

    @abc.abstractmethod
    def write(self, path: str): pass

    def serialize(self) -> bytes:
        serialized_data = pickle.dumps(self.dict())
        return serialized_data

    @classmethod
    def deserialize(cls, data) -> 'UserData':
        deserialized_date = pickle.loads(data)
        return cls(**deserialized_date)


class AccountData(UserData):
    address: StrictStr
    public_key: StrictStr
    private_key: Union[StrictStr, StrictBytes]
    path: Optional[StrictStr] = None
    mnemonic: Union[StrictStr, StrictBytes] = None
    profile: Optional[str] = None

    class Config:
        validate_assignment = True

    @validator('address')
    def validate_address(cls, address):
        address = address.replace('-', '')
        if (avs := check_address(address)) != AccountValidationState.OK:
            raise ValueError(avs.value)
        return address

    def __str__(self):
        prepare = list()
        for key, value in self.dict().items():
            if key == 'address':
                value = '-'.join(value[i:i + 6] for i in range(0, len(value), 6))
            if key == 'mnemonic' and not isinstance(value, bytes):
                positions = [pos for pos, char in enumerate(value) if char == ' ']
                value = C.OKBLUE + value[:positions[8]] + f'{C.END}\n' + C.OKBLUE + value[positions[8] + 1:positions[16]] + f'{C.END}\n' + C.OKBLUE + value[positions[16] + 1:] + C.END
            elif key == 'mnemonic' and isinstance(value, bytes):
                value = f'{C.OKBLUE}******* **** ********** ******* ***** *********** ******** *****{C.END}'
            if key == 'private_key' and isinstance(value, bytes):
                value = '*' * 64
            if key == 'private_key' and isinstance(value, str):
                value = C.OKBLUE + value + C.END
            if isinstance(value, NetworkType):
                value = value.name
            key = key.replace('_', ' ').title()
            prepare.append([key, value])
        account = f'Account - {self.name}'
        indent = (len(self.public_key) - len(account)) // 2
        account = C.INVERT + ' ' * indent + account + ' ' * indent + C.END
        table = tabulate(prepare, headers=['', f'{account}'], tablefmt='grid')
        return table

    @classmethod
    def create(cls, private_key: str, network_type: NetworkType) -> 'AccountData':
        private_key = private_key.upper()
        facade = SymFacade(network_type.value)
        key_pair = KeyPair(PrivateKey(unhexlify(private_key)))
        public_key = str(key_pair.public_key).upper()
        address = str(facade.network.public_key_to_address(key_pair.public_key)).upper()
        return cls(private_key=private_key, public_key=public_key, address=address, network_type=network_type)

    def decrypt(self, password: str) -> 'AccountData':
        if not isinstance(self.private_key, bytes):
            logger.error('Unencrypted account?')
            raise ValueError(DecoderStatus.WRONG_DATA.value)
        decrypted_account = copy.deepcopy(self)
        decrypted_key = decryption(password, self.private_key)
        if decrypted_key is None:
            logger.error(DecoderStatus.WRONG_PASS.value)
            raise ValueError(DecoderStatus.WRONG_PASS.value)
        decrypted_account.private_key = pickle.loads(decrypted_key)
        if decrypted_account.mnemonic is not None:
            decrypted_account.mnemonic = pickle.loads(decryption(password, self.mnemonic))
        return decrypted_account

    @classmethod
    def read(cls, path: str) -> Union['AccountData', DecoderStatus]:
        if not os.path.exists(path):
            logger.error(DecoderStatus.NO_DATA.value)
            return DecoderStatus.NO_DATA
        account = cls.deserialize(open(path, 'rb').read())
        return account

    def encrypt(self, password: str) -> 'AccountData':
        pickle_private_key = pickle.dumps(self.private_key)
        # encrypt the private key
        self.private_key = encryption(password=password, data=pickle_private_key)
        if self.mnemonic is not None:
            pickle_mnemonic = pickle.dumps(self.mnemonic)
            # encrypt the mnemonic
            self.mnemonic = encryption(password=password, data=pickle_mnemonic)
        return self

    def is_encrypted(self):
        return isinstance(self.private_key, bytes)

    def write(self, path: str):
        if not isinstance(self.private_key, bytes):
            raise ValueError('Account data is recorded unencrypted')
        os.makedirs(os.path.dirname(path), exist_ok=True)

        pickled_data = self.serialize()
        with open(path, 'wb') as opened_file:
            opened_file.write(pickled_data)
        logger.debug(f'Wallet saved along the way: {path}')

    @staticmethod
    def accounts_pool_by_mnemonic(network_type: NetworkType,
                                  bip32_coin_id: int,
                                  mnemonic: str) -> Dict[str, 'AccountData']:
        facade = SymFacade(network_type.value)

        bip = Bip32(facade.BIP32_CURVE_NAME)
        root_node = bip.from_mnemonic(mnemonic, '')
        accounts = {}
        for i in range(10):
            path = [44, bip32_coin_id, i, 0, 0]
            child_node = root_node.derive_path(path)
            child_key_pair = facade.bip32_node_to_key_pair(child_node)
            private_key = str(child_key_pair.private_key).upper()
            public_key = str(child_key_pair.public_key).upper()
            address = str(facade.network.public_key_to_address(child_key_pair.public_key)).upper()
            accounts[address] = AccountData(**{'address': address,
                                               'public_key': public_key,
                                               'private_key': private_key,
                                               'mnemonic': mnemonic,
                                               'path': f"m/44'/{path[1]}'/{path[2]}'/0'/0'",
                                               'network_type': network_type})
        return accounts


class ProfileData(UserData):
    pass_hash: StrictBytes

    def __str__(self):
        prepare = [[key.replace('_', ' ').title(), value]
                   for key, value in self.dict().items() if key not in ['network_type', 'pass_hash']]
        prepare.append(['Network Type', self.network_type.name])
        prepare.append(['Pass Hash', C.OKBLUE + '*' * len(self.pass_hash) + C.END])
        profile = f'Profile - {self.name}'
        indent = (len(self.pass_hash) - len(profile)) // 2
        profile = C.INVERT + ' ' * indent + profile + ' ' * indent + C.END

        table = tabulate(prepare, headers=['', f'{profile}'], tablefmt='grid')
        return table

    @classmethod
    def read(cls, path) -> 'ProfileData':
        with open(path, 'rb') as opened_file:
            deserialized = cls.deserialize(opened_file.read())
            return deserialized

    def write(self, path):
        pickled = self.serialize()
        with open(path, 'wb') as opened_file:
            opened_file.write(pickled)

    def check_pass(self, password: str) -> bool:
        """
        Verifies the password from the profile
        Args:
            password: verifiable password

        Returns:
            True if password confirmed or False if password is failed

        """
        if password is not None:
            if bcrypt.checkpw(password.encode('utf-8'), self.pass_hash):
                return True
            else:
                logger.error('Incorrect password')
                return False



