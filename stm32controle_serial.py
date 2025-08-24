
# -*- coding: utf-8 -*-
import logging
from PyQt5 import QtCore
from stm32controle import STM32Controle

class STM32ControleSerial(STM32Controle):
    def __init__(self, port: str = "COM3", baudrate: int = 115200, parent=None):
        super().__init__(parent)
        self._port = port
        self._baud = baudrate
        self._thread = None
        self._worker = None
        logging.info(f"STM32ControleSerial initialisé avec port={port}, baudrate={baudrate}")

    def configure(self, port=None, baudrate=None):
        if port is not None:
            logging.info(f"Changement du port série: {self._port} -> {port}")
            self._port = port
        if baudrate is not None:
            logging.info(f"Changement du baudrate: {self._baud} -> {baudrate}")
            self._baud = int(baudrate)

    def start(self):
        if self._thread:
            logging.warning("Tentative de démarrage alors que le thread est déjà actif.")
            return
        logging.info("Démarrage du thread de communication série.")
        self._thread = QtCore.QThread()
        self._worker = _SerialWorker(self._port, self._baud)
        self._worker.moveToThread(self._thread)
        self._worker.updated.connect(self.updated)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def stop(self):
        if not self._thread:
            logging.warning("Tentative d'arrêt alors qu'aucun thread n'est actif.")
            return
        logging.info("Arrêt du thread de communication série.")
        self._worker.stop()
        self._thread.quit()
        self._thread.wait()
        self._thread = None
        self._worker = None

    def reset(self):
        logging.info("Réinitialisation demandée (reset). Emission d'un dictionnaire vide.")
        self.updated.emit({})

    def set_num_mice(self, n: int):
        logging.info(f"set_num_mice appelé avec n={n} (fonction non implémentée)")
        pass

class _SerialWorker(QtCore.QObject):
    updated = QtCore.pyqtSignal(dict)
    def __init__(self, port, baud):
        super().__init__()
        self._running = True
        self._port = port
        self._baud = baud
        logging.info(f"_SerialWorker initialisé avec port={port}, baud={baud}")

    @QtCore.pyqtSlot()
    def run(self):
        logging.info("Thread worker série lancé.")
        try:
            import serial
        except ImportError:
            logging.error("Le module 'serial' n'est pas installé.")
            self._running = False
            return
        try:
            ser = serial.Serial(self._port, self._baud, timeout=3)
            logging.info(f"Connexion série établie sur {self._port} à {self._baud} bauds.")
        except Exception as e:
            logging.error(f"Échec de la connexion série sur {self._port} à {self._baud} bauds : {e}")
            self._running = False
            return
        with ser:
            buf = b""
            while self._running:
                try:
                    chunk = ser.read(256)
                    if not chunk:
                        continue
                    logging.debug(f"Chunk reçu: {chunk}")
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        logging.debug(f"Ligne reçue: {line}")
                        mapping = self._parse_line(line.decode(errors="ignore"))
                        if mapping is not None:
                            logging.info(f"Mapping décodé: {mapping}")
                            self.updated.emit(mapping)
                except Exception as e:
                    logging.error(f"Erreur lors de la lecture ou du décodage: {e}")

    def stop(self):
        logging.info("Arrêt du worker série demandé.")
        self._running = False

    def _parse_line(self, line: str):
        # Adapter à ton protocole réel
        # Exemple: "Z:3 ID:ABC123;Z:7 ID:00F1A2,11BEEF"
        line = line.strip()
        logging.debug(f"Décodage de la ligne: {line}")
        if not line:
            logging.debug("Ligne vide ignorée.")
            return None
        mapping = {}
        try:
            parts = line.split(";")
            for p in parts:
                p = p.strip()
                if not p:
                    continue
                if p.startswith("Z:"):
                    z_part, id_part = p.split("ID:")
                    idx = int(z_part.replace("Z:","").strip())
                    ids = [s.strip() for s in id_part.split(",") if s.strip()]
                    if ids:
                        mapping[idx] = ids
            logging.debug(f"Résultat du mapping: {mapping}")
            return mapping
        except Exception as e:
            logging.error(f"Erreur lors du parsing de la ligne: {e}")
            return None
