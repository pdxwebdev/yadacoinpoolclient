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
        self.cores = multiprocessing.cpu_count()
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
        self.work_size = 1000000
        self.pool = QLineEdit(self)
        self.pool.setText('http://0.0.0.0:8000')
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
        self.cores.setText(str(multiprocessing.cpu_count()))
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
        if len(self.running_processes) >= int(self.cores.text()):
            for i, proc in enumerate(self.running_processes):
                if not proc['process'].is_alive():
                    self.hashrate.setText("{:,}/Hs".format(int((proc['work_size']) / (time.time() - self.running_processes[i]['start_time'])) * int(self.cores.text())))
                    proc['process'].terminate()
                    try:
                        self.pool_data = self.get_mine_data()
                    except Exception as e:
                        print(e)
                        return
                    if self.pool_data:
                        p = Process(target=MiningPool.pool_mine, args=(self.pool.text(), self.config.address, self.pool_data['height'], self.pool_data['header'], int(self.pool_data['target'], 16), self.nonces, self.pool_data['special_min'], self.pool_data['special_target']))
                        p.start()
                        self.running_processes[i] = {'process': p, 'start_time': time.time(), 'work_size': self.nonces[1] - self.nonces[0]}
                        print('mining process started...')
                        self.nonces[0] += self.work_size
                        self.nonces[1] += self.work_size
        else:
            try:
                self.pool_data = self.get_mine_data()
            except Exception as e:
                print(e)
                return
            if self.pool_data:
                #res = MiningPool.pool_mine(self.pool.text(), self.config.address, self.pool_data['height'], self.pool_data['header'], int(self.pool_data['target'], 16), self.nonces, self.pool_data['special_min'], self.pool_data['special_target'])
                p = Process(target=MiningPool.pool_mine, args=(self.pool.text(), self.config.address, self.pool_data['height'], self.pool_data['header'], int(self.pool_data['target'], 16), self.nonces, self.pool_data['special_min'], self.pool_data['special_target']))
                p.start()
                self.running_processes.append({'process': p, 'start_time': time.time(), 'work_size': self.nonces[1] - self.nonces[0]})
                print('mining process started...')
                self.nonces[0] += self.work_size
                self.nonces[1] += self.work_size
            
if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    gui = Window()
    sys.exit(app.exec_())
