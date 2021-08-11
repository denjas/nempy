# NEMpy

[![tests](https://github.com/denjas/nempy/actions/workflows/tests.yml/badge.svg)](https://github.com/denjas/nempy/actions/workflows/tests.yml)
[![build](https://github.com/denjas/nempy/actions/workflows/build.yml/badge.svg)](https://github.com/denjas/nempy/actions/workflows/build.yml)
[![python-ver](https://github.com/denjas/nempy/blob/dev/.github/badges/python-version.svg)](https://www.python.org/)
[![license](https://github.com/denjas/nempy/blob/dev/.github/badges/license.svg)](https://github.com/nempy/nempy/blob/dev/LICENSE)
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

For convenient work with the project, you will need [pipenv tool](https://pypi.org/project/pipenv/).
  ```shell
  pip install pipenv
  ```

# Installing
Install and update using pip:
  ```shell
  pip install nempy
  ```
## A Simple Example

**_Attention!_**

The example below is intended to demonstrate ease of use, but it is **_not secure_**! Use this code only on the `NetworkType.TEST_NET`
```python
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
You can get funds for the balance for testing in the [Faucet](http://faucet.testnet.symboldev.network/).

Additional [documentation](https://denjas.github.io/nempy/) can be found [here](https://denjas.github.io/nempy/)
## Command-line interface (CLI)
You can get acquainted with the capabilities of the CLI interface [here](https://github.com/denjas/nempy/blob/docgen/docs/cli.md)

## Working with [pipenv](https://pipenv.pypa.io/) environment
1. Clone the repository `git clone https://github.com/denjas/nempy.git`
2. Go to the directory with the project `cd nempy`
3. Install virtualenv package `pip install pipenv`
4. Setting up a virtual environment `pipenv install`
### Running CLI utility
```shell
pipenv run nempy-cli.py
```
### For development
To set up development in a virtual environment. Follow the previous steps then:
```shell
pipenv run pip inasall -e .
```

### Testing
Follow the previous steps to set up your environment.

Running tests `pipenv run tests` or `pipenv run tests --cov=src` to assess coverage

## Version Numbers
Version numbers will be assigned according to the [Semantic Versioning](https://semver.org/) scheme.
This means, given a version number MAJOR.MINOR.PATCH, we will increment the:

1. MAJOR version when we make incompatible API changes,
2. MINOR version when we add functionality in a backwards compatible manner, and
3. PATCH version when we make backwards compatible bug fixes.
