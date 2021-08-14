
from nempy.sym.constants import TransactionTypes


class TestTransactionTypes:

    @staticmethod
    def test_get_type_by_id():
        assert TransactionTypes.get_type_by_id(16724) == TransactionTypes.TRANSFER
