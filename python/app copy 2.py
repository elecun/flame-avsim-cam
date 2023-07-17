import sys
import cv2
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.uic import loadUi
from PyQt6.QtCore import Qt, QTimer


class CameraViewer(QMainWindow):
    def __init__(self):
        super().__init__()

        # UI 파일 로드
        loadUi("MainWindow.ui", self)

        self.setWindowTitle("Camera Viewer")

        # 카메라 열기
        self.camera = cv2.VideoCapture(0)  # 0번 카메라 사용
        if not self.camera.isOpened():
            print("카메라를 열 수 없습니다.")
            sys.exit()

        # 타이머 설정
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)  # 30ms마다 프레임 업데이트

    def update_frame(self):
        # 카메라에서 프레임 읽기
        ret, frame = self.camera.read()
        if not ret:
            print("프레임을 읽을 수 없습니다.")
            return

        # 프레임을 PyQt 이미지로 변환
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

        # 이미지를 QLabel에 표시
        pixmap = QPixmap.fromImage(qt_image)
        self.label.setPixmap(pixmap.scaled(self.label.size(), Qt.AspectRatioMode.KeepAspectRatio))

    def closeEvent(self, event):
        self.camera.release()
        self.timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CameraViewer()
    window.show()
    sys.exit(app.exec())
