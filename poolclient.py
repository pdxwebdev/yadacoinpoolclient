import sys
import json
import requests
import time
import os
import multiprocessing
from multiprocessing import Process
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QPushButton, QLineEdit, QLabel
from yadacoin.miningpool import MiningPool
from yadacoin import Config

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
        self.resize(800, 325)
        self.move(300, 300)
        self.setWindowTitle('YadaCoin Pool Client')
        self.home()
    
    def closeEvent(self, event):
        self.stop_mine()
        event.accept()
    
    def home(self):
        self.logo = QLabel(self)
        self.logo.setPixmap(QPixmap("yadacoinlogo.png"))
        self.logo.resize(800, 300)
        self.logo.show()
        
        anchor = 300
        pooltext = QLabel(self)
        pooltext.setText('Pool:')
        pooltext.move(anchor - 32, 235)
        pooltext.show()
        corestext = QLabel(self)
        corestext.setText('cores:')
        corestext.move(anchor - 32, 275)
        corestext.show()
        self.pool = QLineEdit(self)
        self.pool.setText('yadacoin.io:8000')
        self.pool.move(anchor + 10, 235)
        self.pool.resize(225, 30)
        self.cores = QLineEdit(self)
        self.cores.setText(str(multiprocessing.cpu_count()))
        self.cores.move(anchor + 10, 275)
        self.cores.resize(25, 30)
        self.btn = QPushButton("Start mining", self)
        self.btn.move(anchor + 255, 235)
        self.btn.clicked.connect(self.start_mine)
        self.stopbtn = QPushButton("Stop mining", self)
        self.stopbtn.move(anchor + 375, 235)
        self.stopbtn.clicked.connect(self.stop_mine)
        self.stopbtn.setDisabled(True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.mine)
        self.running_processes = []
        self.show()

    def get_mine_data(self):
        return json.loads(requests.get("http://{pool}/pool".format(pool=self.pool.text())).content)
    
    def start_mine(self):
        self.stopbtn.setDisabled(False)
        self.pool.setDisabled(True)
        self.btn.setDisabled(True)
        self.running_processes = self.running_processes or []
        self.timer.start(1000)

    def stop_mine(self):
        self.stopbtn.setDisabled(True)
        self.pool.setDisabled(False)
        self.btn.setDisabled(False)
        self.timer.stop()
        if self.running_processes:
            for i, proc in enumerate(self.running_processes):
                proc.terminate()
        self.running_processes = []
    
    def mine(self):
        if len(self.running_processes) >= int(self.cores.text()):
            for i, proc in enumerate(self.running_processes):
                if not proc.is_alive():
                    proc.terminate()
                    data = self.get_mine_data()
                    p = Process(target=MiningPool.pool_mine, args=(self.pool.text(), Config.address, data['header'], data['target'], data['nonces'], data['special_min']))
                    p.start()
                    self.running_processes[i] = p
        else:
            data = self.get_mine_data()
            p = Process(target=MiningPool.pool_mine, args=(self.pool.text(), Config.address, data['header'], data['target'], data['nonces'], data['special_min']))
            p.start()
            self.running_processes.append(p)
            
        
app = QApplication(sys.argv)
gui = Window()
sys.exit(app.exec_())