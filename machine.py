'''
In-cabin monitoring system performance monitor
@author bh.hwang@iae.re.kr
'''

import sys, os
from PyQt6 import QtGui
import cv2
import pathlib
import json
from PyQt6.QtGui import QImage, QPixmap, QCloseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QMessageBox
from PyQt6.uic import loadUi
from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal, pyqtSlot
import timeit
import paho.mqtt.client as mqtt
from datetime import datetime
import argparse
import time
from ultralytics import YOLO
import math
import pynvml

# for gpu usage monitor
class MachineMonitor(QThread):
    gpu_monitor_slot = pyqtSignal(dict)

    def __init__(self, time_ms):
        super().__init__()

        self.time_ms = time_ms
        self.gpu_handle = []
        self.time_ms = time_ms

        # for gpu status
        pynvml.nvmlInit()
        self.gpu_count = pynvml.nvmlDeviceGetCount()
        for gpu_id in range(self.gpu_count):
            self.gpu_handle.append(pynvml.nvmlDeviceGetHandleByIndex(gpu_id))

    def run(self):
        while True:
            if self.isInterruptionRequested():
                break

            for handle in self.gpu_handle:
                info = pynvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_status = {"gpu_count":int(self.gpu_count), "gpu_usage":int(info.gpu), "gpu_memory_usage":int(info.memory)}
                self.gpu_monitor_slot.emit(gpu_status)

            QThread.msleep(self.time_ms)
        
    # close machine(gpu) resource monitoring class termination
    def close(self):
        pynvml.nvmlShutdown()
        self.requestInterruption() # to quit for thread
        self.quit()
        self.wait(1000)
