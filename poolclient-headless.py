import sys
import os.path
yada_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'yadacoin')
print(yada_dir)
sys.path.insert(0, yada_dir)
import json
import requests
import time
import os
import multiprocessing
import yadacoin.config
import binascii
import pyrx
from random import randrange
from multiprocessing import Process, Queue
from yadacoin.config import Config
from yadacoin.miningpool import MiningPool
from yadacoin.transaction import TransactionFactory
from yadacoin.mongo import Mongo
from yadacoin.graphutils import GraphUtils


class Miner(object):
    def __init__(
        self,
        pool='',
        address='',
        cores=multiprocessing.cpu_count() - 2,
        work_size=1000,
        debug=False,
    ):
        self.pool = pool
        self.address = address
        self.cores = int(cores)
        self.work_size = int(work_size)
        self.debug = bool(int(debug))
        self.data = None
        self.nonces = []
        self.pyrx = pyrx.PyRX()

    def get_mine_data(self):
        try:
            return json.loads(requests.get("{pool}/pool".format(pool=self.pool), headers={'Connection':'close'}, timeout=5).content)
        except Exception as e:
            if self.debug:
                print(e)
            return None
        
    def mine(self):
        while True:
            if not self.nonces:
                start_nonce = randrange(0xffffffffffff)
                self.nonces.extend([start_nonce, start_nonce + self.work_size])
            try:
                self.pool_data = self.get_mine_data()
            except Exception as e:
                print(e)
                return
            if self.pool_data:
                lowest = (0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff, 0, '')
                nonce = self.nonces[0]
                start = time.time()
                seed_hash = binascii.unhexlify('4181a493b397a733b083639334bc32b407915b9a82b7917ac361816f0a1f5d4d') #sha256(yadacoin65000)
                while nonce < self.nonces[1]:
                    header = self.pool_data['header'].format(nonce=nonce)
                    bh = self.pyrx.get_rx_hash(header, seed_hash, int(self.pool_data['height']), 8)
                    hash_test = binascii.hexlify(bh).decode()
                    if hash_test.startswith('000'):
                        print(hash_test)
                    text_int = int(hash_test, 16)
                    if text_int < int(self.pool_data['target'], 16) or (self.pool_data['special_min'] and text_int < int(self.pool_data['special_target'], 16)):
                        lowest = (text_int, nonce, hash_test)
                        break

                    if text_int < lowest[0]:
                        lowest = (text_int, nonce, hash_test)
                    nonce += 1
                print(lowest[2])
                try:
                    res = requests.post("{pool}/pool-submit".format(pool=self.pool), json={
                        'nonce': '{:02x}'.format(lowest[1]),
                        'hash': lowest[2],
                        'address': self.address
                    }, headers={'Connection':'close'})
                    print(res.content)
                except Exception as e:
                    print(e)
                self.hashrate = '{}H/s'.format(int(self.work_size / (time.time() - start)))
                print(self.hashrate)
                self.nonces[0] += self.work_size
                self.nonces[1] += self.work_size
            
if __name__ == '__main__':
    multiprocessing.freeze_support()
    miner = Miner(*sys.argv[1:])
    miner.mine()