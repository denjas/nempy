import pytest

from nempy import init
from nempy.wallet import Wallet


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


def test_numbers_3_4():
    print("test 3*4")
    assert 3 * 4 == 12


def test_strings_a_3():
    print("test a*3")
    assert 'a' * 3 == 'aaa'


def test_hello_world():
    wallet = Wallet(skip_checks=True)
    result = init()
    assert result == 'Hello NEMpy!'
