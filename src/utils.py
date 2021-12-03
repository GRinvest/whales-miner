import asyncio
import logging
import random

log = logging.getLogger()
def exponential_backoff_delay(start, mx, max_retries):
    retries = 0
    delay = start
    async def sleep():
        nonlocal delay, retries
        if retries == max_retries:
            raise "Retries exceeded, aborting..."
        
        log.info("Retrying in {:.2f} seconds...".format(delay))
        await asyncio.sleep(delay)
        retries += 1
        delay = min(mx, delay * 2 ** retries + random.uniform(0, 1))

    def reset_delay():
        nonlocal retries, delay
        retries = 0
        delay = start

    return (sleep, reset_delay)


def pluralize(n, forms):
    if n == 1:
        return forms[0]
    return forms[1]