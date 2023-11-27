'''
In-Cabin Camera Controller Class
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
from datetime import datetime
from ultralytics import YOLO
import csv
from itertools import chain

# pre-defined options
WORKING_PATH = pathlib.Path(__file__).parent
APP_UI = WORKING_PATH / "gui.ui"
APP_NAME = "avsim-cam"
DATA_OUT_DIR = WORKING_PATH / "data"
VIDEO_FILE_EXT = "avi"
CAMERA_RECORD_FPS = 30
CAMERA_RECORD_WIDTH = 1920
CAMERA_RECORD_HEIGHT = 1080


# camera interfaces for GUI
camera_dev_ids = [0, 2, 4, 6] # ready to connect


'''
camera controller class
'''
class CameraController(QThread):
    image_frame_slot = pyqtSignal(QImage)

    def __init__(self, camera_id):
        super().__init__()

        self.camera_id = camera_id # camera idinfo
        self.recording_start_trigger = False # True means starting
        self.is_recording = False # video recording status
        self.is_capturing = False # image capturing status
        self.data_out_path = DATA_OUT_DIR
        self.grabber = None
        self.raw_video_writer = None
        self.processed_video_writer = None
        self.pose_csvfile = None
        self.pose_csvfile_writer = None
        self.capture_start_time = timeit.default_timer()
        self.capture_delay = 1 # 1 sec

        self.start_trigger_on = False # trigger for starting 

        # for pose estimation
        print("Load HPE model...")
        self.hpe_model = YOLO(model="./model/yolov8x-pose.pt")
        self.hpe_activated = True


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
            
            t_start = datetime.now()
            ret, frame = self.grabber.read() # grab

            if frame is not None:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) # warning! it should be converted from BGR to RGB. But each camera IR turns ON, grayscale is able to use. (grayscale is optional)

                # performing pose estimation
                if self.hpe_activated:
                    results = self.hpe_model.predict(frame_rgb, iou=0.7, conf=0.7, verbose=False)

                    # count found
                    log_bbox = []
                    log_kps = []
                    if len(results[0].boxes)==0:
                        log_bbox = [float('nan') for i in range(4)]
                        log_kps = [float('nan') for i in range(17*2)]
                    else:
                        # draw key points
                        for kps in results[0].keypoints.xy.tolist(): #for multi-person
                            for kp in kps:
                                cv2.circle(frame_rgb, center=(int(kp[0]), int(kp[1])), radius=7, color=(255,0,0), thickness=-1)
                                log_kps = log_kps + kp
                        
                        # draw bounding box
                        for bbox in results[0].boxes.xyxy.tolist():
                            # cv2.rectangle(frame_rgb, pt1=(int(bbox[0]), int(bbox[1])), pt2=(int(bbox[2]), int(bbox[3])), color=(255,0,0), thickness=1)
                            log_bbox = log_bbox + bbox

                # recording if recording status flag is on
                if self.is_recording:
                    self.raw_video_record(frame)
                    self.processed_video_record(frame_rgb)
                    logdata = [t_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]] + log_kps + log_bbox + [results[0].speed['preprocess'], results[0].speed['inference'], results[0].speed['postprocess']]
                    self.pose_csvfile_writer.writerow(logdata)
                elif self.is_capturing:
                    if timeit.default_timer()-self.capture_start_time>self.capture_delay:
                        cv2.imwrite(f"{self.camera_id}.png", frame)
                        print(f"Captured image from {self.camera_id}")
                        self.is_capturing = False

                # camera monitoring (only for RGB color image)
                t_end = datetime.now()
                framerate = int(1./(t_end - t_start).total_seconds())
                cv2.putText(frame_rgb, f"Camera #{self.camera_id}(fps:{framerate}, processing time:{int(results[0].speed['preprocess']+results[0].speed['inference']+results[0].speed['postprocess'])}ms)", (10,50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 2, cv2.LINE_AA)
                cv2.putText(frame_rgb, t_start.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3], (10, 1070), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 2, cv2.LINE_AA)

                _h, _w, _ch = frame_rgb.shape
                _bpl = _ch*_w # bytes per line
                qt_image = QImage(frame_rgb.data, _w, _h, _bpl, QImage.Format.Format_RGB888)
                self.image_frame_slot.emit(qt_image)

    # video recording process impl.
    def raw_video_record(self, frame):
        if self.raw_video_writer != None:
            self.raw_video_writer.write(frame)

    # processed video recording impl.
    def processed_video_record(self, frame):
        if self.processed_video_writer != None:
            self.processed_video_writer.write(frame)

    # create new video writer to save as video file
    def create_raw_video_writer(self):
        if self.is_recording:
            self.release_video_writer()

        record_start_datetime = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        
        self.data_out_path = DATA_OUT_DIR / record_start_datetime
        self.data_out_path.mkdir(parents=True, exist_ok=True)

        camera_fps = int(self.grabber.get(cv2.CAP_PROP_FPS))
        camera_w = int(self.grabber.get(cv2.CAP_PROP_FRAME_WIDTH))
        camera_h = int(self.grabber.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fourcc = cv2.VideoWriter_fourcc(*'MJPG') # low compression but bigger (file extension : avi)

        print(f"recording camera({self.camera_id}) info : ({camera_w},{camera_h}@{camera_fps})")
        self.raw_video_writer = cv2.VideoWriter(str(self.data_out_path/f'cam_{self.camera_id}.{VIDEO_FILE_EXT}'), fourcc, CAMERA_RECORD_FPS, (camera_w, camera_h))
        self.processed_video_writer = cv2.VideoWriter(str(self.data_out_path/f'proc_cam_{self.camera_id}.{VIDEO_FILE_EXT}'), fourcc, CAMERA_RECORD_FPS, (camera_w, camera_h))
        self.pose_csvfile = open(self.data_out_path / "keypoints.csv", mode="a+", newline='')
        self.pose_csvfile_writer = csv.writer(self.pose_csvfile)

    # start video recording
    def start_recording(self):
        if not self.is_recording:
            self.create_raw_video_writer()
            self.is_recording = True # working on thread

    # stop video recording
    def stop_recording(self):
        if self.is_recording:
            self.is_recording = False
    
    # start image capturing        
    def start_capturing(self, delay_sec:float=1.0):
        if not self.is_capturing:
            self.capture_start_time = timeit.default_timer()
            self.capture_delay = delay_sec
            self.is_capturing = True

    # destory the video writer
    def release_video_writer(self):
        if self.raw_video_writer:
            self.raw_video_writer.release()

        if self.processed_video_writer:
            self.processed_video_writer.release()
        

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
       