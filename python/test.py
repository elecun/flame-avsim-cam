

from uvc_camera import camera


import tkinter as tk
import cv2
from PIL import Image, ImageTk
import threading

class CameraApp:
    def __init__(self, window, video_source=0):
        self.window = window
        self.window.title("카메라 영상 미리보기")

        # OpenCV 비디오 캡처 초기화
        self.video_capture = cv2.VideoCapture(video_source)
        if not self.video_capture.isOpened():
            raise ValueError("카메라를 열 수 없습니다.")

        # 프레임을 보여주기 위한 레이블 초기화
        self.label = tk.Label(window)
        self.label.pack()

        # 종료 버튼 초기화
        self.quit_button = tk.Button(window, text="종료", command=self.close)
        self.quit_button.pack()

        # 이미지 업데이트를 위한 이벤트 초기화
        self.event = threading.Event()

        # 이미지 업데이트 스레드 시작
        self.thread = threading.Thread(target=self.update)
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while True:
            # 이미지 캡처
            ret, frame = self.video_capture.read()

            if ret:
                # OpenCV BGR 이미지를 RGB로 변환
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # 이미지 크기를 조정하고 tkinter에 표시하기 위해 PIL 이미지로 변환
                image = Image.fromarray(frame_rgb)
                image = ImageTk.PhotoImage(image)

                # 레이블에 이미지 업데이트
                self.label.configure(image=image)
                self.label.image = image

            # 이벤트를 기다림
            self.event.wait(timeout=0.03)

    def close(self):
        # 종료 시 카메라 캡처 종료
        self.video_capture.release()
        self.window.destroy()

# 메인 윈도우 생성
window = tk.Tk()

# 카메라 앱 인스턴스 생성
app = CameraApp(window)

# 메인 루프 시작
window.mainloop()
