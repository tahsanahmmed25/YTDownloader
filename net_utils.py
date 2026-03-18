import random
import time
import requests

from logging_utils import get_logger

_log = get_logger()


def request_with_retry(method,
                       url,
                       *,
                       retries=3,
                       backoff=0.6,
                       timeout=10,
                       **kwargs):
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except Exception as exc:
            last_err = exc
            _log.warning("Network attempt %s failed for %s: %s", attempt + 1, url, exc)
            response = getattr(exc, "response", None)
            if response is not None:
                code = int(getattr(response, "status_code", 0) or 0)
                # Do not retry on permanent client errors.
                if 400 <= code < 500 and code not in (408, 429):
                    break
            if attempt == retries - 1:
                break
            sleep_time = backoff * (2 ** attempt) + random.uniform(0, 0.2)
            time.sleep(sleep_time)
    raise last_err


def get_json(url, *, retries=3, timeout=10, **kwargs):
    resp = request_with_retry(
        "GET",
        url,
        retries=retries,
        timeout=timeout,
        **kwargs
    )
    return resp.json()


def get_bytes(url, *, retries=3, timeout=10, **kwargs):
    resp = request_with_retry(
        "GET",
        url,
        retries=retries,
        timeout=timeout,
        **kwargs
    )
    return resp.content
