#!/usr/bin/env python

from time import time
from websockets import exceptions
import websockets
import asyncio
import click


async def measure_latency(
    host: str,
    port: int = 443,
    timeout: float = 5,
    runs: int = 1,
    wait: float = 0,
) -> list:
    """
    :rtype: list
    Builds a list composed of latency_points
    """
    tasks = []
    latency_points = []
    for i in range(runs):
        await asyncio.sleep(wait)
        tasks.append(asyncio.create_task(latency_point(host=host, port=port, timeout=timeout)))
        # last_latency_point = await latency_point(host=host, port=port, timeout=timeout)
    for i in range(runs):
        latency_points.append(await tasks[i])
    return latency_points


async def latency_point(host: str, port: int = 443, timeout: float = 5) -> [float, None]:
    '''
    :rtype: Returns float if possible
    Calculate a latency point using sockets. If something bad happens the point returned is None
    '''
    # New Socket and Time out
    # Start a timer
    s_start = time()

    # Try to Connect
    uri = f"ws://{host}:{port}"
    try:
        async with websockets.connect(uri, timeout=timeout):
            pass
    except exceptions.InvalidMessage:
        pass
    except exceptions.InvalidStatusCode:
        pass
    except Exception as e:
        return None

    # Stop Timer
    s_runtime = (time() - s_start) * 1000
    return float(s_runtime)


@click.command()
@click.option('-h', '--host', default='google.com', help='host to check latency')
@click.option('-p', '--port', default=443, help='port to check')
@click.option('-r', '--runs', default=1, help='port to check')
def main(host, port, runs):
    loop = asyncio.get_event_loop()
    latency = loop.run_until_complete(measure_latency(host=host, port=port, runs=runs))
    print(latency)


if __name__ == '__main__':
    main()
