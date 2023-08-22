'''
 In-Cabin Camera Monitoring and Recorder (with Qt6)
 @author Byunghun Hwang<bh.hwang@iae.re.kr>
'''

import sys, os
import typing
from PyQt6 import QtGui
import cv2
import pathlib
import json
from PyQt6.QtGui import QImage, QPixmap, QCloseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QMessageBox
from PyQt6.uic import loadUi
from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
import timeit
import paho.mqtt.client as mqtt
from datetime import datetime
import csv
import argparse


WORKING_PATH = pathlib.Path(__file__).parent
APP_UI = WORKING_PATH / "MainWindow.ui"
APP_NAME = "avsim-cam" # application name
VIDEO_OUT_DIR = WORKING_PATH / "video"

camera_ids = [0, 2, 4, 6]
camera_windows = {camera_ids[0]:"window_camera_1", 
                  camera_ids[1]:"window_camera_2", 
                  camera_ids[2]:"window_camera_3", 
                  camera_ids[3]:"window_camera_4"}
btn_camera_open = {camera_ids[0]:"btn_camera_open_1", 
                  camera_ids[1]:"btn_camera_open_2", 
                  camera_ids[2]:"btn_camera_open_3", 
                  camera_ids[3]:"btn_camera_open_4"}
mqtt_topic_manager = "flame/avsim/manager"
_def_record_fps = 30
_def_record_width = 1920
_def_record_height = 1080

