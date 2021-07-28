
import pytest
from nempy.sym import ed25519
from nempy.sym.api import Message, PlainMessage, EncryptMessage, Namespace
from ..test_account import test_account


# def setup():
#     print("basic setup into module")
#
#
# def teardown():
#     print("basic teardown into module")
#
#
# def setup_module(module):
#     print("module setup")
#
#
# def teardown_module(module):
#     print("module teardown")
#
#
# def setup_function(function):
#     print("function setup")
#
#
# def teardown_function(function):
#     print("function teardown")


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
    message = PlainMessage('')
    assert message == b''


def test_encrypt_message():
    _message = 'Hello NEM!'
    account0, account1 = test_account()
    sender_private_key = account0.private_key
    recipient_pub = account1.public_key

    enc_message = EncryptMessage(_message, sender_private_key, recipient_pub)
    with pytest.raises(OverflowError):
        EncryptMessage('#' * 1024, sender_private_key, recipient_pub)

    assert enc_message.size == 77
    recipient_priv = account1.private_key
    sender_pub = account0.public_key

    message = ed25519.Ed25519.decrypt(recipient_priv, sender_pub, enc_message[1:])
    assert message == b'Hello NEM!'


def test_namespace():
    namespace = Namespace('gtns.gt.gt-')
    assert namespace == '93EB2CE4539AB443'
    with pytest.raises(ValueError):
        Namespace('')
    with pytest.raises(ValueError):
        Namespace('test@')
    with pytest.raises(ValueError):
        Namespace('t' * 65)
