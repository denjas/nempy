import logging


logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('asyncio.coroutines').setLevel(logging.ERROR)
logging.getLogger('websockets').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
log_format = "[%(asctime)s][%(levelname)s] %(name)s - %(message)s"
logging.basicConfig(level=logging.DEBUG, format=log_format)

