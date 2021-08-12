import datetime
from enum import Enum, EnumMeta, IntEnum

NETWORK_GENERATION_HASH_SEED_PUBLIC = '57F7DA205008026C776CB6AED843393F04CD458E0AA2D9F1D5F31A402072B2D6'
NETWORK_GENERATION_HASH_SEED_TEST = '3B5E1FA6445653C971A50687E75E6D09FB30481055E3990C84B25E9222DC1155'

EPOCH_TIME_MAINNET = datetime.datetime(2021, 3, 16, 0, 6, 25, tzinfo=datetime.timezone.utc)
EPOCH_TIME_TESTNET = datetime.datetime(2021, 3, 25, 17, 56, 17, tzinfo=datetime.timezone.utc)


class AccountValidationState(Enum):
    OK = 'The address is correct'
    LENGTH_FAILURE = 'The address length must be 39 characters'
    CHECKSUM_FAILURE = 'Checksum does not match'


class NetworkType(Enum):
    TEST_NET = 'public_test'
    MAIN_NET = 'public'


class TransactionStatus(Enum):
    NOT_FOUND = None
    UNCONFIRMED_ADDED = 'unconfirmed'
    CONFIRMED_ADDED = 'confirmed'
    PARTIAL_ADDED = 'partial'
    # UNCONFIRMED_REMOVED = 3
    # PARTIAL_REMOVED = 4


class BlockchainStatuses(Enum):
    UNKNOWN = 'Unknown blockchain error'
    OK = 'Blockchain successfully initialized'
    NOT_INITIALIZED = 'Blockchain not initialized. Initialize the private key with the command: `flask init wallet'
    NODE_FAILURE = 'NIS is not running or is in a state where it can`t serve requests.'
    DB_FAILURE = 'Database is not initialized or is out of date'
    REST_FAILURE = 'REST API server is not responding'
    NO_NODES_AVAILABLE = 'No nodes available in the picklist (URL is None)'


class HexSequenceSizes(IntEnum):
    ADDRESS = 39
    PUBLIC_KEY = PRIVATE_KEY = 64
    MOSAIC_ID = NAMESPACE_ID = 16


class Fees(Enum):
    ZERO = 0
    AVERAGE = 1
    FAST = 2
    SLOWEST = 3
    SLOW = 4


# Fees Multipliers
class FM(EnumMeta):
    lowest = 'lowestFeeMultiplier'
    min = 'minFeeMultiplier'
    average = 'averageFeeMultiplier'
    median = 'medianFeeMultiplier'
    highest = 'highestFeeMultiplier'


class TransactionMetrics:
    TRANSACTION_HEADER_SIZE = 8 + 64 + 32 + 4
    TRANSACTION_BODY_INDEX = TRANSACTION_HEADER_SIZE + 1 + 1 + 2 + 8 + 8


class TransactionTypes(IntEnum):
    #  Reserved entity type.
    RESERVED = 0
    #  Transfer Transaction transaction type.
    TRANSFER = 16724
    #  Register namespace transaction type.
    NAMESPACE_REGISTRATION = 16718
    #  Address alias transaction type
    ADDRESS_ALIAS = 16974
    #  Mosaic alias transaction type
    MOSAIC_ALIAS = 17230
    #  Mosaic definition transaction type.
    MOSAIC_DEFINITION = 16717
    #  Mosaic supply change transaction.
    MOSAIC_SUPPLY_CHANGE = 16973
    #  Modify multisig account transaction type.
    MULTISIG_ACCOUNT_MODIFICATION = 16725
    #  Aggregate complete transaction type.
    AGGREGATE_COMPLETE = 16705
    #  Aggregate bonded transaction type
    AGGREGATE_BONDED = 16961
    #  Lock transaction type
    HASH_LOCK = 16712
    #  Secret Lock Transaction type
    SECRET_LOCK = 16722
    #  Secret Proof transaction type
    SECRET_PROOF = 16978
    #  Account restriction address transaction type
    ACCOUNT_ADDRESS_RESTRICTION = 16720
    #  Account restriction mosaic transaction type
    ACCOUNT_MOSAIC_RESTRICTION = 16976
    #  Account restriction operation transaction type
    ACCOUNT_OPERATION_RESTRICTION = 17232
    #  Link account transaction type
    ACCOUNT_KEY_LINK = 16716
    #  Mosaic address restriction type
    MOSAIC_ADDRESS_RESTRICTION = 16977
    #  Mosaic global restriction type
    MOSAIC_GLOBAL_RESTRICTION = 16721
    #  Account metadata transaction
    ACCOUNT_METADATA = 16708
    #  Mosaic metadata transaction
    MOSAIC_METADATA = 16964
    #  Namespace metadata transaction
    NAMESPACE_METADATA = 17220
    #  Link vrf key transaction
    VRF_KEY_LINK = 16963
    #  Link voting key transaction
    VOTING_KEY_LINK = 16707
    #  Link node key transaction
    NODE_KEY_LINK = 16972

    @staticmethod
    def get_type_by_id(_id) -> 'TransactionTypes':
        attributes = TransactionTypes.__dict__
        attributes = {key: attributes[key] for key in attributes if not key.startswith('_') and key != 'get_type_by_id'}
        return TransactionTypes[list(attributes.keys())[list(attributes.values()).index(_id)]]