'''
camera module with thread
'''
class CameraModule(QThread):
    image_frame = pyqtSignal(QImage)

    def __init__(self, camera_id):
        super().__init__()
        self.camera_id = camera_id
        self.working = False # grabing image
        self.record_start = False # recording video
        self.video_out_path = VIDEO_OUT_DIR

    def open(self) -> bool:
        self.dev = cv2.VideoCapture(self.camera_id)
        self.fourcc = cv2.VideoWriter_fourcc(*'mp4v') # high compression but smaller (file extension : mp4)
        #self.fourcc = cv2.VideoWriter_fourcc(*'MJPG') # low compression but bigger (file extension : avi)
        
        if not self.dev.isOpened():
            return False
        
        self.working = True
        print("connected camera device : {}".format(self.camera_id))
        return True

    def run(self):
        while True:
            if self.isInterruptionRequested():
                break
            
            start_t = timeit.default_timer()
        
            ret, frame = self.dev.read()
            
            # enable recording
            if self.record_start:
                self.video_out.write(frame)
                
            if not ret:
                self.working = False
                self.dev.release()
                break
            
            #change image to QImage
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # post processing
            end_t = timeit.default_timer()
            FPS = int(1./(end_t - start_t ))
            cv2.putText(rgb_image, "Camera #{}(fps:{})".format(self.camera_id, FPS), (10,50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 2, cv2.LINE_AA)

            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            self.image_frame.emit(qt_image)

    def close(self):
        if self.dev:
            self.requestInterruption()
            if self.record_start:
                self.video_out.release()
            self.dev.release()
            
    def pause_recording(self):
        self.record_start = False
    
    def stop_recording(self):
        if self.dev:
            self.record_start = False
            self.video_out.release()
            
        
    def start_recording(self):
        if not self.record_start:
            self.record_start_datetime = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            
            # create path
            self.video_out_path = VIDEO_OUT_DIR / self.record_start_datetime
            self.video_out_path.mkdir(parents=True, exist_ok=True)
                
            self.camera_fps = self.dev.get(cv2.CAP_PROP_FPS)
            self.camera_w = int(self.dev.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.camera_h = int(self.dev.get(cv2.CAP_PROP_FRAME_HEIGHT))

            print("recording camera({}) info : ({},{}@{})".format(self.camera_id, self.camera_w, self.camera_h, self.camera_fps))
            self.video_out = cv2.VideoWriter(str(self.video_out_path/'cam_{}.mp4'.format(self.camera_id)), self.fourcc, _def_record_fps, (self.camera_w, self.camera_h))
            self.record_start = True
    
    def begin(self):
        if self.dev.isOpened():
            self.start()
            
    def __str__(self):
        return str(self.camera_id)
            

'''
Main window
'''
class CameraMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        loadUi(APP_UI, self)

        self.device_modules = {}
        self.message_api = {
            "flame/avsim/cam/mapi_record_start" : self.mapi_record_start,
            "flame/avsim/cam/mapi_record_stop" : self.mapi_record_stop,
            "flame/avsim/mapi_request_active" : self.mapi_notify_active #response directly
        }
        
        # menu
        self.actionStart_Recording.triggered.connect(self.on_select_start_recording)
        self.actionStop_Recording.triggered.connect(self.on_select_stop_recording)

        # for manual load
        for id in camera_ids:
            camera = CameraModule(id)
            if camera.open():
                self.device_modules[id] = camera
                self.device_modules[id].image_frame.connect(self.update_frame)
                btn = self.findChild(QPushButton, btn_camera_open[id])
                btn.clicked.connect(self.device_modules[id].begin)
            else:
                btn = self.findChild(QPushButton, btn_camera_open[id])
                btn.clicked.connect(lambda:QMessageBox.critical(self, "No Camera", "No Camera device connection"))

         # for mqtt connection
        self.mq_client = mqtt.Client(client_id="flame-avsim-cam",transport='tcp',protocol=mqtt.MQTTv311, clean_session=True)
        self.mq_client.on_connect = self.on_mqtt_connect
        self.mq_client.on_message = self.on_mqtt_message
        self.mq_client.on_disconnect = self.on_mqtt_disconnect
        self.mq_client.connect_async("127.0.0.1",port=1883,keepalive=60)
        self.mq_client.loop_start()
    
    # start recording selected
    def on_select_start_recording(self):
        self.api_start_record()
    
    def on_select_stop_recording(self):
        self.api_stop_record()

                
    # message-based api
    def mapi_record_start(self, payload):
        for camera in self.device_modules.values():
            camera.start_recording()
        self.show_on_statusbar("Start Recording...")
            
    def mapi_record_stop(self, payload):
        for camera in self.device_modules.values():
            camera.stop_recording()
        self.show_on_statusbar("Stopped Recording...")
        
                
    # show message on status bar
    def show_on_statusbar(self, text):
        self.statusBar().showMessage(text)
    

    # update image frame on label area
    def update_frame(self, image):
        id = self.sender().camera_id
        pixmap = QPixmap.fromImage(image)
        window = self.findChild(QLabel, camera_windows[id])
        window.setPixmap(pixmap.scaled(window.size(), Qt.AspectRatioMode.KeepAspectRatio))

    # close event callback function by user
    def closeEvent(self, a0: QCloseEvent) -> None:
        for device in self.device_modules.values():
            device.close()

        return super().closeEvent(a0)
    
    # notification
    def mapi_notify_active(self):
        if self.mq_client.is_connected():
            msg = {"app":APP_NAME, "active":True}
            self.mq_client.publish(mqtt_topic_manager, json.dumps(msg), 0)
        else:
            self.show_on_statusbar("Notified")
    ™
    # MQTT callbacks
    def on_mqtt_connect(self, mqttc, obj, flags, rc):
        self.mapi_notify_active()
        
        # subscribe message api
        for topic in self.message_api.keys():
            self.mq_client.subscribe(topic, 0)
        
        self.show_on_statusbar("Connected to Broker({})".format(str(rc)))
        
    def on_mqtt_disconnect(self, mqttc, userdata, rc):
        self.show_on_statusbar("Disconnected to Broker({})".format(str(rc)))
        
    def on_mqtt_message(self, mqttc, userdata, msg):
        mapi = str(msg.topic)
        
        try:
            if mapi in self.message_api.keys():
                payload = json.loads(msg.payload)
                if "app" not in payload:
                    print("Message payload does not contain the app")
                    return
                
                if payload["app"] != APP_NAME:
                    self.message_api[mapi](payload)
            else:
                print("Unknown MAPI was called : {}".format(mapi))
        except json.JSONDecodeError as e:
            print("MAPI message payload connot be converted : {}".format(str(e)))
        

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', nargs='?', required=False, help="Broker Address")
    args = parser.parse_args()

    broker_address = "127.0.0.1"
    if args.broker is not None:
        broker_address = args.broker
    
    app = QApplication(sys.argv)
    window = CameraMonitor()
    window.show()
    sys.exit(app.exec())
