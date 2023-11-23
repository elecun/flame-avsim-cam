'''
In-cabin camera monitor & data extractor window class
@Author bh.hwang@iae.re.kr
'''

import cv2
import pathlib
import paho.mqtt.client as mqtt
from PyQt6.QtGui import QImage, QPixmap, QCloseEvent
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QMessageBox
from PyQt6.uic import loadUi
from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from camera import CameraController
import json

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
Main window
'''
class CameraWindow(QMainWindow):
    def __init__(self, broker_ip_address):
        super().__init__()
        loadUi(APP_UI, self)

        self.opened_camera = {}
        self.machine_monitor = None
        self.message_api = {
            "flame/avsim/cam/mapi_record_start" : self.mapi_record_start,
            "flame/avsim/cam/mapi_record_stop" : self.mapi_record_stop,
            "flame/avsim/mapi_request_active" : self.mapi_notify_active #response directly
        }
        
        # menu
        self.actionStart_Recording.triggered.connect(self.on_select_start_recording)
        self.actionStop_Recording.triggered.connect(self.on_select_stop_recording)
        self.actionCapture_Image.triggered.connect(self.on_select_capture_image)
        self.actionConnect_All.triggered.connect(self.on_select_connect_all)

        # for mqtt connection
        self.mq_client = mqtt.Client(client_id=APP_NAME,transport='tcp',protocol=mqtt.MQTTv311, clean_session=True)
        self.mq_client.on_connect = self.on_mqtt_connect
        self.mq_client.on_message = self.on_mqtt_message
        self.mq_client.on_disconnect = self.on_mqtt_disconnect
        self.mq_client.connect_async(broker_ip_address, port=1883, keepalive=60)
        self.mq_client.loop_start()

    # camera open after show this GUI
    def start_monitor(self):
        # for manual load
        for id in camera_dev_ids:
            camera = CameraController(id)
            if camera.open():
                self.opened_camera[id] = camera
                self.opened_camera[id].image_frame_slot.connect(self.update_frame)
            else:
                lambda:QMessageBox.critical(self, "No Camera", "No Camera device connection")

        for camera in self.opened_camera.values():
            camera.begin()
    
    # internal api for starting record
    def _api_record_start(self):
        for camera in self.opened_camera.values():
            print(f"Recording start...({camera.camera_id})")
            camera.start_recording()
        self.show_on_statusbar("Start Recording...")
    
    # internal api for stopping record
    def _api_record_stop(self):
        for camera in self.opened_camera.values():
            print(f"Recording stop...({camera.camera_id})")
            camera.stop_recording()
        self.show_on_statusbar("Stopped Recording...")
        
    # capture image
    def _api_capture_image(self):
        delay = 15.0
        for camera in self.opened_camera.values():
            camera.start_capturing(delay)
        self.show_on_statusbar(f"Captured image after {delay} second(s)")
    
    # on_select event for starting record
    def on_select_start_recording(self):
        self._api_record_start()
    
    # on_select event for stopping record
    def on_select_stop_recording(self):
        self._api_record_stop()
        
    # on_select event for capturing to image(png)
    def on_select_capture_image(self):
        self._api_capture_image()
    
    # connect all camera and show on display continuously
    def on_select_connect_all(self):
        self.start_monitor()
                
    # mapi : record start
    def mapi_record_start(self, payload):
        self._api_record_start()

    # mapi : record stop
    def mapi_record_stop(self, payload):
        self._api_record_stop()
                
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
        for device in self.opened_camera.values():
            device.close()

        if self.machine_monitor!=None:
            self.machine_monitor.close()
            
        return super().closeEvent(a0)
    
    # notification
    def mapi_notify_active(self):
        if self.mq_client.is_connected():
            msg = {"app":APP_NAME, "active":True}
            self.mq_client.publish(mqtt_topic_manager, json.dumps(msg), 0)
        else:
            self.show_on_statusbar("Notified")
    
    # mqtt connection callback function
    def on_mqtt_connect(self, mqttc, obj, flags, rc):
        self.mapi_notify_active()
        
        # subscribe message api
        for topic in self.message_api.keys():
            self.mq_client.subscribe(topic, 0)
        
        self.show_on_statusbar("Connected to Broker({})".format(str(rc)))
    
    # mqtt disconnection callback function
    def on_mqtt_disconnect(self, mqttc, userdata, rc):
        self.show_on_statusbar("Disconnected to Broker({})".format(str(rc)))
    
    # mqtt message receive callback function
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
        