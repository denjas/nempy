import os
import pickle
import logging

from base64 import b64decode
from base64 import b64encode
from enum import Enum
from hashlib import blake2b

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from Crypto.Util.Padding import unpad
from tabulate import tabulate


class Account:
    name = None
    address = None
    public_key = None
    private_key = None
    path = None
    mnemonic = None
    password = None
    node_url = None

    def __init__(self, account: dict):
        [setattr(self, key, value) for key, value in account.items()]
        if self.private_key is None:
            raise AttributeError('The private key is required for the account')

    def __str__(self):
        prepare = list()
        prepare.append(['Name', self.name])
        prepare.append(['Address', self.address])
        prepare.append(['Public Key ', self.public_key])
        prepare.append(['Private Key', self.private_key])
        prepare.append(['Path', self.path])
        positions = [pos for pos, char in enumerate(self.mnemonic) if char == ' ']
        mnemonic = self.mnemonic[:positions[8]] + '\n' + self.mnemonic[positions[8] + 1:positions[16]] + '\n' + self.mnemonic[positions[16] + 1:]
        prepare.append(['Mnemonic', mnemonic])
        prepare.append(['Password', self.password])
        prepare.append(['URL', self.node_url])
        table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
        return table

    def __repr__(self):
        prepare = list()
        prepare.append(['Name', self.name])
        prepare.append(['Address', self.address])
        prepare.append(['Public Key ',  self.public_key])
        prepare.append(['Private Key', ''.join('*' for e in self.private_key if e.isalnum())])
        prepare.append(['Path', ''.join('*' for e in self.path if e.isalnum())])
        prepare.append(['Mnemonic', '****** ***** ****** ***** ***** ******* ******** ***** *********'])
        prepare.append(['Password', ''.join('*' for e in self.password if e.isalnum())])
        prepare.append(['URL', self.node_url])
        table = tabulate(prepare, headers=['Property', 'Value'], tablefmt='grid')
        return table

    def serialize(self):
        return pickle.dumps(self.__dict__, fix_imports=False)

    @staticmethod
    def deserialize(data):
        des_date = pickle.loads(data, fix_imports=False)
        return Account(des_date)


class DecoderStatus(Enum):
    DECRYPTED = None
    NO_DATA = 'Missing data to decode'
    WRONG_PASS = 'Wrong password'


def encryption(password: str, data: bytes) -> str:
    key = blake2b(password.encode(), digest_size=16).hexdigest().encode()
    cipher = AES.new(key, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(data, AES.block_size))
    iv = b64encode(cipher.iv).decode('utf-8')
    ct = b64encode(ct_bytes).decode('utf-8')
    result = iv + ct
    return result


def decryption(password: str, encrypted_data: str) -> [bytes, None]:
    key = blake2b(password.encode(), digest_size=16).hexdigest().encode()
    try:
        iv = b64decode(encrypted_data[0:24])
        ct = b64decode(encrypted_data[24:])
        cipher = AES.new(key, AES.MODE_CBC, iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size)
        return pt
    except (ValueError, KeyError):
        return None


def read_account(path: str, password: str) -> [Account, DecoderStatus]:
    if not os.path.exists(path):
        logging.error(DecoderStatus.NO_DATA.value)
        return DecoderStatus.NO_DATA
    encrypted_data = open(path, 'r').read()
    decrypted = decryption(password, encrypted_data)
    if decrypted is None:
        logging.error(DecoderStatus.WRONG_PASS.value)
        return DecoderStatus.WRONG_PASS
    decrypted_account = Account.deserialize(decrypted)
    return decrypted_account


def write_account(path, password, account: Account):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pickled_data = account.serialize()
    enc_data = encryption(password=password, data=pickled_data)
    with open(path, 'w+') as opened_file:
        opened_file.write(enc_data)
    logging.debug(f'Wallet saved along the way: {path}')


