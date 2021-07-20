
from enum import Enum
import click
from nempy.wallet import Wallet, Profile


@click.group('profile')
def main():
    """
    Interactive account management
    :return:
    """
    print('Interactive account management:')


@main.command('import')
def import_account():
    pass
    # account_path, name, network_type, bip32_coin_id, node_url = init_general_params()
    # password = input_pass(10)
    # gen_type = get_gen_type()
    #
    # if gen_type == GenerationTypes.MNEMONIC:
    #     account = account_by_mnemonic(network_type, bip32_coin_id)
    # account['password'] = password
    # account['name'] = name
    # account['node_url'] = node_url
    # account = Account(account)
    # account_creation(account, account_path)


@main.command('create')
def create_profile():
    profile = Profile()
    profile.create_profile()
    # account_path, name, network_type, bip32_coin_id, node_url = init_general_params()
    # password = input_pass(10)
    # account = account_by_mnemonic(network_type, bip32_coin_id, is_generate=True)
    #
    # account['password'] = password
    # account['name'] = name
    # account['node_url'] = node_url
    # account = Account(account)
    # account_creation(account, account_path)


@main.command('info')
@click.option('-n', '--name', type=str, required=False, default='', help='Account name')
def profile_info(name):
    wallet = Wallet()
    wallet.print_profiles()
    # if not name:
    #     name = get_default_account()
    # account_path = build_account_path(name)
    # if not os.path.exists(account_path):
    #     print(f'The account named `{name}` does not exist')
    #     exit(1)
    # password = stdiomask.getpass(f'Enter your account password: ')
    # account = read_account(account_path, password)
    # if isinstance(account, DecoderStatus):
    #     exit(1)
    # print(account)
    # print_warning()


if __name__ == '__main__':
    main()
