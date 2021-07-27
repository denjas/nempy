
import pytest
from nempy.sym import ed25519
from binascii import hexlify, unhexlify
from nempy.sym.api import Message, PlainMessage, EncryptMessage


def setup():
    print("basic setup into module")


def teardown():
    print("basic teardown into module")


def setup_module(module):
    print("module setup")


def teardown_module(module):
    print("module teardown")


def setup_function(function):
    print("function setup")


def teardown_function(function):
    print("function teardown")


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


def test_plain_message():
    _messages = 'Hello NEM!'
    message = PlainMessage(_messages)
    assert message == b'\x00Hello NEM!'
    assert message.size == len(_messages) + 1


def test_encrypt_message():
    _message = 'Hello NEM!'
    sender_private_key = '96AF80EBCE635BC5F19FF1E982C44753341F3154A27D10E530138FFBD68FA8A3'
    recipient_pub = 'AFFDC5BE0EC17B395C59334C4CAE22DA44620B0D9DEEE5B057670C05EFBC2122'

    enc_message = EncryptMessage(_message, sender_private_key, recipient_pub)
    with pytest.raises(OverflowError):
        EncryptMessage('#' * 1024, sender_private_key, recipient_pub)

    assert enc_message.size == 77
    recipient_priv = 'FF88AAD14071144CDD6C50BB4C3E398AF6C64D173832B838B06BAF5313D8EB6A'
    sender_pub = 'F291486DAD4B920464FB701EEB516890224292EDE0CAD118FD5A8C4ECB0FECE1'

    message = ed25519.Ed25519.decrypt(recipient_priv, sender_pub, enc_message[1:])
    assert message == b'Hello NEM!'
