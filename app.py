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
from PyQt6.QtCore import QObject, Qt, QTimer, QThread, pyqtSignal
import timeit
import paho.mqtt.client as mqtt
from datetime import datetime
import argparse

# pre-defined options
WORKING_PATH = pathlib.Path(__file__).parent
APP_UI = WORKING_PATH / "MainWindow.ui"
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
btn_camera_open = {camera_dev_ids[0]:"btn_camera_open_1", 
                  camera_dev_ids[1]:"btn_camera_open_2", 
                  camera_dev_ids[2]:"btn_camera_open_3", 
                  camera_dev_ids[3]:"btn_camera_open_4"}

# for message APIs
mqtt_topic_manager = "flame/avsim/manager"


'''
camera controller class
'''
class CameraController(QThread):
    image_frame_slot = pyqtSignal(QImage)

    def __init__(self, camera_id):
        super().__init__()

        self.camera_id = camera_id # camera id
        self.recording_start_trigger = False # True means starting
        self.is_recording = False # video recording status
        self.video_out_path = VIDEO_OUT_DIR
        self.grabber = None
        self.video_writer = None

        self.start_trigger_on = False # trigger for starting 


    # open camera device (if open success, return True, otherwise return False)
    def open(self) -> bool:
        self.grabber = cv2.VideoCapture(self.camera_id, cv2.CAP_V4L2) # video capture instance with opencv
        
        if not self.grabber.isOpened():
            return False
        
        print(f"[Info] connected camera device {self.camera_id}")

        self.is_recording = False
        return True

    # recording by thread
    def run(self):
        while True:
            if self.isInterruptionRequested():
                print(f"camera {self.camera_id} controller worker is interrupted")
                break
            
            t_start = timeit.default_timer()
            ret, frame = self.grabber.read() # grab
            t_end = timeit.default_timer()
            framerate = int(1./(t_end - t_start))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) # warning! it should be converted from BGR to RGB. But each camera IR turns ON, grayscale is able to use. (grayscale is optional)

            # recording if recording status flag is on
            if self.is_recording:
                self.video_record(frame)

            # camera monitoring (only for RGB color image)
            cv2.putText(frame_rgb, f"Camera #{self.camera_id}(fps:{framerate})", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 2, cv2.LINE_AA)
            _h, _w, _ch = frame_rgb.shape
            _bpl = _ch*_w # bytes per line
            qt_image = QImage(frame_rgb.data, _w, _h, _bpl, QImage.Format.Format_RGB888)
            self.image_frame_slot.emit(qt_image)

    # video recording process impl.
    def video_record(self, frame):
        if self.video_writer != None:
            self.video_writer.write(frame)

    # create new video writer to save as video file
    def create_video_writer(self):
        if self.is_recording:
            self.release_video_writer()

        record_start_datetime = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        
        self.video_out_path = VIDEO_OUT_DIR / record_start_datetime
        self.video_out_path.mkdir(parents=True, exist_ok=True)

        camera_fps = int(self.grabber.get(cv2.CAP_PROP_FPS))
        camera_w = int(self.grabber.get(cv2.CAP_PROP_FRAME_WIDTH))
        camera_h = int(self.grabber.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*'MJPG') # low compression but bigger (file extension : avi)

        print(f"recording camera({self.camera_id}) info : ({camera_w},{camera_h}@{camera_fps})")
        self.video_writer = cv2.VideoWriter(str(self.video_out_path/f'cam_{self.camera_id}.{VIDEO_FILE_EXT}'), fourcc, CAMERA_RECORD_FPS, (camera_w, camera_h))

    # start video recording
    def start_recording(self):
        if not self.is_recording:
            self.create_video_writer()
            self.is_recording = True # working on thread

    # stop video recording
    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
            #self.release_video_writer()

    # destory the video writer
    def release_video_writer(self):
        if self.video_writer:
            self.video_writer.release()

    # close this camera device
    def close(self):
        self.requestInterruption() # to quit for thread
        self.quit()
        self.wait(1000)

        self.release_video_writer()
        self.grabber.release()
        print(f"camera controller {self.camera_id} is terminated successfully")
    
    # thread start
    def begin(self):
        if self.grabber.isOpened():
            self.start()
            
    def __str__(self):
        return str(self.camera_id)
            

'''
Main window
'''
class CameraMonitor(QMainWindow):
    def __init__(self, broker_ip_address):
        super().__init__()
        loadUi(APP_UI, self)

        self.opened_camera = {}
        self.message_api = {
            "flame/avsim/cam/mapi_record_start" : self.mapi_record_start,
            "flame/avsim/cam/mapi_record_stop" : self.mapi_record_stop,
            "flame/avsim/mapi_request_active" : self.mapi_notify_active #response directly
        }
        
        # menu
        self.actionStart_Recording.triggered.connect(self.on_select_start_recording)
        self.actionStop_Recording.triggered.connect(self.on_select_stop_recording)

        # for manual load
        for id in camera_dev_ids:
            camera = CameraController(id)
            if camera.open():
                self.opened_camera[id] = camera
                self.opened_camera[id].image_frame_slot.connect(self.update_frame)
                btn = self.findChild(QPushButton, btn_camera_open[id])
                btn.clicked.connect(self.opened_camera[id].begin)
            else:
                btn = self.findChild(QPushButton, btn_camera_open[id])
                btn.clicked.connect(lambda:QMessageBox.critical(self, "No Camera", "No Camera device connection"))

         # for mqtt connection
        self.mq_client = mqtt.Client(client_id=APP_NAME,transport='tcp',protocol=mqtt.MQTTv311, clean_session=True)
        self.mq_client.on_connect = self.on_mqtt_connect
        self.mq_client.on_message = self.on_mqtt_message
        self.mq_client.on_disconnect = self.on_mqtt_disconnect
        self.mq_client.connect_async(broker_ip_address, port=1883, keepalive=60)
        self.mq_client.loop_start()

    # camera open after show this GUI
    def start_monitor(self):
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
    
    # start recording selected
    def on_select_start_recording(self):
        self._api_record_start()
    
    def on_select_stop_recording(self):
        self._api_record_stop()
                
    # message-based api
    def mapi_record_start(self, payload):
        self._api_record_start()
            
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

        return super().closeEvent(a0)
    
    # notification
    def mapi_notify_active(self):
        if self.mq_client.is_connected():
            msg = {"app":APP_NAME, "active":True}
            self.mq_client.publish(mqtt_topic_manager, json.dumps(msg), 0)
        else:
            self.show_on_statusbar("Notified")
    
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
        

'''
 Entry point
'''
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--broker', nargs='?', required=False, help="Broker IP Address")
    args = parser.parse_args()

    broker_ip_address = "127.0.0.1"
    if args.broker is not None:
        broker_ip_address = args.broker
    
    app = QApplication(sys.argv)
    window = CameraMonitor(broker_ip_address=broker_ip_address)
    window.show()
    window.start_monitor()
    sys.exit(app.exec())
