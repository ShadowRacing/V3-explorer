"""
Background job module for Shadows File Explorer.

BackgroundJob runs a slow function (zipping, extracting, ...) in a worker
thread and reports back to the UI thread through Qt signals.
"""
import threading

from PyQt6.QtCore import QObject, pyqtSignal


class BackgroundJob(QObject):
    """Run func(progress=..., cancel=...) in a worker thread.
    
    func receives a progress(done, total) callback and a threading.Event
    that is set when the user cancels.
    
    Signals:
        progress: Progress update (done, total)
        succeeded: func returned (its result)
        failed: func raised (the exception)
    """
    
    progress = pyqtSignal(object, object)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)
    
    def __init__(self, func, parent=None):
        super().__init__(parent)
        self.func = func
        self.cancel = threading.Event()
    
    def start(self):
        threading.Thread(target=self._run, daemon=True).start()
    
    def _run(self):
        try:
            result = self.func(progress=lambda done, total: self.progress.emit(done, total),
                               cancel=self.cancel)
        except Exception as e:
            self.failed.emit(e)
        else:
            self.succeeded.emit(result)
