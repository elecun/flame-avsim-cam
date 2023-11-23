'''
 In-Cabin Camera Monitoring and Video Recorder (with Qt6 GUI)
 @author Byunghun Hwang<bh.hwang@iae.re.kr>
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

from window import CameraWindow
from machine import MachineMonitor

# pre-defined options
WORKING_PATH = pathlib.Path(__file__).parent
APP_UI = WORKING_PATH / "gui.ui"
APP_NAME = "avsim-cam"
VIDEO_OUT_DIR = WORKING_PATH / "video"
VIDEO_FILE_EXT = "avi"
CAMERA_RECORD_FPS = 30
CAMERA_RECORD_WIDTH = 1920
CAMERA_RECORD_HEIGHT = 1080


# camera interfaces for GUI
camera_dev_ids = [0, 2, 4, 6] # ready to connect
camera_windows = {camera_dev_ids[0]:"window_camera_1", 
                  camera_dev_ids[1]:"window_camera_2", 
                  camera_dev_ids[2]:"window_camera_3", 
                  camera_dev_ids[3]:"window_camera_4"}

# for message APIs
mqtt_topic_manager = "flame/avsim/manager"

     

'''
 Entry point
'''
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', nargs='?', required=False, help="Broker IP Address", default="127.0.0.1")
    parser.add_argument('--config', nargs='?', required=False, help="Configuration File(*.cfg)", default="param.cfg")
    args = parser.parse_args()

    broker_ip_address = ""
    parameters = ""
    if args.broker is not None:
        broker_ip_address = args.broker
    if args.config is not None:
        parameters = args.config
    
    app = QApplication(sys.argv)
    window = CameraWindow(broker_ip_address=broker_ip_address)
    window.show()
    sys.exit(app.exec())
