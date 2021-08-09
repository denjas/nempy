# NEMpy

[![tests](https://github.com/denjas/nempy/actions/workflows/main.yml/badge.svg)](https://github.com/DENjjA/nempy/actions/workflows/main.yml)
[![python-ver](https://github.com/denjas/nempy/blob/dev/.github/badges/python-version.svg)](https://www.python.org/)
[![license](https://github.com/denjas/nempy/blob/dev/.github/badges/license.svg)](https://github.com/DENjjA/nempy/blob/dev/LICENSE)
![badge](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/denjas/9c7a615b3b16ced41d8530c7535ca131/raw/coverage.json)



High-level python wrapper for working with cryptocurrencies of the NEM ecosystem

Implemented on the basis symbol project [core sdk python library](https://github.com/symbol/symbol-sdk-core-python)
## Possibilities
* Creating a wallet with profiles and accounts
* Using a wallet to send funds view activity history and balance
* Blockchain [monitoring](https://docs.symbolplatform.com/api.html#websockets) via [websocket](https://ru.wikipedia.org/wiki/WebSocket)
* Ability to use all the above in third-party products and services

## Getting Started

This is an example of how you may give instructions on setting up your project locally.
To get a local copy up and running follow these simple example steps.

### Prerequisites

This is an example of how to list things you need to use the software and how to install them.
* pipenv
  ```shell
  pip install pipenv
  ```

# Installing
Install and update using pip:
  ```shell
  pip install nempy
  ```
## A Simple Example

<font color='orange'>**Attention**!</font>
The example below is intended to demonstrate ease of use, but it is <font color='orange'>not secure</font>! Use this code only on the `NetworkType.TEST_NET`
```python
from nempy.user_data import AccountData
from nempy.engine import XYMEngine
from nempy.sym.network import NetworkType
from nempy.sym.constants import Fees

PRIVATE_KEY = '<YOUR_PRIVATE_KEY>'
PASSWORD = '<YOUR_PASS>'
account = AccountData.create(PRIVATE_KEY, NetworkType.TEST_NET).encrypt(PASSWORD)

engine = XYMEngine(account)
engine.send_tokens(recipient_address='TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ',
                   mosaics=[('@symbol.xym', 0.1), ],
                   message='Hallo NEM!',
                   password=PASSWORD,
                   fee_type=Fees.SLOWEST)
```
You can get funds for the balance for testing in the [Faucet](http://faucet.testnet.symboldev.network/).
## Command-line interface (CLI)

```shell
pipenv run nempy-cli.py
# Usage: nempy-cli.py [OPTIONS] COMMAND [ARGS]...
# Commands:
#   about       - About the program
#   account     - Interactive account management
#   monitoring  - Monitor blocks, transactions and errors
#   profile     - Interactive profile management
nempy-cli.py profile create  # create a profile according to the prompts of the interactive mode
nempy-cli.py account create  # create a account according to the prompts of the interactive mode
pipenv run nempy-cli.py profile info
#  +--------------+---------------------------------------------------------------+
#  |  >DEFAULT<   |                     Profile - test-main                       |
#  +==============+===============================================================+
#  | Name         | test-main                                                     |
#  +--------------+---------------------------------------------------------------+
#  | Network Type | TEST_NET                                                      |
#  +--------------+---------------------------------------------------------------+
#  | Pass Hash    | ************************************************************  |
#  +--------------+---------------------------------------------------------------+
nempy-cli.py account info
#  +--------------+--------------------------------------------------------------------+
#  |  >DEFAULT<   |                         Account - test-3                           |
#  +==============+====================================================================+
#  | Name         | test-3                                                             |
#  +--------------+--------------------------------------------------------------------+
#  | Network Type | TEST_NET                                                           |
#  +--------------+--------------------------------------------------------------------+
#  | Address      | TBTCYC-IDRQ7T-JBEAYD-ZLDPHO-TGIRKZ-HO5CH2-SMQ                      |
#  +--------------+--------------------------------------------------------------------+
#  | Public Key   | F291486DAD4B920464FB701EEB516890224292EDE0CAD118FD5A8C4ECB0FECE1   |
#  +--------------+--------------------------------------------------------------------+
#  | Private Key  | ****************************************************************   |
#  +--------------+--------------------------------------------------------------------+
#  | Path         | m/44'/1'/0'/0'/0'                                                  |
#  +--------------+--------------------------------------------------------------------+
#  | Mnemonic     | ******* **** ********** ******* ***** *********** ******** *****   |
#  +--------------+--------------------------------------------------------------------+
#  | Profile      | test-main                                                          |
#  +--------------+--------------------------------------------------------------------+
nempy-cli.py account send -a TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ -m @symbol.xym:0.01
#  +---------------------+-----------------------------------------------+
#  | Network Type        | PUBLIC_TEST                                   |
#  +---------------------+-----------------------------------------------+
#  | Recipient address:  | TDPFLB-K4NSCK-UBGAZD-WQWCUF-NJOJB3-3Y5R5A-WPQ |
#  +---------------------+-----------------------------------------------+
#  | Max Fee:            | slowest                                       |
#  +---------------------+-----------------------------------------------+
#  | Deadline (minutes): | 3                                             |
#  +---------------------+-----------------------------------------------+
#  | Mosaics:            | `symbol.xym`: - 0.01 (balance: 18.576735)     |
#  +---------------------+-----------------------------------------------+
#  Funds will be debited from your balance!
#  We continue? y/N:
#  Enter your `test-main [TEST_NET]` profile password: **********

#  MONITORING: ws://ngl-dual-401.testnet.symboldev.network:3000/ws
#  UID: YHPOFTQB72A7FBGTEBQ7SHPUTHWUMZIV
#  +----------------------------------------------------------+
#  | Subscribers                                              |
#  +==========================================================+
#  | confirmedAdded/TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ   |
#  +----------------------------------------------------------+
#  | unconfirmedAdded/TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ |
#  +----------------------------------------------------------+
#  | status/TDPFLBK4NSCKUBGAZDWQWCUFNJOJB33Y5R5AWPQ           |
#  +----------------------------------------------------------+
#  Listening... `Ctrl+C` for abort
#  [UNCONFIRMED] Transaction related to the given address enters the unconfirmed state, waiting to be included in a block...
#  [CONFIRMED] Transaction related to the given address is included in a block
pipenv run nempy-cli.py account balance
#  {
#    "symbol.xym": 18.000575
#  }
```
## Working with [pipenv](https://pipenv.pypa.io/) environment
1. Clone the repository `git clone https://github.com/denjas/nempy.git`
2. Go to the directory with the project `cd nempy`
3. Install virtualenv package `pip install pipenv`
4. Setting up a virtual environment `pipenv install`
### For development
To set up development in a virtual environment. Follow the previous steps then:
```shell
pipenv run pip inasall -e .
```

### Testing
Follow the previous steps to set up your environment.

Running tests `pipenv run tests` or `pipenv run tests --cov=src`to assess coverage

## Version Numbers
Version numbers will be assigned according to the [Semantic Versioning](https://semver.org/) scheme.
This means, given a version number MAJOR.MINOR.PATCH, we will increment the:

1. MAJOR version when we make incompatible API changes,
2. MINOR version when we add functionality in a backwards compatible manner, and
3. PATCH version when we make backwards compatible bug fixes.