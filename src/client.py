import asyncio
from typing import Callable, Any
import json
import logging
import requests
import numpy as np

log = logging.getLogger('pool')

class PoolClient:
    url: str
    current_task: any

    def __init__(self, url, wallet) -> None:
        self.url = url
        self.wallet = wallet

    def report_solution(self, solution):
        response = requests.post(f'{self.url}/submit', json={
            'giver': solution['giver'],
            'miner_addr': self.wallet,
            'inputs': [solution['input']]
        })
        data = response.ok
        return data


    def load_next_task(self):
        response = requests.get(f'{self.url}/job')
        data = response.json()
        data['seed'] = bytes.fromhex(data['seed'])
        data['prefix'] = np.random.randint(0, 255, 16, np.uint8).tobytes()
        data['complexity'] = bytes.fromhex(data['complexity'])
        return data