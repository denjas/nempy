import datetime
import json
import logging

import requests
from requests.exceptions import ConnectionError

from .constants import NISStatuses
from .ed25519 import Ed25519

from symbolchain.core.CryptoTypes import PrivateKey
from symbolchain.core.CryptoTypes import Signature, PublicKey
from symbolchain.core.facade.NisFacade import NisFacade
from binascii import hexlify, unhexlify


EPOCH_TIME_TEST = datetime.datetime(2015, 3, 29, 0, 6, 38, tzinfo=datetime.timezone.utc)
EPOCH_TIME_MAIN = datetime.datetime(2015, 3, 29, 0, 6, 25, tzinfo=datetime.timezone.utc)


class Timing:

    def __init__(self, network_type: str = None):
        if network_type == 'testnet':
            self.epoch_time = EPOCH_TIME_TEST

    def calc_deadline(self, days: float = 0, seconds: float = 0, milliseconds: float = 0,
                      minutes: float = 0, hours: float = 0, weeks: float = 0):

        if days + seconds + milliseconds + minutes + hours + weeks <= 0:
            raise TimeoutError('Added time must be positive otherwise the transaction will not have time to process')
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        timestamp = now - self.epoch_time
        td = timestamp + datetime.timedelta(days=days, seconds=seconds,
                                            milliseconds=milliseconds, minutes=minutes,
                                            hours=hours, weeks=weeks)
        deadline = int(td.total_seconds())
        return deadline


def tx_ver2(binary, tx_dict):
    # first section same with ver1

    """ add mosaic section """
    binary += len(tx_dict['mosaics']).to_bytes(4, "little")  # Number of mosaics 0x01000000

    # The following part is repeated for every mosaic in the attachment.
    # NIS bug, need mosaic order
    mosaic_dict = {e['mosaicId']['namespaceId']+e['mosaicId']['name']: e for e in tx_dict['mosaics']}
    for name in sorted(mosaic_dict.keys()):
        mosaic = mosaic_dict[name]
        namespace_id = mosaic['mosaicId']['namespaceId'].encode('utf8')
        namespace_id_len = len(namespace_id).to_bytes(4, "little")

        name = mosaic['mosaicId']['name'].encode('utf8')
        name_len = len(name).to_bytes(4, "little")

        mosaic_id_structure = namespace_id_len + namespace_id + name_len + name
        mosaic_id_structure_len = len(mosaic_id_structure).to_bytes(4, "little")

        value = mosaic['quantity'].to_bytes(8, "little")

        mosaic_structure = mosaic_id_structure_len + mosaic_id_structure + value
        mosaic_structure_len = len(mosaic_structure).to_bytes(4, "little")

        binary += mosaic_structure_len + mosaic_structure
    return binary


class Transaction:
    # Size of transaction with empty message
    MIN_TRANSACTION_SIZE = 160
    XYM_ID = int('091F837E059AE13C', 16)

    def __init__(self):
        self.size = None
        self.max_fee = None

        # self.timing = network.Timing()
        # self.network_type = network.get_node_network()
        # self.nis_facade = NisFacade(self.network_type) TODO
        self.nis_facade = NisFacade('testnet')
        self.timing = Timing('testnet')

    def create(self,
               pr_key: str,
               recipient_address: str,
               # mosaics: [Mosaic, List[Mosaic]] = None, # do not implemented
               amount: float = 0,
               message: str = None,
               deadline: [dict, None] = None
               ):

        if deadline is None:
            deadline = {'hours': 24}
        else:
            raise NotImplemented('Deadline change is not possible due to libraries in dependencies')
        key_pair = self.nis_facade.KeyPair(PrivateKey(unhexlify(pr_key)))

        deadline = self.timing.calc_deadline(**deadline)

        descriptor = {
            'type': 'transfer',
            'recipient_address': recipient_address,
            'signer_public_key': key_pair.public_key,
            'amount': amount * 10 ** 6,
            # 'mosaics': ['nem.xem', 12345],
            'deadline': deadline,
            'message': message
        }

        transaction = self.nis_facade.transaction_factory.create(descriptor)

        signature = self.nis_facade.sign_transaction(key_pair, transaction)
        # entity_hash = Transaction.entity_hash_gen(signature, key_pair.public_key, transaction,
        #                                           self.nis_facade.network.generation_hash_seed)

        payload_bytes = self.nis_facade.transaction_factory.attach_signature(transaction, signature)

        # mosaics = {'mosaicId': {'namespaceId': 'nem', 'name': 'xem'}, 'quantity': 11111}
        # tx_dict = {
        #     'mosaics': [mosaics]
        # }
        # bytes_with_mosaic = tx_ver2(transaction.serialize(), tx_dict)
        #
        print(transaction)
        # print(hexlify(transaction.serialize()))
        # logging.debug(f'Transaction hash: {entity_hash}')

        return None, {'data': hexlify(transaction.serialize()).decode(), 'signature': str(signature)}


