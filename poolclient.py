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
        self.registration_status = QLabel(self)
        self.registration_status.setText('click "start mining" button')
        self.registration_status.move(22, yanchor + 80)
        self.registration_status.resize(250, 20)
        self.registration_status.show()
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
        self.invite_timer = QTimer(self)
        self.invite_timer.setSingleShot(False)
        self.invite_timer.timeout.connect(self.invite_status)
        self.accept_invite_timer = QTimer(self)
        self.accept_invite_timer.setSingleShot(False)
        self.accept_invite_timer.timeout.connect(self.accept_invite_status)
        self.running_processes = []
        self.hashrate = QLabel(self)
        self.hashrate.move(25, yanchor + 75)
        self.invite = QPushButton("Request invite", self)
        self.invite.move(40, yanchor + 105)
        self.invite.resize(150, 30)
        self.invite.setDisabled(True)
        self.invite.clicked.connect(self.request_invite)
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
    
    def request_invite(self):
        self.invite_q = Queue()
        p = Process(target=self.request_invite_process, args=(self.invite_q,))
        p.start()
        self.invite_timer.start(1000)
    
    def accept_invite(self):
        self.accept_invite_q = Queue()
        transaction = TransactionFactory(
            block_height=0,
            bulletin_secret=self.graph['invited']['bulletin_secret'],
            username=self.graph['invited']['username'],
            value=int([x for x in self.graph['invited']['outputs'] if x['to'] == self.config.address][0]['value']),
            fee=0,
            public_key=self.config.public_key,
            private_key=self.config.private_key,
            to=[x for x in self.graph['invited']['outputs'] if x['to'] != self.config.address][0]['to'],
            inputs=[{'id': self.graph['invited']['id']}],
            skip_money=True # because we don't have a local copy of the blockchain
        )
        p = Process(target=self.accept_invite_process, args=(self.accept_invite_q, transaction.transaction.to_dict()))
        p.start()
        self.invite_timer.start(1000)

    def accept_invite_process(self, q, transaction):
        self.invite.setText("Wait...")
        self.invite.setDisabled(True)
        try:
            q.put(json.loads(
                requests.post(
                    "{pool}/transaction?bulletin_secret={bulletin_secret}".format(
                        pool=self.pool.text(),
                        bulletin_secret=self.config.bulletin_secret
                    ), 
                    json=transaction,
                    headers={'Connection':'close',}
                ).content))
        except Exception as e:
            self.invite.setDisabled(False)
            self.invite.setText("Error...{}".format(e))
            if self.debug:
                print(e)
            return None

    def request_invite_process(self, q):
        self.invite.setText("Wait...")
        self.invite.setDisabled(True)
        try:
            q.put(json.loads(
                requests.post(
                    "{pool}/create-relationship".format(pool=self.pool.text()), 
                    json={
                        'bulletin_secret': self.config.bulletin_secret,
                        'to': self.config.address,
                        'username': self.config.username
                    },
                    headers={'Connection':'close',}
                ).content))
        except Exception as e:
            self.invite.setDisabled(False)
            self.invite.setText("Error...{}".format(e))
            if self.debug:
                print(e)
            return None

    def invite_status(self):
        try:
            self.invite_q = self.invite_q.get_nowait()
        except:
            return
        if self.invite_q.get('success') == True:
            self.invite.setDisabled(True)
            self.invite.setText("Invite complete!")
        else:
            self.invite.setDisabled(False)
        self.invite_timer.stop()

    def accept_invite_status(self):
        try:
            self.accept_invite_q = self.accept_invite_q.get_nowait()
        except:
            return
        if self.accept_invite_q.get('success') == True:
            self.invite.setDisabled(True)
            self.invite.setText("Invite complete!")
        else:
            self.invite.setDisabled(False)
        self.invite_timer.stop()
    
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
        self.invite_timer.stop()

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
        """
        try:
            self.graph = self.graph.get_nowait()
        except:
            return
        if self.graph.get('invited'):
            self.registration_status.setText('Join status: Invited')
            self.invite.setText('Accept invite')
            self.invite.setDisabled(False)
            self.invite.clicked.disconnect()
            self.invite.clicked.connect(self.accept_invite)
        elif self.graph.get('pending_registration'):
            self.registration_status.setText('Join status: Pending')
            self.invite.clicked.disconnect()
            self.invite.setText('Accept invite')
            self.invite.setDisabled(True)
        elif self.graph['registered']:
            self.registration_status.setText('Join status: Registered')
            self.invite.setDisabled(True)
        else:
            self.invite.setDisabled(False)
            return
        """
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
                        p = Process(target=MiningPool.pool_mine, args=(self.pool.text(), self.config.address, self.pool_data['header'], int(self.pool_data['target'], 16), self.nonces, self.pool_data['special_min'], self.pool_data['special_target']))
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
                #res = MiningPool.pool_mine(self.pool.text(), self.config.address, self.pool_data['header'], int(self.pool_data['target'], 16), self.nonces, self.pool_data['special_min'], self.pool_data['special_target'])
                p = Process(target=MiningPool.pool_mine, args=(self.pool.text(), self.config.address, self.pool_data['header'], int(self.pool_data['target'], 16), self.nonces, self.pool_data['special_min'], self.pool_data['special_target']))
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
