from PyQt5.QtCore import QThread, pyqtSignal


class Worker(QThread):
    """Run a zero-argument callable off the main thread and emit its return value."""
    result = pyqtSignal(object)
    error  = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.result.emit(self._fn())
        except Exception as e:
            self.error.emit(str(e))