DIV = {'nem:xem': 6}


def check_status(url, is_logging=False) -> NISStatuses:
    endpoint = f'{url}/status'
    try:
        request = requests.get(endpoint, timeout=3)
    except ConnectionError:
        nem_log.critical(NISStatuses.S9.value)
        return NISStatuses.S9
    if request.status_code == 200:
        status = request.json()
        nis_status = NISStatuses[f"_{status['code']}"]
        if status['code'] in [0, 1]:
            logger = logging.error
        elif status['code'] != 6:
            logger = logging.warning
        else:
            logger = logging.info
    else:
        nis_status = NISStatuses.S9
        logger = logging.critical
    if is_logging:
        logger(nis_status.value)
    return nis_status


def byte2str(b):
    return b if type(b) == str else b.decode()


def get_divisibility(url, name_space_id, mosaic_id):
    timeout = 10
    mosaic_info_endpoint = 'namespace/mosaic/definition/page'
    mosaic_info_req_data = {'namespace': name_space_id}
    mosaic_info_url = f'{url}/{mosaic_info_endpoint}'
    mosaic_info_ret = requests.get(mosaic_info_url, params=mosaic_info_req_data, timeout=timeout)
    if mosaic_info_ret.status_code == 200:
        mosaics_info = mosaic_info_ret.json()['data']
        for mosaic_info in mosaics_info:
            if mosaic_info['mosaic']['id']['name'] == mosaic_id:
                divisibility = mosaic_info['mosaic']['properties'][0]['value']
                return divisibility, 200
        raise RuntimeError(f'Missing mosaic `{mosaic_id}` in namespace `{name_space_id}`')
    else:
        logging.error(f'{mosaic_info_ret.status_code}: {mosaic_info_ret.text}')
        return mosaic_info_ret.json(), mosaic_info_ret.status_code


def send_token(url, nem_address, pr_key, pub_key, namespace, mosaic_name, quantity):
    """
    Send tokens to nem_address
    :param url: http://3.122.185.121:7890
    :param nem_address: address of recipient
    :param pr_key: our privet key
    :param pub_key: our public key
    :param quantity:
    :param div: divisibility of mosaic
    :return:
    """
    # get divisibility
    mosaic_full_name = "{}:{}".format(namespace, mosaic_name)
    if mosaic_full_name in DIV:
        div = DIV[mosaic_full_name]
    else:
        div, ret_code = get_divisibility(url, namespace, mosaic_name)
        if ret_code != 200:
            div['nem_address'] = nem_address
            return ret_code, div
    divisibility = 10**int(div)
    nem_address = nem_address.replace('-', '')
    quantity = int(quantity*divisibility)
    chain_call = 'time-sync/network-time'
    endpoint = f'{url}/{chain_call}'
    answer_chain = requests.get(endpoint, timeout=10)
    last_block_data = answer_chain.json()
    timestamp_nem = int(last_block_data['receiveTimeStamp']/1000)

    # nemEpoch = datetime.datetime(2015, 3, 29, 0, 6, 25, 0, None)
    # unixtime = time.mktime(nemEpoch.timetuple())
    # date1 = datetime.datetime.now()
    # unixtime1 = time.mktime(date1.timetuple())
    #
    # timestamp_nem = int(unixtime1 - unixtime)

    # create raw transaction
    tb = TransactionBuilder()
    mosaic = {'mosaicId': {'namespaceId': namespace, 'name': mosaic_name}, 'quantity': quantity}
    mosaics = [mosaic]
    tx_dict = {
        'type': 257, 'version': -1744830462,
        'signer': pub_key,
        'timeStamp': timestamp_nem, 'deadline': timestamp_nem + 86400,  # 86400 - seconds per 24 hours
        'recipient': nem_address,
        'amount': 1000000,
        'fee': 100000,
        'message': {'type': 1, 'payload': 'from main-wallet'.encode("utf-8").hex()},
        'mosaics': mosaics
    }

    tx_hex = tb.encode(tx_dict)
    # sign transaction
    secret_key = pr_key
    public_key = pub_key
    sign_hex = Ed25519.sign(unhexlify(tx_hex.encode()), secret_key, public_key)
    transaction_call = 'transaction/announce'
    endpoint = f'{url}/{transaction_call}'

    data = {'data': byte2str(tx_hex), 'signature': byte2str(sign_hex)}
    headers = {'Content-type': 'application/json'}
    answer = requests.post(endpoint, data=json.dumps(data), headers=headers, timeout=10)
    # tx_hash = Ed25519.nem.transaction_announce(tx_hex, sign_hex)
    if answer.status_code == 200:
        message = answer.json()
        if message['code'] == 1:
            nem_log.info(str(message))
            return answer.status_code, message['transactionHash']['data']
        nem_log.error(str(message))
        return False, message
    else:
        err = answer.json()
        nem_log.error(str(err))
        return answer.status_code, err


