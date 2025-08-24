# -*- coding: utf-8 -*-
from PyQt5 import QtCore
from stm32controle import STM32Controle

class STM32ControleSerial(STM32Controle):
    def __init__(self, port: str = "COM3", baudrate: int = 115200, parent=None):
        super().__init__(parent)
        self._port = port
        self._baud = baudrate
        self._thread = None
        self._worker = None

    def configure(self, port=None, baudrate=None):
        if port is not None: self._port = port
        if baudrate is not None: self._baud = int(baudrate)

    def start(self):
        if self._thread: return
        self._thread = QtCore.QThread()
        self._worker = _SerialWorker(self._port, self._baud)
        self._worker.moveToThread(self._thread)
        self._worker.updated.connect(self.updated)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def stop(self):
        if not self._thread: return
        self._worker.stop()
        self._thread.quit()
        self._thread.wait()
        self._thread = None
        self._worker = None

    def reset(self):
        self.updated.emit({})

    def set_num_mice(self, n: int): pass

class _SerialWorker(QtCore.QObject):
    updated = QtCore.pyqtSignal(dict)
    def __init__(self, port, baud):
        super().__init__()
        self._running = True
        self._port = port
        self._baud = baud

    @QtCore.pyqtSlot()
    def run(self):
        try:
            import serial
        except ImportError:
            self._running = False
            return
        try:
            ser = serial.Serial(self._port, self._baud, timeout=1)
        except Exception:
            self._running = False
            return
        with ser:
            buf = b""
            while self._running:
                try:
                    chunk = ser.read(256)
                    if not chunk: continue
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        mapping = self._parse_line(line.decode(errors="ignore"))
                        if mapping is not None:
                            self.updated.emit(mapping)
                except Exception:
                    pass

    def stop(self):
        self._running = False

    def _parse_line(self, line: str):
        # Adapter à ton protocole réel
        # Exemple: "Z:3 ID:ABC123;Z:7 ID:00F1A2,11BEEF"
        line = line.strip()
        if not line: return None
        mapping = {}
        try:
            parts = line.split(";")
            for p in parts:
                p = p.strip()
                if not p: continue
                if p.startswith("Z:"):
                    z_part, id_part = p.split("ID:")
                    idx = int(z_part.replace("Z:","").strip())
                    ids = [s.strip() for s in id_part.split(",") if s.strip()]
                    if ids: mapping[idx] = ids
            return mapping
        except Exception:
            return None
