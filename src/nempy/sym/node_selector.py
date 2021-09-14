import asyncio
import logging

import re

import time
import aiohttp

from http import HTTPStatus
from typing import Optional, Union, List
from urllib.parse import urlparse


import websockets
from requests import RequestException
from websockets import exceptions

from . import config, constants
from .constants import NetworkType, BlockchainStatuses


logger = logging.getLogger(__name__)


async def get_node_network():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{node_selector.url}/node/info", timeout=1) as response:
                if response.status == HTTPStatus.OK:
                    fee_info = await response.json()
                    network_generation_hash_seed = fee_info["networkGenerationHashSeed"]
                    if network_generation_hash_seed == constants.NETWORK_GENERATION_HASH_SEED_TEST:
                        return NetworkType.TEST_NET
                    elif network_generation_hash_seed == constants.NETWORK_GENERATION_HASH_SEED_PUBLIC:
                        return NetworkType.MAIN_NET
                    else:
                        return None
                response.raise_for_status()
    except RequestException as e:
        logger.exception(e)
        raise e


def url_validation(url):
    """django URL validation regex
    Raise an exception if the url is not valid"""
    regex = re.compile(
        r"^(?:http|ftp)s?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    if re.match(regex, url) is None:
        raise ValueError(f"`{url}` is not a valid URL")


class NodeSelector:
    """Works with a list of nodes in both the main and test networks.
    Offline finds the best connection options and makes adjustments if conditions change.
    Also allows you to add connections manually.
    """

    _URL: Optional[str] = None
    _URLs: Optional[list] = None
    _network_type: Optional[NetworkType] = None

    is_elections: bool = False
    task: Optional[asyncio.Task] = None
    interval: int = 3600

    def __init__(self, node_urls: Union[List[str], str]):
        self._URLs = [node_urls] if isinstance(node_urls, str) else node_urls
        self._URL = self._URLs[0]

    @property
    async def url(self):
        while self.is_elections:
            await asyncio.sleep(0.1)
        return self._URL

    @property
    async def network_type(self):
        while self.is_elections:
            await asyncio.sleep(0.1)
        self._network_type = await get_node_network()
        return self._network_type

    def start(self, interval: Optional[int] = None):
        """
        Starts a background task to select the nodes of the blockchain network
        The method is synchronous but needs to be run from async code
        """
        if len(self._URLs) == 1:
            logger.warning(
                "Only one blockchain node is installed. "
                "It is recommended to install a list of several nodes for more stable work"
            )
            return
        self.interval = interval if interval is not None else self.interval
        self.task = asyncio.create_task(self.node_actualizer(self.interval))
        self.task.set_name("elector")

    async def stop(self):
        """Stops the background async thread of node selection"""
        if self.task is not None and not self.task.cancelled():
            self.task.cancel()
            await self.task
        else:
            print("Task is cancelled or not set")

    async def restart(self, interval: Optional[int] = None):
        """Restarts the background node selection async thread"""
        await self.stop()
        self.start(interval)

    async def node_actualizer(self, interval: int = 3600):
        while True:
            try:
                self.is_elections = True
                await self.reelection_node()
                self.is_elections = False
                await asyncio.sleep(interval)
            except asyncio.CancelledError as e:
                print("Stop node actualizer")
                break

    async def reelection_node(self):
        logger.debug("Node reselecting...")
        heights = [await NodeSelector.get_height(url) for url in self._URLs]
        max_height = max(heights)
        heights_filter = [
            True if height >= max_height * 0.97 else False for height in heights
        ]
        # filtered by block height - 97%
        filtered_by_height = [
            url for i, url in enumerate(self._URLs) if heights_filter[i]
        ]
        urls_p_h = {
            url: (await NodeSelector.ping(url), await NodeSelector.simple_health(url))
            for url in filtered_by_height
        }
        # Remove non-working nodes from the dict
        working = {key: val for key, val in urls_p_h.items() if val[1]}
        _sorted_URLs = [
            k for k, v in sorted(working.items(), key=lambda item: item[1][0])
        ]
        new_url = _sorted_URLs[0] if len(_sorted_URLs) > 0 else None
        if new_url != self._URL and self._URL is not None:
            logger.warning(f"Reselection node: {self._URL} -> {new_url}")
        if new_url is None:
            logger.error(
                "It was not possible to select the current node from the list of available ones"
            )
        self._URL = new_url
        logger.warning(f"Selected node: {self._URL}")

    @staticmethod
    async def health(url) -> BlockchainStatuses:
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
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/node/health", timeout=1) as response:
                    if response.status == HTTPStatus.OK:
                        node_info = await response.json()
                        if (
                            node_info["status"]["apiNode"] == "up"
                            and node_info["status"]["db"] == "up"
                        ):
                            return BlockchainStatuses.OK
                        if node_info["status"]["apiNode"] == "down":
                            return BlockchainStatuses.NODE_FAILURE
                        if node_info["status"]["db"] == "down":
                            return BlockchainStatuses.DB_FAILURE
        except Exception as e:
            logger.exception(e)
            return BlockchainStatuses.REST_FAILURE
        return BlockchainStatuses.UNKNOWN

    @staticmethod
    async def simple_health(url) -> bool:
        health_status = await NodeSelector.health(url)
        if health_status == BlockchainStatuses.OK:
            return True
        return False

    @staticmethod
    async def get_height(url) -> int:
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
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/chain/info", timeout=1) as response:
                    node_info = await response.json()
                    height = node_info["height"]
                    return int(height)
        except Exception as e:
            logger.exception(e)
            return 0

    @staticmethod
    async def ping(url) -> Optional[float]:
        """Calculate and return a latency point using sockets"""

        parse_result = urlparse(url)

        latency = await NodeSelector.measure_latency(
            host=parse_result.hostname, port=parse_result.port, runs=3
        )
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
            tasks.append(
                asyncio.create_task(
                    NodeSelector.latency_point(host=host, port=port, timeout=timeout)
                )
            )
            # last_latency_point = await latency_point(host=host, port=port, timeout=timeout)
        for i in range(runs):
            latency_points.append(await tasks[i])
        return latency_points

    @staticmethod
    async def latency_point(
        host: str, port: int = 443, timeout: float = 5
    ) -> Optional[float]:
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
