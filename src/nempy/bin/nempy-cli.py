#!/usr/bin/env python
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('asyncio.coroutines').setLevel(logging.ERROR)
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


def main():
    print('Hello NEMpy!')


if __name__ == '__main__':
    main()
