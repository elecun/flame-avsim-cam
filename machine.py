'''
In-cabin monitoring system performance monitor
@author bh.hwang@iae.re.kr
'''

from PyQt6.QtCore import QThread, pyqtSignal
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
