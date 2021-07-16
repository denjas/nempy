from enum import Enum


class NISStatuses(Enum):
    S0 = 'Unknown status.'
    S1 = 'NIS is stopped.'
    S2 = 'NIS is starting.'
    S3 = 'NIS is running.'
    S4 = 'NIS is booting the local node (implies NIS is running).'
    S5 = 'The local node is booted (implies NIS is running).'
    S6 = 'The local node is synchronized (implies NIS is running and the local node is booted).'  # NODE OK
    S7 = 'NIS local node does not see any remote NIS node (implies running and booted).'
    S8 = 'NIS is currently loading the block chain from the database. In this state NIS cannot serve any requests.'
    S9 = 'NIS is not running or is in a state where it can`t serve requests.'
    S10 = 'Blockchain not initialized. Initialize the private key with the command: `flask init wallet.'
