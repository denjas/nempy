

```shell
nempy-cli.py
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