from nempy.sym.ed25519 import Ed25519


class TestEd25519:

    def setup(self):
        self.ed25519 = Ed25519()
        self.secret_key = self.ed25519.secret_key(b'0000000000000000000000')
        self.public_key = self.ed25519.public_key(self.secret_key)
        self.address = self.ed25519.get_address(self.public_key)

    def test_secret_key(self):
        assert self.secret_key == b'584714908DD017296F9D787F51C369C090EDC031449CD535ABE8CD936A4C895A'

    def test_public_key(self):
        assert self.public_key == b'C4B8371902500B150BCFA9E4704AA504B4AFEDFFB472B26A777670EDD62FE4A7'

    def test_get_address(self):
        assert self.address == 'TB2BOAUT2JESCX4KMCKTVY27CYYJ4YK3RJD7FCQ'
