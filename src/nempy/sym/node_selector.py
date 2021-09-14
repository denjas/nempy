import asyncio
import logging
import multiprocessing
import re
import threading
import time
from http import HTTPStatus
from typing import Optional, Union, List, Callable
from urllib.parse import urlparse

import requests
import websockets
from websockets import exceptions

from . import config
from .constants import NetworkType, BlockchainStatuses

logger = logging.getLogger(__name__)


def url_validation(url):
    """django URL validation regex
    Raise an exception if the url is not valid"""
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    if re.match(regex, url) is None:
        raise ValueError(f'`{url}` is not a valid URL')


class Thread:
    """A helper class for working with a thread, starting and stopping it by signals"""
    def __init__(self):
        self.stop_event: Optional[threading.Event] = None
        self.thread: Optional[threading.Thread] = None
        self.is_started = False
        self.updated = threading.Event()

    def stop(self):
        if self.thread is not None and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join()
            self.is_started = False
            logger.debug(f'The node actualization thread {self.thread.name} has been stopped.')

    def start(self, func: Callable, interval: int = 3600):
        self.is_started = True
        self.stop_event = threading.Event()
        self.updated = threading.Event()
        params = {'interval': interval, 'stop_event': self.stop_event, 'updated': self.updated}
        self.thread = threading.Thread(target=func, kwargs=params, daemon=True)
        self.thread.start()
        logger.debug(f'New actualizer thread started: {self.thread.name}')
        return self

    def wait(self):
        updated_is_set = self.updated.wait(60)
        if not updated_is_set:
            raise RuntimeError('Very long waiting time for node selection')


