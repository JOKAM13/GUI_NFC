# -*- coding: utf-8 -*-
import logging, os
from PyQt5 import QtCore
from logging.handlers import RotatingFileHandler

class QtLogEmitter(QtCore.QObject):
    log_record = QtCore.pyqtSignal(str)

class QtLogHandler(logging.Handler):
    def __init__(self, emitter: QtLogEmitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()
        self.emitter.log_record.emit(msg)

def setup_logger(name="app", log_dir="logs", level=logging.INFO):
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    fh = RotatingFileHandler(os.path.join(log_dir, "app.log"), maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fh.setLevel(level); fh.setFormatter(fmt); logger.addHandler(fh)

    emitter = QtLogEmitter()
    qh = QtLogHandler(emitter); qh.setLevel(level); qh.setFormatter(fmt)
    logger.addHandler(qh)
    return logger, emitter
