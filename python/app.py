'''
 In-Cabin Camera Monitoring and Recorder (with Qt6)
 @author Byunghun Hwang<bh.hwang@iae.re.kr>
'''

import sys
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


WORKING_PATH = pathlib.Path(__file__).parent
APP_UI = WORKING_PATH / "MainWindow.ui"

camera_ids = [0, 2, 4, 6]
camera_windows = {camera_ids[0]:"window_camera_1", 
                  camera_ids[1]:"window_camera_2", 
                  camera_ids[2]:"window_camera_3", 
                  camera_ids[3]:"window_camera_4"}
btn_camera_open = {camera_ids[0]:"btn_camera_open_1", 
                  camera_ids[1]:"btn_camera_open_2", 
                  camera_ids[2]:"btn_camera_open_3", 
                  camera_ids[3]:"btn_camera_open_4"}

'''
camera module with thread
'''
class CameraModule(QThread):
    image_frame = pyqtSignal(QImage)

    def __init__(self, camera_id):
        super().__init__()
        self.camera_id = camera_id
        self.working = False

    def open(self) -> bool:
        self.dev = cv2.VideoCapture(self.camera_id)
        if not self.dev.isOpened():
            # print("cannot connect camera device {}".format(self.camera_id))
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
            if not ret:
                self.working = False
                self.dev.release()
                break
            
            #change image to QImage
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # post processing
            end_t = timeit.default_timer()
            FPS = int(1./(end_t - start_t ))
            cv2.putText(rgb_image, "Camera #{}({})".format(self.camera_id, FPS), (10,50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0,255,0), 2, cv2.LINE_AA)

            h, w, ch = rgb_image.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

            self.image_frame.emit(qt_image)

    def close(self):
        if self.dev:
            self.requestInterruption()
            self.dev.release()
    
    def begin(self):
        if self.dev.isOpened():
            print("start camera thread", self.camera_id)
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
    

    def update_frame(self, image):

        id = self.sender().camera_id
        pixmap = QPixmap.fromImage(image)
        window = self.findChild(QLabel, camera_windows[id])
        window.setPixmap(pixmap.scaled(window.size(), Qt.AspectRatioMode.KeepAspectRatio))

    def closeEvent(self, a0: QCloseEvent) -> None:
        for device in self.device_modules.values():
            print("close ", device)
            device.close()

        return super().closeEvent(a0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraMonitor()
    window.show()
    sys.exit(app.exec())
