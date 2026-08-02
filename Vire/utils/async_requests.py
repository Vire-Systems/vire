"""
This module(async_requests) is an asynchronous set-up for requests (aiohttp). Keeps a pool of connections.

Function(s):
------------
- send_request
"""

import asyncio
import httpx
from shared.errors import vire_errors as errors

MAX_CONCURRENT = 50
TIMEOUT = 5
MAX_ALIVE = 50

client: httpx.AsyncClient | None = None

semaphore = asyncio.Semaphore(MAX_ALIVE)

limits = httpx.Limits(
    max_keepalive_connections=MAX_ALIVE, max_connections=MAX_CONCURRENT
)

timeout = httpx.Timeout(TIMEOUT, connect=5.0, read=5.0)


async def _send_request_helper(client: httpx.AsyncClient, url: str) -> httpx.Response:
    """Helper for send_request."""
    async with semaphore:
        try:
            response = await client.get(url, timeout=timeout)
            _ = response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            raise errors.RepoFileFetchError(
                error_title=f"Fetching file (raw url: {url}) failed. Provider's API returned status code : '{status_code}'."
            )

        except Exception:
            raise errors.RepoFileFetchError(
                error_title=f"Fetching file (raw url: {url}) failed. Vire faced unexpected errors while fetching (Internal Error)."
            )


async def send_request(url: str) -> httpx.Response:
    """
    Async implementation for requests (using httpx). Performs a GET request on the specified URL.
    
    Behavior:
    ---------
    - Works asynchronously using asyncio.Semaphore for limiting max outbound requests.
    - Semaphore blocks until a thread calls release().
    - Uses httpx.Limits to avoid OOM and 100k requests under load.
    - Timeout of 5s is used as to not wait for long periods of time.
    
    Args:
    -----
    - client - httpx.AsyncClient, an asynchronous HTTP client with connection pooling, HTTP/2, redirects, cookie persistence, etc.
    - url - The url to perform a GET request on.

    Raises:
    -------
    - RepoFileFetchError
    """
    global client

    if client is None:
        client = httpx.AsyncClient(limits=limits)

    return await _send_request_helper(client, url)
