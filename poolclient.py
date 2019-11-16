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
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QPushButton, QLineEdit, QLabel, QMessageBox
from yadacoin.config import Config
from yadacoin.miningpool import MiningPool
from yadacoin.transaction import TransactionFactory
from yadacoin.mongo import Mongo
from yadacoin.graphutils import GraphUtils


class Window(QMainWindow):
    def __init__(self):
        configfilepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.json')
        if os.path.isfile(configfilepath):
            with open(configfilepath) as f:
                self.config = Config(json.loads(f.read()))
        else:
            self.config = Config.generate()
            with open(configfilepath, 'w') as f:
                f.write(self.config.to_json())
        
        yadacoin.config.CONFIG = self.config

        super(Window, self).__init__()
        self.cores = multiprocessing.cpu_count() - 2
        self.resize(820, 325)
        self.move(300, 300)
        self.setWindowTitle('YadaCoin Pool Client')
        self.home()
        self.debug = False
        self.data = None
        self.graph = None
    
    def closeEvent(self, event):
        self.stop_mine()
        event.accept()
    
    def home(self):
        self.logo = QLabel(self)
        self.logo.setPixmap(QPixmap(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'yadacoinlogo.png')))
        self.logo.move(0, -35)
        self.logo.resize(800, 300)
        self.logo.show()
        
        xanchor = 300
        yanchor = 165
        pooltext = QLabel(self)
        pooltext.setText('Pool:')
        pooltext.move(xanchor - 32, yanchor + 35)
        pooltext.show()
        corestext = QLabel(self)
        corestext.setText('Cores:')
        corestext.move(xanchor - 32, yanchor + 75)
        corestext.show()
        corestext = QLabel(self)
        corestext.setText('Address:')
        corestext.move(xanchor + 50, yanchor + 75)
        corestext.show()
        corestext = QLabel(self)
        corestext.setText('WIF/Seed:')
        corestext.move(xanchor - 32, yanchor + 115)
        corestext.show()
        self.nonces = []
        self.work_size = 10000
        self.pool = QLineEdit(self)
        self.pool.setText('https://yadacoin.io')
        self.pool.move(xanchor + 10, yanchor + 35)
        self.pool.resize(225, 30)
        self.address = QLineEdit(self)
        self.address.setText(self.config.address)
        self.address.move(xanchor + 115, yanchor + 75)
        self.address.resize(325, 30)
        self.address.setReadOnly(True)
        self.address.setStyleSheet("background-color: rgb(200, 200, 200); color: rgb(100, 100, 100); border: none;")
        self.wif = QLineEdit(self)
        self.wif.setText(self.config.wif)
        self.wif.move(xanchor + 40, yanchor + 115)
        self.wif.resize(460, 30)
        self.wif.setReadOnly(True)
        self.wif.setStyleSheet("background-color: rgb(200, 200, 200); color: rgb(100, 100, 100); border: none;")
        self.cores = QLineEdit(self)
        self.cores.setText(str(multiprocessing.cpu_count() - 2))
        self.cores.move(xanchor + 15, yanchor + 75)
        self.cores.resize(25, 30)
        self.btn = QPushButton("Start mining", self)
        self.btn.move(xanchor + 255, yanchor + 35)
        self.btn.clicked.connect(self.start_mine)
        self.stopbtn = QPushButton("Stop mining", self)
        self.stopbtn.move(xanchor + 375, yanchor + 35)
        self.stopbtn.clicked.connect(self.stop_mine)
        self.stopbtn.setDisabled(True)
        self.timer = QTimer(self)
        self.timer.setSingleShot(False)
        self.timer.timeout.connect(self.mine)
        self.running_processes = []
        self.hashrate = QLabel(self)
        self.hashrate.move(25, yanchor + 75)
        self.pyrx = pyrx.PyRX()
        self.show()

    def get_mine_data(self):
        try:
            return json.loads(requests.get("{pool}/pool".format(pool=self.pool.text()), headers={'Connection':'close'}, timeout=5).content)
        except Exception as e:
            if self.debug:
                print(e)
            return None

    def get_graph_info(self, q, pool_text, bulletin_secret):
        try:
            q.put(json.loads(requests.get("{pool}/get-graph-info?bulletin_secret={bulletin_secret}".format(pool=pool_text, bulletin_secret=bulletin_secret), headers={'Connection':'close'}).content))
        except Exception as e:
            if self.debug:
                print(e)
            return None
    
    def start_mine(self):
        self.graph = Queue()
        #self.get_graph_info_p = Process(target=self.get_graph_info, args=(self.graph, self.pool.text(), self.config.bulletin_secret))
        #self.get_graph_info_p.start()
        print('Starting YadaCoin Mining...')
        self.stopbtn.setDisabled(False)
        self.pool.setDisabled(True)
        self.cores.setDisabled(True)
        self.btn.setDisabled(True)
        self.running_processes = self.running_processes or []
        self.data = Queue()
        self.timer.start(1000)

    def stop_mine(self):
        self.stopbtn.setDisabled(True)
        self.pool.setDisabled(False)
        self.cores.setDisabled(False)
        self.btn.setDisabled(False)
        self.timer.stop()
        if self.running_processes:
            for i, proc in enumerate(self.running_processes):
                proc['process'].terminate()
        self.running_processes = []
    
    def mine(self):
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
                requests.post("{pool}/pool-submit".format(pool=self.pool.text()), json={
                    'nonce': '{:02x}'.format(lowest[1]),
                    'hash': lowest[2],
                    'address': self.address.text()
                }, headers={'Connection':'close'})
            except Exception as e:
                print(e)
            self.hashrate.setText('{}H/s'.format(int(self.work_size / (time.time() - start))))
            self.nonces[0] += self.work_size
            self.nonces[1] += self.work_size
            
if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    gui = Window()
    sys.exit(app.exec_())
