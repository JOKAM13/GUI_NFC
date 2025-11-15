# -*- coding: utf-8 -*-
import logging
import time
import queue
from PyQt5 import QtCore
from Pilotes.stm32controle import STM32Controle

APP_LOGGER_NAME = "app"

class SerialBridge(QtCore.QObject):
    """Pont pour partager le port série entre plusieurs fenêtres."""
    line = QtCore.pyqtSignal(str)          # lignes brutes (str)
    connected = QtCore.pyqtSignal(str)     # nom de port
    disconnected = QtCore.pyqtSignal()
    _writeRequested = QtCore.pyqtSignal(str)

    @QtCore.pyqtSlot(str)
    def write_line(self, s: str):
        # Appel côté GUI secondaire (pe42582_gui)
        self._writeRequested.emit(s if isinstance(s, str) else str(s))


class STM32ControleSerial(STM32Controle):
    def __init__(self, port: str = "COM3", baudrate: int = 115200, parent=None, logger=None):
        super().__init__(parent)
        self._port = port
        self._baud = baudrate
        self._thread = None
        self._worker = None
        self.logger = logger or logging.getLogger(APP_LOGGER_NAME)
        self.logger.info(f"STM32ControleSerial initialisé avec port={port}, baudrate={baudrate}")
        # Bridge partagé pour les autres fenêtres (PE42582)
        self._bridge = SerialBridge()

    def get_bridge(self) -> SerialBridge:
        return self._bridge

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
        self._worker = _SerialWorker(self._port, self._baud, logger=self.logger)
        self._worker.moveToThread(self._thread)

        # Flux agrégé existant (Afficheur 3x5)
        self._worker.updated.connect(self.updated)

        # Connexion d'émission : on empile en DirectConnection (pas d'event loop dans le worker)
        self._bridge._writeRequested.connect(self._worker.enqueue_tx, QtCore.Qt.DirectConnection)

        # Partage de réception/état vers le bridge
        self._worker.raw_line.connect(self._bridge.line)
        self._worker.connected.connect(self._bridge.connected)
        self._worker.disconnected.connect(self._bridge.disconnected)

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
    # Sortie « agrégée » pour Afficheur
    updated = QtCore.pyqtSignal(dict)
    # Sorties pour le port partagé
    raw_line = QtCore.pyqtSignal(str)
    connected = QtCore.pyqtSignal(str)
    disconnected = QtCore.pyqtSignal()

    def __init__(self, port, baud, logger=None):
        super().__init__()
        self._running = True
        self._port = port
        self._baud = baud
        self._ser = None
        self.logger = logger or logging.getLogger(APP_LOGGER_NAME)
        self.logger.info(f"_SerialWorker initialisé avec port={port}, baud={baud}")

        # Agrégation pour l'afficheur
        self._acc = {}          # { zone_idx: set(ids) }
        self._last_emit = time.monotonic()

        # ✅ File de transmission thread-safe
        self._tx = queue.Queue()

    # --- API TX : appelée via DirectConnection depuis le bridge (thread UI) ---
    @QtCore.pyqtSlot(str)
    def enqueue_tx(self, s: str):
        try:
            self._tx.put_nowait(str(s))
        except Exception:
            pass

    # Compat : si quelqu'un appelait write_line auparavant
    @QtCore.pyqtSlot(str)
    def write_line(self, s: str):
        self.enqueue_tx(s)

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
            # Timeout court -> bonne réactivité pour drainer la TX
            ser = serial.Serial(self._port, self._baud, timeout=0.05, write_timeout=0.5)
            self._ser = ser
            self.logger.info(f"Connexion série établie sur {self._port} à {self._baud} bauds.")
            self.connected.emit(self._port)
        except Exception as e:
            self.logger.error(f"Échec de la connexion série sur {self._port} à {self._baud} bauds : {e}")
            self._running = False
            return

        try:
            with self._ser as ser:
                buf = b""
                while self._running:
                    # 🔁 Draine ce qu'on a à envoyer AVANT la lecture
                    self._drain_tx(ser)

                    try:
                        chunk = ser.read(256)
                        self._maybe_flush()
                        if not chunk:
                            continue
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            text = line.decode(errors="ignore").strip()
                            if not text:
                                continue
                            # Diffuser la ligne brute (pour pe42582_gui -> filtre #pi)
                            self.raw_line.emit(text)
                            # Essayer de parser en mapping Z:..;ID:.. pour l’Afficheur
                            mapping = self._parse_line(text)
                            if mapping is not None:
                                self._accumulate(mapping)
                                self._maybe_flush()
                    except Exception as e:
                        self.logger.error(f"Erreur lors de la lecture/décodage: {e}")
        finally:
            self._ser = None
            self.disconnected.emit()

    def _drain_tx(self, ser):
        """Envoie toutes les commandes en attente."""
        while True:
            try:
                s = self._tx.get_nowait()
            except queue.Empty:
                break
            try:
                payload = (s + "\n").encode("utf-8", errors="ignore")
                ser.write(payload)
                ser.flush()
                self.logger.debug(f"TX: {s}")
            except Exception as e:
                self.logger.error(f"Erreur écriture série: {e}")
                break

    @QtCore.pyqtSlot()
    def stop(self):
        self.logger.info("Arrêt du worker série demandé.")
        self._running = False
        # Pas d'envoi ici : le run() s'arrêtera après le prochain read()

    # --- Agrégation pour Afficheur ---
    def _accumulate(self, mapping: dict):
        for idx, ids in mapping.items():
            try:
                z = int(idx)
            except Exception:
                continue
            bucket = self._acc.setdefault(z, set())
            for mid in ids:
                if mid:
                    bucket.add(mid)

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
        self.logger.info(f"Emission agrégée: {merged}")
        self.updated.emit(merged)

    def _parse_line(self, line: str):
        line = line.strip()
        if not line or "Z:" not in line:
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
                    idx1 = int(z_part.replace("Z:", "").strip())
                    idx0 = idx1 - 1
                    ids = [s.strip() for s in id_part.split(",") if s.strip()]
                    if ids:
                        mapping[idx0] = ids
            return mapping
        except Exception:
            return None


    # def _parse_line(self, line: str):
    #     line = line.strip()
    #     if not line or "Z:" not in line:
    #         return None
    #     mapping = {}
    #     try:
    #         for m in re.finditer(r"Z\s*:\s*(\d+)\s*;?\s*ID\s*:\s*([^\r\n]*)", line):
    #             idx = int(m.group(1))
    #             idx1 = idx-1
    #             ids = [s.strip() for s in m.group(2).split(",") if s.strip()]
    #             if ids:
    #                 mapping[idx1] = ids
    #         return mapping if mapping else None
    #     except Exception:
    #         return None