# def get_balance_old(url, nem_address):
#     """
#     Get balance
#     :param url: http://62.75.163.236:7890/account/mosaic/owned?address=NCR2CQE6AI3DIRHPHEPBSVDBOQFSHXFSQF4NIUAH
#     :param nem_address:
#     :return:
#     """
#     timeout = 10
#     endpoint = "account/mosaic/owned"
#     url = f'{url}/{endpoint}'
#     data = {"address": nem_address}
#     ret = requests.get(url, params=data, timeout=timeout)
#     if ret.status_code == 200:
#         balance = {"{}:{}".format(e['mosaicId']['namespaceId'], e['mosaicId']['name']): e['quantity']
#                    for e in ret.json()['data']}
#         return balance
#     nem_log.error(str(ret.json()))
#     return {}


def get_balance(url, nem_address, test=False):
    """
    Get balance
    :param url: http://62.75.163.236:7890/account/mosaic/owned?address=NCR2CQE6AI3DIRHPHEPBSVDBOQFSHXFSQF4NIUAH
    :param nem_address:
    :return:
    """
    if test:
        token = f"{'gtns'}:{'gt'}"
        return {token: 10}, 200
    timeout = 10
    balance_endpoint = "account/mosaic/owned"
    balance_url = f'{url}/{balance_endpoint}'
    data = {"address": nem_address}
    try:
        ret = requests.get(balance_url, params=data, timeout=timeout)
    except ConnectionError:
        return {'err': 'NIS is not responding'}, 522
    if ret.status_code == 200:
        balance = {}
        for e in ret.json()['data']:
            name_space_id = e['mosaicId']['namespaceId']
            mosaic_id = e['mosaicId']['name']
            mosaic_quantity = e['quantity']
            mosaic_full_name = "{}:{}".format(name_space_id, mosaic_id)
            if mosaic_full_name in DIV:
                divisibility = DIV[mosaic_full_name]
            else:
                # TODO think over the general scheme of processing requests from NIS NEM
                divisibility, ret_code = get_divisibility(url, name_space_id, mosaic_id)
                if ret_code != 200:
                    divisibility['nem_address'] = nem_address
                    return divisibility, ret_code
            mosaic_quantity = float(mosaic_quantity) / 10 ** float(divisibility)
            balance[mosaic_full_name] = mosaic_quantity
        return balance, ret.status_code
    err = str(ret.json())
    nem_log.error(err)
    return err, ret.status_code


def check_transaction_confirmation(url, nem_address, transaction_hash):
    """
    Get balance
    :param url: http://62.75.163.236:7890/account/mosaic/owned?address=NCR2CQE6AI3DIRHPHEPBSVDBOQFSHXFSQF4NIUAH
    :param nem_address:
    :param transaction_hash:
    :return: transaction confirmation, bool
    """
    timeout = 10
    endpoint = "/account/transfers/incoming"
    url = f'{url}/{endpoint}'
    data = {"address": nem_address}
    ret = requests.get(url, params=data, timeout=timeout)
    if ret.status_code == 200:
        transactions = ret.json()['data']
        for transaction in transactions:
            if transaction['meta']['hash']['data'] == transaction_hash:
                return True
        return False
    nem_log.error(str(ret.json()))
    return False







