# -*- coding: utf-8 -*-
import logging
import time
from PyQt5 import QtCore
from stm32controle import STM32Controle

APP_LOGGER_NAME = "app"

class STM32ControleSerial(STM32Controle):
    def __init__(self, port: str = "COM3", baudrate: int = 115200, parent=None, logger=None):
        super().__init__(parent)
        self._port = port
        self._baud = baudrate
        self._thread = None
        self._worker = None
        # réutilise le logger passé, sinon le logger "app"
        self.logger = logger or logging.getLogger(APP_LOGGER_NAME)
        self.logger.info(f"STM32ControleSerial initialisé avec port={port}, baudrate={baudrate}")

    def configure(self, port=None, baudrate=None):
        if port is not None:
            self.logger.info(f"Changement du port série: {self._port} -> {port}")
            self._port = port
        if baudrate is not None:
            self.logger.info(f"Changement du baudrate: {self._baud} -> {baudrate}")
            self._baud = int(baudrate)

    def start(self):
        if self._thread:
            self.logger.warning("Tentative de démarrage alors que le thread est déjà actif.")
            return
        self.logger.info("Démarrage du thread de communication série.")
        self._thread = QtCore.QThread()
        self._worker = _SerialWorker(self._port, self._baud, logger=self.logger)  # <-- passe le même logger
        self._worker.moveToThread(self._thread)
        self._worker.updated.connect(self.updated)
        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def stop(self):
        if not self._thread:
            self.logger.warning("Tentative d'arrêt alors qu'aucun thread n'est actif.")
            return
        self.logger.info("Arrêt du thread de communication série.")
        self._worker.stop()
        self._thread.quit()
        self._thread.wait()
        self._thread = None
        self._worker = None

    def reset(self):
        self.logger.info("Réinitialisation demandée (reset). Emission d'un dictionnaire vide.")
        self.updated.emit({})

    def set_num_mice(self, n: int):
        self.logger.info(f"set_num_mice appelé avec n={n} (fonction non implémentée)")
        pass

class _SerialWorker(QtCore.QObject):
    updated = QtCore.pyqtSignal(dict)

    def __init__(self, port, baud, logger=None):
        super().__init__()
        self._running = True
        self._port = port
        self._baud = baud
        self.logger = logger or logging.getLogger(APP_LOGGER_NAME)
        self.logger.info(f"_SerialWorker initialisé avec port={port}, baud={baud}")

        # --- Accumulation + cadence 1s (sans QTimer) ---
        self._acc = {}                 # { zone_idx: set(ids) }
        self._last_emit = time.monotonic()

    @QtCore.pyqtSlot()
    def run(self):
        self.logger.info("Thread worker série lancé.")
        try:
            import serial
        except ImportError:
            self.logger.error("Le module 'serial' n'est pas installé.")
            self._running = False
            return
        try:
            ser = serial.Serial(self._port, self._baud, timeout=3)
            self.logger.info(f"Connexion série établie sur {self._port} à {self._baud} bauds.")
        except Exception as e:
            self.logger.error(f"Échec de la connexion série sur {self._port} à {self._baud} bauds : {e}")
            self._running = False
            return
        with ser:
            buf = b""
            while self._running:
                try:
                    chunk = ser.read(256)
                    # même si aucune donnée nouvelle, on vérifie si on doit flusher
                    self._maybe_flush()
                    if not chunk:
                        continue
                    self.logger.debug(f"Chunk reçu: {chunk!r}")
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        self.logger.debug(f"Ligne reçue: {line!r}")
                        mapping = self._parse_line(line.decode(errors="ignore"))
                        if mapping is not None:
                            self.logger.info(f"Mapping décodé: {mapping}")
                            self._accumulate(mapping)  # on bufferise
                            self._maybe_flush()        # flush si ≥ 1s écoulée
                except Exception as e:
                    self.logger.error(f"Erreur lors de la lecture ou du décodage: {e}")

    def stop(self):
        self.logger.info("Arrêt du worker série demandé.")
        self._running = False
        # flush final pour ne rien perdre
        self._flush()

    # ---------- Accumulation & emission ----------

    def _accumulate(self, mapping: dict):
        # mapping: { zone_idx: [id1, id2, ...] }
        for idx, ids in mapping.items():
            try:
                z = int(idx)
            except Exception:
                continue
            bucket = self._acc.setdefault(z, set())
            for mid in ids:
                if mid:
                    bucket.add(mid)
        self.logger.debug(f"Accumulation actuelle: {{k: len(v) for k,v in self._acc.items()}}")

    def _maybe_flush(self):
        now = time.monotonic()
        if self._acc and (now - self._last_emit) >= 0.6:
            self._flush(now)

    def _flush(self, now=None):
        if not self._acc:
            return
        merged = {idx: sorted(list(ids)) for idx, ids in self._acc.items()}
        self._acc.clear()
        self._last_emit = now if now is not None else time.monotonic()
        self.logger.info(f"Emission agrégée (1s): {merged}")
        self.updated.emit(merged)
        self.logger.info(f"update terminé: {merged}")

    # --------------------------------------------

    def _parse_line(self, line: str):
        line = line.strip()
        self.logger.debug(f"Décodage de la ligne: {line}")
        if not line:
            self.logger.debug("Ligne vide ignorée.")
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
            self.logger.debug(f"Résultat du mapping: {mapping}")
            return mapping
        except Exception as e:
            self.logger.error(f"Erreur lors du parsing de la ligne: {e}")
            return None
