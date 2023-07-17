
'''
FLAME AVSIM CAMERA Monitor & Controller
'''

import pathlib
import tkinter as tk
import tkinter.ttk as ttl
import json
import pygubu
from uvc_camera import camera

PROJECT_PATH = pathlib.Path(__file__).parent
PROJECT_UI = PROJECT_PATH / "gui.ui"


class app_camera_monitor:
    def __init__(self, master=None) -> None:
        self.builder = pygubu.Builder()
        self.builder.add_resource_path(PROJECT_PATH)
        self.master = master

        #devices
        self.camera0 = None
        self.camera1 = None
        self.camera2 = None
        self.camera3 = None
        self.camera4 = None
        self.camera5 = None

        self.builder.add_from_file(PROJECT_UI)
        self.mainwindow = self.builder.get_object('flame_ui_root', master)
        self.camera0_monitor = self.builder.get_object('camera1_canvas', master)
        self.builder.connect_callbacks(self)


    def __del__(self) -> None:
        print("close all devices")
        if self.camera0 != None:
            self.camera0.close()

        self.mainwindow.quit()

    def run(self):
        self.mainwindow.mainloop()

    def camera1_connect(self):
        if self.camera0 == None:
            btn_camera_connect_label = self.builder.get_object('btn_camera1_connect', self.master)
            print("camera 1 opening..")
            self.mainwindow.wm_attributes("-alpha", True)
            self.camera0 = camera(0, tk_canvas=self.camera0_monitor)

    def camera2_connect(self):
        print("camera 2 connect ")
    def camera3_connect(self):
        print("camera 3 connect ")
    def camera4_connect(self):
        print("camera 4 connect ")
    def camera5_connect(self):
        print("camera 5 connect ")
    def camera6_connect(self):
        print("camera 6 connect ")


if __name__ == '__main__':
    app = app_camera_monitor()
    app.run()