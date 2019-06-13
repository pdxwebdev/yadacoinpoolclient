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
from random import randrange
from multiprocessing import Process
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QPushButton, QLineEdit, QLabel
from yadacoin.config import Config
from yadacoin.miningpool import MiningPool


class Window(QMainWindow):
    def __init__(self):
        configfilepath = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'config.json')
        if os.path.isfile(configfilepath):
            with open(configfilepath) as f:
                Config.from_dict(json.loads(f.read()))
        else:
            Config.generate()
            with open(configfilepath, 'w') as f:
                f.write(Config.to_json())

        super(Window, self).__init__()
        self.cores = multiprocessing.cpu_count()
        self.resize(820, 325)
        self.move(300, 300)
        self.setWindowTitle('YadaCoin Pool Client')
        self.home()
        self.debug = False
    
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
        self.pool.setText('https://yadacoin.io')
        self.pool.move(xanchor + 10, yanchor + 35)
        self.pool.resize(225, 30)
        self.address = QLineEdit(self)
        self.address.setText(Config.address)
        self.address.move(xanchor + 115, yanchor + 75)
        self.address.resize(325, 30)
        self.wif = QLineEdit(self)
        self.wif.setText(Config.wif)
        self.wif.move(xanchor + 40, yanchor + 115)
        self.wif.resize(460, 30)
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
            return json.loads(requests.get("{pool}/pool".format(pool=self.pool.text()), verify=False, headers={'Connection':'close'}).content)
        except Exception as e:
            if self.debug:
                print(e)
            return None
    
    def start_mine(self):
        print('Starting YadaCoin Mining...')
        self.stopbtn.setDisabled(False)
        self.pool.setDisabled(True)
        self.cores.setDisabled(True)
        self.btn.setDisabled(True)
        self.running_processes = self.running_processes or []
        self.data = self.get_mine_data()
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
                    self.data = self.get_mine_data()
                    if self.data:
                        p = Process(target=MiningPool.pool_mine, args=(self.pool.text(), Config.address, self.data['header'], int(self.data['target'], 16), self.nonces, self.data['special_min'], self.data['special_target']))
                        p.start()
                        self.running_processes[i] = {'process': p, 'start_time': time.time(), 'work_size': self.nonces[1] - self.nonces[0]}
                        print('mining process started...')
                        self.nonces[0] += self.work_size
                        self.nonces[1] += self.work_size
        else:
            if self.data:
                #res = MiningPool.pool_mine(self.pool.text(), Config.address, self.data['header'], int(self.data['target'], 16), self.nonces, self.data['special_min'], self.data['special_target'])
                p = Process(target=MiningPool.pool_mine, args=(self.pool.text(), Config.address, self.data['header'], int(self.data['target'], 16), self.nonces, self.data['special_min'], self.data['special_target']))
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
