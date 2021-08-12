#!/usr/bin/env python3

"""
this code is a cleaned version of http://ed25519.cr.yp.to/python/ed25519.py for python3

code released under the terms of the GNU Public License v3, copyleft 2015 yoochan

http://code.activestate.com/recipes/579102-ed25519/
"""

import collections
import hashlib
import logging
import os
from base64 import b32decode, b32encode
from binascii import hexlify, unhexlify
from operator import getitem, methodcaller

from Crypto.Cipher import AES
from Cryptodome.Hash import RIPEMD160
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from .constants import HexSequenceSizes, AccountValidationState

logger = logging.getLogger(__name__)

Point = collections.namedtuple('Point', ['x', 'y'])

key_mask = int.from_bytes(b'\x3F' + b'\xFF' * 30 + b'\xF8', 'big', signed=False)

b = 256
q = 2 ** 255 - 19

hash_len = 32


def check_hex(hex_sequence: str, size: HexSequenceSizes):
    try:
        int(hex_sequence, 16)
    except ValueError:
        return False
    if len(hex_sequence) == size:
        return True
    return False


def check_address(address: str) -> AccountValidationState:
    if len(address) != 39:
        return AccountValidationState.LENGTH_FAILURE
    try:
        raw = b32decode((address + '=').encode())
        header, ripe, checksum = raw[:1], raw[1:1 + 20], raw[1 + 20:]
        f_body = (checksum == hashlib.sha3_256(header + ripe).digest()[0:3])
    except Exception as e:
        logger.exception(e)
        return AccountValidationState.CHECKSUM_FAILURE
    return AccountValidationState.OK if f_body else AccountValidationState.CHECKSUM_FAILURE


