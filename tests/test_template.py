import unittest

from nempy import init


class TemplateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_hello_world(self):
        result = init()
        self.assertEqual(result, 'Hello NEMpy!')