class NodeSelector:
    """Works with a list of nodes in both the main and test networks.
       Offline finds the best connection options and makes adjustments if conditions change.
       Also allows you to add connections manually.
    """
    _URL: Optional[str] = None
    _URLs: Optional[list] = None
    is_elections: bool = False
    _network_type: NetworkType = NetworkType.TEST_NET

    def __init__(self, node_urls: Union[List[str], str]):
        self.thread = Thread()
        self.url = node_urls

    @property
    def url(self):
        while self.is_elections:
            time.sleep(0.1)
        return self._URL

    @url.setter
    def url(self, urls: Union[list, str]):
        self.is_elections = True
        self.thread.stop()
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            url_validation(url)
        self._URLs = urls
        if len(self._URLs) == 1:
            self._URL = self._URLs[0]  # setting a single URL value
            logger.debug(f'Installed node: {self._URL}')
        else:
            self.thread.start(self.node_actualizer, interval=3600).wait()
        self.is_elections = False

    def node_actualizer(self, interval, stop_event, updated):
        while True:
            self.reelection_node()
            updated.set()
            event_is_set = stop_event.wait(interval)
            if event_is_set:
                break

    def reelection_node(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        logger.debug('Node reselecting...')
        heights = [NodeSelector.get_height(url) for url in self._URLs]
        max_height = max(heights)
        heights_filter = [True if height >= max_height * 0.97 else False for height in heights]
        # filtered by block height - 97%
        filtered_by_height = [url for i, url in enumerate(self._URLs) if heights_filter[i]]
        urls_p_h = {url: (NodeSelector.ping(url), NodeSelector.simple_health(url)) for url in filtered_by_height}
        # Remove non-working nodes from the dict
        working = {key: val for key, val in urls_p_h.items() if val[1]}
        _sorted_URLs = [k for k, v in sorted(working.items(), key=lambda item: item[1][0])]
        new_url = _sorted_URLs[0] if len(_sorted_URLs) > 0 else None
        if new_url != self._URL and self._URL is not None:
            logger.warning(f'Reselection node: {self._URL} -> {new_url}')
        if new_url is None:
            logger.error('It was not possible to select the current node from the list of available ones')
        self._URL = new_url
        logger.debug(f'Selected node: {self._URL}')

    @property
    def network_type(self):
        return self._network_type

    @network_type.setter
    def network_type(self, network_type):
        if network_type == self.network_type:
            return
        self._network_type = network_type
        if self._network_type == NetworkType.MAIN_NET:
            logger.debug('Switch to MAIN network')
            self.url = config.MAIN_NODE_URLs
        elif self._network_type == NetworkType.TEST_NET:
            logger.debug('Switch to TEST network')
            self.url = config.TEST_NODE_URLs
        else:
            raise TypeError('Unknown network type')

    @staticmethod
    def health(url) -> BlockchainStatuses:
        """
        Returns the statuses of node services
        Parameters
        ----------
        url
            URL node in the form of http://ngl-dual-001.testnet.symboldev.network:3000
        Returns
        -------
        BlockchainStatuses
            The statuses of node services
        ```py
        BlockchainStatuses.DB_FAILURE
        BlockchainStatuses.NO_NODES_AVAILABLE
        BlockchainStatuses.NOT_INITIALIZED
        BlockchainStatuses.REST_FAILURE
        BlockchainStatuses.OK
        BlockchainStatuses.UNKNOWN
        ```
        """
        if url is None:
            return BlockchainStatuses.NO_NODES_AVAILABLE
        try:
            answer = requests.get(f'{url}/node/health', timeout=1)
        except Exception as e:
            logger.exception(e)
            return BlockchainStatuses.REST_FAILURE
        if answer.status_code == HTTPStatus.OK:
            node_info = answer.json()
            if node_info['status']['apiNode'] == 'up' and node_info['status']['db'] == 'up':
                return BlockchainStatuses.OK
            if node_info['status']['apiNode'] == 'down':
                return BlockchainStatuses.NODE_FAILURE
            if node_info['status']['db'] == 'down':
                return BlockchainStatuses.DB_FAILURE
        return BlockchainStatuses.UNKNOWN

    @staticmethod
    def simple_health(url) -> bool:
        health_status = NodeSelector.health(url)
        if health_status == BlockchainStatuses.OK:
            return True
        return False

    @staticmethod
    def get_height(url) -> int:
        """
        Returns the last block known to the node
        Parameters
        ----------
        url
            URL node in the form of http://ngl-dual-001.testnet.symboldev.network:3000

        Returns
        -------

        """
        try:
            answer = requests.get(f'{url}/chain/info', timeout=1)
        except Exception:
            return 0
        node_info = answer.json()
        height = node_info['height']
        return int(height)

    @staticmethod
    def ping(url) -> Optional[float]:
        """Calculate and return a latency point using sockets"""
        if multiprocessing.current_process().daemon:
            asyncio.set_event_loop(asyncio.new_event_loop())
        parse_result = urlparse(url)
        loop = asyncio.get_event_loop()
        latency = loop.run_until_complete(NodeSelector.measure_latency(host=parse_result.hostname, port=parse_result.port, runs=3))
        if (result := len(list(filter(None, latency)))) == 0:
            return None
        average = sum(filter(None, latency)) / result
        return average

    @staticmethod
    async def measure_latency(
            host: str,
            port: int = 443,
            timeout: float = 5,
            runs: int = 1,
            wait: float = 0,
    ) -> list:
        """
        Builds a list composed of latency_points
        Parameters
        ----------
        host
            Host name
        port
            Port
        timeout
            Server response timeout
        runs
            Number of attempts
        wait
            Delay before request
        Returns
        -------
        list
            list of latency for all runs
        """
        tasks = []
        latency_points = []
        for i in range(runs):
            await asyncio.sleep(wait)
            tasks.append(asyncio.create_task(NodeSelector.latency_point(host=host, port=port, timeout=timeout)))
            # last_latency_point = await latency_point(host=host, port=port, timeout=timeout)
        for i in range(runs):
            latency_points.append(await tasks[i])
        return latency_points

    @staticmethod
    async def latency_point(host: str, port: int = 443, timeout: float = 5) -> Optional[float]:
        """
        Calculate a latency point using sockets. If something bad happens the point returned is None
        Parameters
        ----------
        host
            Host name
        port
            Port
        timeout
            Server response timeout
        Returns
        -------
        Optional[float]
            Returns float if possible
        """
        # New Socket and Time out
        # Start a timer
        s_start = time.time()

        # Try to Connect
        uri = f"ws://{host}:{port}"
        try:
            async with websockets.connect(uri, close_timeout=timeout):
                pass
        except exceptions.InvalidMessage:
            pass
        except exceptions.InvalidStatusCode:
            pass
        except Exception as e:
            logger.debug(str(e))
            return None

        # Stop Timer
        s_runtime = (time.time() - s_start) * 1000
        return float(s_runtime)


# singleton for background work with the list of nodes
node_selector = NodeSelector(config.TEST_NODE_URLs)