class Ed25519:
    def __init__(self, main_net=True):
        self.l = 2 ** 252 + 27742317777372353535851937790883648493
        self.d = -121665 * self.inverse(121666)
        self.i = pow(2, (q - 1) // 4, q)
        self.B = self.point(4 * self.inverse(5))
        self.main_net = main_net

    @staticmethod
    def to_hash(m):
        return hashlib.sha512(m).digest()
        # return hashlib.sha512(m).digest()

    def from_bytes(self, h):
        """ pick 32 bytes, return a 256 bit int """
        return int.from_bytes(h[0:b // 8], 'little', signed=False)

    def to_bytes(self, k):
        return k.to_bytes(b // 8, 'little', signed=False)

    def as_key(self, h):
        return 2 ** (b - 2) + (self.from_bytes(h) & key_mask)

    def secret_key(self, seed=None):
        """ pick a random secret key """
        if seed is None:
            m = os.urandom(1024)
        else:
            if isinstance(seed, str):
                m = seed.encode('utf8')
            else:
                m = seed
        h = self.to_hash(m)
        k = self.as_key(h)
        return hexlify(self.to_bytes(k)).upper()

    def public_key(self, sk):
        """ compute the public key from the secret one """
        h = self.to_hash(unhexlify(sk))
        a = self.as_key(h)
        c = self.outer(self.B, a)
        return hexlify(self.point_to_bytes(c)).upper()

    @staticmethod
    def get_address(public_key, main_net=False, prefix=None):
        """ compute the nem-py address from the public one """
        public_key = unhexlify(Ed25519.str2bytes(public_key))
        if isinstance(public_key, str):
            public_key = unhexlify(public_key.encode())
        assert len(public_key) == 32, 'PK is 32bytes {}'.format(len(public_key))
        k = hashlib.sha3_256(public_key).digest()
        ripe = RIPEMD160.new(k).digest()
        if prefix is None:
            body = (b"\x68" if main_net else b"\x98") + ripe
        else:
            assert isinstance(prefix, bytes), 'Set prefix 1 bytes'
            body = prefix + ripe
        checksum = hashlib.sha3_256(body).digest()[0:3]
        return b32encode(body + checksum).decode()[0:-1]

    def inverse(self, x):
        return pow(x, q - 2, q)

    @staticmethod
    def str2bytes(string):
        return string if isinstance(string, bytes) else string.encode('utf8')

    @staticmethod
    def encrypt(private_key, public_key, message):
        _message = Ed25519.str2bytes(message)
        _sk = Ed25519.str2bytes(private_key)
        _pk = Ed25519.str2bytes(public_key)

        ecc = SignClass()
        encrypted_message = ecc.encrypt(unhexlify(_sk), unhexlify(_pk), _message)
        return hexlify(encrypted_message)

    @staticmethod
    def decrypt(private_key, public_key, msg_hex):
        _msg_hex = Ed25519.str2bytes(msg_hex)
        _sk = Ed25519.str2bytes(private_key)
        _pk = Ed25519.str2bytes(public_key)

        ecc = SignClass()
        raw_msg = ecc.decrypt(unhexlify(_sk), unhexlify(_pk), unhexlify(_msg_hex))
        return raw_msg

    def recover(self, y):
        """ given a value y, recover the preimage x """
        p = (y * y - 1) * self.inverse(self.d * y * y + 1)
        x = pow(p, (q + 3) // 8, q)
        if (x * x - p) % q != 0:
            x = (x * self.i) % q
        if x % 2 != 0:
            x = q - x
        return x

    def point(self, y):
        """ given a value y, recover x and return the corresponding P(x, y) """
        return Point(self.recover(y) % q, y % q)

    def is_on_curve(self, P):
        return (P.y * P.y - P.x * P.x - 1 - self.d * P.x * P.x * P.y * P.y) % q == 0

    def inner(self, P, Q):
        """ inner product on the curve, between two points """
        x = (P.x * Q.y + Q.x * P.y) * self.inverse(1 + self.d * P.x * Q.x * P.y * Q.y)
        y = (P.y * Q.y + P.x * Q.x) * self.inverse(1 - self.d * P.x * Q.x * P.y * Q.y)
        return Point(x % q, y % q)

    def outer(self, P, n):
        """ outer product on the curve, between a point and a scalar """
        if n == 0:
            return Point(0, 1)
        Q = self.outer(P, n // 2)
        Q = self.inner(Q, Q)
        if n & 1:
            Q = self.inner(Q, P)
        return Q

    def point_to_bytes(self, P):
        return (P.y + ((P.x & 1) << 255)).to_bytes(b // 8, 'little')


class SignClass:
    l = 2 ** 252 + 27742317777372353535851937790883648493
    ident = (0, 1, 1, 0)
    Bpow = []
    MAC_TAG_SIZE = 16
    IV_SIZE = 12
    PLAIN_MESSAGE_SIZE = 1023

    def __init__(self):
        self.d = -121665 * self.inv(121666) % q
        self.By = 4 * self.inv(5)
        self.Bx = self.xrecover(self.By)
        self.B = (self.Bx % q, self.By % q, 1, (self.Bx * self.By) % q)
        self.I = pow(2, (q - 1) // 4, q)
        self.int2byte = methodcaller("to_bytes", 1, "big")
        self.Bpow = self.make_Bpow()

    def make_Bpow(self):
        P = self.B
        Bpow = []
        for i in range(253):
            Bpow.append(P)
            P = self.edwards_double(P)

        return Bpow

    @staticmethod
    def to_hash(m):
        return hashlib.sha512(m).digest()


    def inv(self, z):
        """
        $= z^{-1} \\ mod q$, for z != 0
        """
        # Adapted from curve25519_athlon.c in djb's Curve25519.
        z2 = z * z % q  # 2
        z9 = self.pow2(z2, 2) * z % q  # 9
        z11 = z9 * z2 % q  # 11
        z2_5_0 = (z11 * z11) % q * z9 % q  # 31 == 2^5 - 2^0
        z2_10_0 = self.pow2(z2_5_0, 5) * z2_5_0 % q  # 2^10 - 2^0
        z2_20_0 = self.pow2(z2_10_0, 10) * z2_10_0 % q  # ...
        z2_40_0 = self.pow2(z2_20_0, 20) * z2_20_0 % q
        z2_50_0 = self.pow2(z2_40_0, 10) * z2_10_0 % q
        z2_100_0 = self.pow2(z2_50_0, 50) * z2_50_0 % q
        z2_200_0 = self.pow2(z2_100_0, 100) * z2_100_0 % q
        z2_250_0 = self.pow2(z2_200_0, 50) * z2_50_0 % q  # 2^250 - 2^0
        return self.pow2(z2_250_0, 5) * z11 % q  # 2^255 - 2^5 + 11 = q - 2

    def pow2(self, x, p):
        """== pow(x, 2**p, q)"""
        while p > 0:
            x = x * x % q
            p -= 1
        return x

    def xrecover(self, y):
        xx = (y * y - 1) * self.inv(self.d * y * y + 1)
        x = pow(xx, (q + 3) // 8, q)

        if (x * x - xx) % q != 0:
            x = (x * self.I) % q

        if x % 2 != 0:
            x = q - x

        return x

    def edwards_add(self, P, Q):
        # This is formula sequence 'addition-add-2008-hwcd-3' from
        # http://www.hyperelliptic.org/EFD/g1p/auto-twisted-extended-1.html
        (x1, y1, z1, t1) = P
        (x2, y2, z2, t2) = Q

        a = (y1 - x1) * (y2 - x2) % q
        b = (y1 + x1) * (y2 + x2) % q
        c = t1 * 2 * self.d * t2 % q
        dd = z1 * 2 * z2 % q
        e = b - a
        f = dd - c
        g = dd + c
        h = b + a
        x3 = e * f
        y3 = g * h
        t3 = e * h
        z3 = f * g

        return (x3 % q, y3 % q, z3 % q, t3 % q)

    def edwards_double(self, P):
        # This is formula sequence 'dbl-2008-hwcd' from
        # http://www.hyperelliptic.org/EFD/g1p/auto-twisted-extended-1.html
        (x1, y1, z1, t1) = P

        a = x1 * x1 % q
        b = y1 * y1 % q
        c = 2 * z1 * z1 % q
        # dd = -a
        e = ((x1 + y1) * (x1 + y1) - a - b) % q
        g = -a + b  # dd + b
        f = g - c
        h = -a - b  # dd - b
        x3 = e * f
        y3 = g * h
        t3 = e * h
        z3 = f * g

        return (x3 % q, y3 % q, z3 % q, t3 % q)

    def encodepoint(self, P):
        (x, y, z, t) = P
        zi = self.inv(z)
        x = (x * zi) % q
        y = (y * zi) % q
        bits = [(y >> i) & 1 for i in range(b - 1)] + [x & 1]
        return b''.join([
            self.int2byte(sum([bits[i * 8 + j] << j for j in range(8)]))
            for i in range(b // 8)
        ])


    def decodepoint(self, s):
        y = sum(2 ** i * self.bit(s, i) for i in range(0, b - 1))
        x = self.xrecover(y)
        if x & 1 != self.bit(s, b - 1):
            x = q - x
        P = (x, y, 1, (x * y) % q)
        if not self.isoncurve(P):
            raise ValueError("decoding point that is not on curve")
        return P

    def decodeint(self, s):
        return sum(2 ** i * self.bit(s, i) for i in range(0, b))

    def scalarmult(self, P, e):
        if e == 0:
            return self.ident
        Q = self.scalarmult(P, e // 2)
        Q = self.edwards_double(Q)
        if e & 1:
            Q = self.edwards_add(Q, P)
        return Q


    def isoncurve(self, P):
        (x, y, z, t) = P
        return (z % q != 0 and
                x * y % q == z * t % q and
                (y * y - x * x - z * z - self.d * t * t) % q == 0)

    @staticmethod
    def bit(h, i):
        return (getitem(h, i // 8) >> (i % 8)) & 1

    def derive_shared_secret(self, your_sk: bytes, recipient_pk: bytes):
        h = self.to_hash(your_sk)
        a = 2 ** (b - 2) + sum(2 ** i * self.bit(h, i) for i in range(3, b - 2))
        A = self.decodepoint(recipient_pk)
        shared_secret = self.encodepoint(self.scalarmult(A, a))
        return shared_secret

    def encrypt(self, your_sk, recipient_pk, message):

        shared_secret = self.derive_shared_secret(your_sk, recipient_pk)
        # salt = os.urandom(32) did not understand why it does not work with not empty salt
        salt = b''
        iv = os.urandom(12)
        info = b'catapult'

        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=info,
            backend=default_backend()
        ).derive(shared_secret)

        cipher = AES.new(derived_key, AES.MODE_GCM, iv)
        encrypted_msg, mac_tag = cipher.encrypt_and_digest(message)
        return mac_tag + iv + encrypted_msg

    def decrypt(self, your_sk, sender_pk, message):
        shared_secret = self.derive_shared_secret(your_sk, sender_pk)
        salt = b''
        mac_tag = message[0:self.MAC_TAG_SIZE]
        iv = message[len(mac_tag):len(mac_tag) + self.IV_SIZE]
        info = b'catapult'

        encrypted_msg = message[self.MAC_TAG_SIZE + self.IV_SIZE:]

        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=info,
            backend=default_backend()
        ).derive(shared_secret)

        cipher = AES.new(derived_key, AES.MODE_GCM, iv)
        plaintext = cipher.decrypt_and_verify(encrypted_msg, mac_tag)
        return plaintext
