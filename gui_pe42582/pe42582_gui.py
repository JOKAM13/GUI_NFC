# -*- coding: utf-8 -*-
import sys, re, random
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer, QIODevice
from PyQt5.QtGui import QIntValidator, QCloseEvent, QTextCursor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QPlainTextEdit,
    QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox, QLineEdit, QCheckBox,
    QMessageBox, QComboBox, QSizePolicy, QFrame, QSpacerItem
)
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
from Utils.constants import *

# ======== Commandes ========
CMD_SCAN_ON  = "SCAN 1"
CMD_SCAN_OFF = "SCAN 0"
CMD_SEL      = "SEL {n}"
CMD_RATE     = "RATE {ms}"
CMD_ANT_Q    = "ANT?"
CMD_LIST     = "LIST {items}"
CMD_DEBUG    = "DEBUG"
CMD_DEBUG_ON = "DEBUG ON"
CMD_DEBUG_OFF= "DEBUG OFF"

# ======== 8 UID factices (constantes) ========
FAKE_UIDS = [
    "Souris-01",
    "Souris-02",
    "Souris-03",
    "Souris-04",
    "Souris-05",
    "Souris-06",
    "Souris-07",
    "Souris-08",
]

def available_ports():
    return QSerialPortInfo.availablePorts()


class SerialClient(QObject):
    """
    Client série bi-mode :
    - 'direct' : QSerialPort
    - 'shared' : s'abonne à un bridge (QObject: line/connected/disconnected + write_line)
    """
    lineParsed   = pyqtSignal(str)
    antChanged   = pyqtSignal(int)
    listEchoed   = pyqtSignal(list)
    debugParsed  = pyqtSignal(int, int, int, str)
    connected    = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self, baud=115200, parent=None, bridge=None):
        super().__init__(parent)
        self._shared = bridge is not None # Drapeau interne : True si on est en mode partagé (l'afficheur principal
                                          # possède le port série et pe42582_gui s'y connecte automatiquement)
        self.port_name = None
        self.logging_enabled = True

        self.re_ant   = re.compile(r"^\s*ANT\s*=\s*(\d+)\s*$")
        self.re_list  = re.compile(r"^\s*LIST\s*=\s*([\d,\s;]+)\s*$")
        self.re_debug = re.compile(r"^DEBUG:\s+DRIVER=(\d+)\s+GPIO=(\d+)\s+LS=(\d+)\s+CODE=0x([0-9A-Fa-f]{2})\s*$")

        if self._shared:
            # alors on s’abonne aux signaux du pont : notification de connexion/déconnexion,
            # et réception des lignes texte déjà lues ailleurs (le filtrage #pi et le parsing
            # seront faits dans _on_shared_filtre_line → _parse_and_emit).
            self.bridge = bridge
            self.bridge.connected.connect(self._on_shared_connected)
            self.bridge.disconnected.connect(self._on_shared_disconnected)
            self.bridge.line.connect(self._on_shared_filtre_line)
        else:
            self.uart = QSerialPort(self)
            self.uart.setBaudRate(baud)
            self.uart.readyRead.connect(self._on_ready)
            self._buffer = bytearray()

    def set_logging(self, on: bool):
        self.logging_enabled = on

    def auto_open(self) -> bool:
        if self._shared:
            return False
        cand, best = None, -1
        for info in available_ports():
            meta = f"{info.portName()} {info.description()} {info.manufacturer()}".lower()
            score = 0
            if any(k in meta for k in ["stlink", "stm", "stmicro", "cdc"]): score += 3
            if any(k in meta for k in ["usb", "usb serial", "usb-serial", "com"]): score += 2
            if any(k in meta for k in ["ch340", "wch", "cp210", "silicon labs"]): score += 1
            if score > best:
                best, cand = score, info.portName()
        return self.open_port(cand) if cand else False

    def open_port(self, name: str) -> bool:
        if self._shared:
            return False
        if not name: return False
        if self.uart.isOpen():
            self.uart.close()
        self.uart.setPortName(name)
        success = self.uart.open(QIODevice.ReadWrite)
        if success:
            self._buffer = bytearray()
            try: self.uart.clear()
            except Exception: pass
            self.port_name = name
            self.connected.emit(name)
        return success

    def close(self):
        if self._shared:
            return
        if self.uart.isOpen():
            self.uart.close()
            self.disconnected.emit()
        self.port_name = None

    def write_line(self, s: str):
        if self._shared:
            try:
                # Bridge : bascule envoi thread-safe
                self.bridge.write_line(s)
            except Exception:
                pass
            return
        if not self.uart.isOpen():
            return
        self.uart.write((s + "\n").encode("utf-8", errors="ignore"))

    # ---- Mode direct ----
    def _on_ready(self):
        big_reader = bytes(self.uart.readAll())
        if not big_reader:
            return
        big_reader = big_reader.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if not hasattr(self, "_buffer"):
            self._buffer = bytearray()
        self._buffer += big_reader

        while True:
            nl = self._buffer.find(b"\n")
            if nl < 0:
                break
            raw = self._buffer[:nl]
            self._buffer = self._buffer[nl + 1:]

            # Filtre strict '#pi'
            if b"#pi" not in raw:
                continue
            raw = raw.replace(b"#pi", b"")
            raw_str = raw.decode("utf-8", errors="ignore").strip()
            if not raw_str:
                continue
            self._parse_and_emit(raw_str)

    # ---- Mode partagé ----
    def _on_shared_connected(self, name: str):
        self.port_name = name
        self.connected.emit(name)

    def _on_shared_disconnected(self):
        self.port_name = None
        self.disconnected.emit()

    def _on_shared_filtre_line(self, raw_str: str):
        # Filtre strict '#pi'
        if "#pi" not in raw_str:
            return
        raw_str = raw_str.replace("#pi", "").strip()
        if raw_str:
            self._parse_and_emit(raw_str)

    # ---- Parsing commun ----
    def _parse_and_emit(self, raw_str: str):
        is_ant = False
        m_ant = self.re_ant.match(raw_str)
        if m_ant:
            is_ant = True
            try: self.antChanged.emit(int(m_ant.group(1)))
            except ValueError: pass

        m_list = self.re_list.match(raw_str)
        if m_list:
            nums = []
            for tok in re.split(r"[,\s;]+", m_list.group(1).strip()):
                if tok.isdigit():
                    v = int(tok)
                    if 1 <= v <= 8:
                        nums.append(v)
            if nums:
                self.listEchoed.emit(nums)

        is_debug = False
        m_dbg = self.re_debug.match(raw_str)
        if m_dbg:
            is_debug = True
            try:
                drv = int(m_dbg.group(1))
                gpio = int(m_dbg.group(2))
                ls = int(m_dbg.group(3))
                code = m_dbg.group(4).upper()
                self.debugParsed.emit(drv, gpio, ls, code)
            except ValueError:
                pass

        # STOP UART_RX masque ANT/DEBUG dans la console uniquement
        if self.logging_enabled or not (is_ant or is_debug):
            self.lineParsed.emit(raw_str)


def _style(active: bool, outline="#9e9e9e") -> str:
    if active:
        return f"QFrame {{ background:#cfefff; border:2px solid #1565c0; border-radius:6px }}"
    return f"QFrame {{ background:#fff; border:2px solid {outline}; border-radius:6px }}"


class AntCell(QFrame):
    def __init__(self, index: int, on_click, parent=None):
        super().__init__(parent)
        self.index = index
        self.on_click = on_click
        self._active = False
        self.setFrameShape(QFrame.Box)
        self.setLineWidth(2)
        self.setStyleSheet(_style(False))
        self.setCursor(Qt.PointingHandCursor)

        # Index
        self.label_index = QLabel(str(index), self)
        self.label_index.setAlignment(Qt.AlignCenter)
        self.label_index.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.label_index.setAttribute(Qt.WA_TransparentForMouseEvents)

        # Zone multi-UID
        self.label_ids = QLabel("", self)
        self.label_ids.setWordWrap(True)
        self.label_ids.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.label_ids.setStyleSheet("font-size: 16px;")
        self.label_ids.setAttribute(Qt.WA_TransparentForMouseEvents)

    def resizeEvent(self, e):
        r = self.rect()
        h_index = max(28, int(r.height() * 0.25))
        self.label_index.setGeometry(r.x(), r.y(), r.width(), h_index)
        margin = 6
        self.label_ids.setGeometry(r.x() + margin,
                                   r.y() + h_index + margin,
                                   r.width() - 2 * margin,
                                   r.height() - h_index - 2 * margin)
        super().resizeEvent(e)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.on_click:
            self.on_click(self.index)

    def set_active(self, active: bool):
        if self._active == active: return
        self._active = active
        self.setStyleSheet(_style(active))

    def flash_outline(self, ms=500):
        self.setStyleSheet(
            "QFrame { background:%s; border:3px solid red; border-radius:6px }"
            % ("#cfefff" if self._active else "#fff")
        )
        QTimer.singleShot(ms, lambda: self.setStyleSheet(_style(self._active)))

    def set_ids(self, ids):
        if not ids:
            self.label_ids.clear()
            return
        self.label_ids.setText("\n".join(f"ID: {u}" for u in ids))


class MainWindow(QMainWindow):
    """
    Si 'bridge' est fourni -> mode 'partagé' (port géré par Afficheur/STM32ControleSerial)
    Sinon -> mode 'direct' (QSerialPort local).
    """
    def __init__(self, bridge=None):
        super().__init__()
        self.setWindowTitle("PE42582 — GUI (PyQt5)")
        self.resize(850, 550)
        self._apply_global_styles()

        self.serial = SerialClient(baud=115200, parent=self, bridge=bridge)
        self.serial.lineParsed.connect(self.append_log)
        # IMPORTANT : on passe par _on_ant_changed (et pas _highlight) pour publier au STM32
        self.serial.antChanged.connect(self._on_ant_changed)
        self.serial.listEchoed.connect(self.on_list_echo)
        self.serial.debugParsed.connect(self.on_debug)
        self.serial.connected.connect(self.on_connected)
        self.serial.disconnected.connect(self.on_disconnected)

        self.cells = []
        self.current_ant = 0
        self._build_ui()

        if bridge is None:
            self._refresh_ports()
            if not self.serial.auto_open():
                self.on_disconnected()
        else:
            # Mode partagé : l’autre GUI contrôle l’ouverture
            self._set_controls(True)
            self.lbl_status.setText("Partagé (géré par Afficheur 3x5)")
            self.cmb_port.setEnabled(False)
            self.btn_refresh.setEnabled(False)
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(False)

        # ===== Simulation de 8 UID =====
        self._init_uid_sim()

        self.setAttribute(Qt.WA_DeleteOnClose, True)

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # Gauche
        left = QVBoxLayout()
        root.addLayout(left, 7)

        # Connexion
        gb_conn = QGroupBox("Connexion")
        left.addWidget(gb_conn)
        hconn = QHBoxLayout(gb_conn)
        self.cmb_port = QComboBox()
        self.btn_refresh = QPushButton("Rafraîchir")
        self.btn_connect = QPushButton("Connecter")
        self.btn_disconnect = QPushButton("Déconnecter")
        self.lbl_status = QLabel("Déconnecté")
        hconn.addWidget(QLabel("Port:"))
        hconn.addWidget(self.cmb_port, 1)
        hconn.addWidget(self.btn_refresh)
        hconn.addWidget(self.btn_connect)
        hconn.addWidget(self.btn_disconnect)
        hconn.addWidget(self.lbl_status, 1, Qt.AlignRight)
        self.btn_refresh.clicked.connect(self._refresh_ports)
        self.btn_connect.clicked.connect(self._do_connect)
        self.btn_disconnect.clicked.connect(self.serial.close)

        # Grille 2x4
        gb_grid = QGroupBox("Grille d'antennes (clic = SEL n)")
        left.addWidget(gb_grid)
        grid = QGridLayout(gb_grid)
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(0)
        for r in range(2):
            for c in range(4):
                idx = r * 4 + c + 1
                cell = AntCell(idx, self._on_cell_clicked)
                cell.setMinimumSize(150, 120)
                self.cells.append(cell)
                grid.addWidget(cell, r, c)

        # Ligne 1 : Scan & ANT?
        row1 = QHBoxLayout()
        left.addLayout(row1)
        self.btn_scan_off = QPushButton("Arrêter Scan")
        self.btn_scan_on  = QPushButton("Relancer Scan")
        self.btn_ant_q    = QPushButton("ANT?")
        row1.addWidget(self.btn_scan_off)
        row1.addWidget(self.btn_scan_on)
        row1.addWidget(self.btn_ant_q)
        self.btn_scan_off.clicked.connect(lambda: self.send(CMD_SCAN_OFF))
        self.btn_scan_on.clicked.connect(lambda: self.send(CMD_SCAN_ON))
        self.btn_ant_q.clicked.connect(lambda: self.send(CMD_ANT_Q))

        # Ligne 2 : UART logs & debug
        row2 = QHBoxLayout()
        left.addLayout(row2)
        self.btn_uart_stop = QPushButton("STOP UART_RX")
        self.btn_uart_start = QPushButton("START UART_RX")
        self.btn_dbg = QPushButton("DEBUG (one-shot)")
        self.btn_dbg_on = QPushButton("DEBUG ON")
        self.btn_dbg_off = QPushButton("DEBUG OFF")
        row2.addWidget(self.btn_uart_stop)
        row2.addWidget(self.btn_uart_start)
        row2.addWidget(self.btn_dbg)
        row2.addWidget(self.btn_dbg_on)
        row2.addWidget(self.btn_dbg_off)
        self.btn_uart_stop.clicked.connect(self._stop_uart_logs)
        self.btn_uart_start.clicked.connect(self._start_uart_logs)
        self.btn_dbg.clicked.connect(lambda: self.send(CMD_DEBUG))
        self.btn_dbg_on.clicked.connect(lambda: self.send(CMD_DEBUG_ON))
        self.btn_dbg_off.clicked.connect(lambda: self.send(CMD_DEBUG_OFF))

        # Période
        gb_rate = QGroupBox("Période (ms)")
        left.addWidget(gb_rate)
        hrate = QHBoxLayout(gb_rate)
        self.ed_rate = QLineEdit(); self.ed_rate.setPlaceholderText("ex. 40")
        self.ed_rate.setValidator(QIntValidator(1, 100000, self))
        self.btn_rate_apply = QPushButton("Appliquer")
        hrate.addWidget(QLabel("Période (ms):"))
        hrate.addWidget(self.ed_rate, 1)
        hrate.addWidget(self.btn_rate_apply)
        self.btn_rate_apply.clicked.connect(self._apply_rate)
        self.ed_rate.returnPressed.connect(self._apply_rate)

        # LIST
        gb_list = QGroupBox("Antennes à balayer")
        left.addWidget(gb_list)
        vlist = QVBoxLayout(gb_list)
        self.cb_all = QCheckBox("Tout"); self.cb_all.setTristate(True); self.cb_all.stateChanged.connect(self._all_toggled)
        vlist.addWidget(self.cb_all)
        grid_cb = QGridLayout()
        self.cbs_list = []
        for i in range(8):
            cb = QCheckBox(str(i + 1)); cb.setChecked(True); cb.stateChanged.connect(self._children_changed)
            self.cbs_list.append(cb)
            grid_cb.addWidget(cb, i // 4, i % 4)
        vlist.addLayout(grid_cb)
        self.btn_list_apply = QPushButton("Appliquer sélection")
        self.btn_list_apply.clicked.connect(self._apply_list)
        vlist.addWidget(self.btn_list_apply, alignment=Qt.AlignRight)

        left.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Droite : console UART
        # Colonne droite "emballée" dans un QWidget pour pouvoir fixer une largeur max
        rightWrap = QWidget()
        rightWrap.setMaximumWidth(270)  # borne la largeur de la console (ajuste 320/360/400 selon tes goûts)
        right = QVBoxLayout(rightWrap)
        root.addWidget(rightWrap, 3)  # et on garde un ratio plus petit que la grille

        gb_log = QGroupBox("Console UART");
        right.addWidget(gb_log, 1)
        v = QVBoxLayout(gb_log)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(4000)
        v.addWidget(self.log)

        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self.log.clear)
        right.addWidget(self.btn_clear, alignment=Qt.AlignRight)

        # hint = QLabel("STOP UART_RX masque ANT/DEBUG dans la console, mais la grille/LIST restent mises à jour.")
        # hint.setStyleSheet("color:#666")
        # right.addWidget(hint)

        self._set_controls(False)
        self._update_master_checkbox()


    """
    Augmente la police des labels, group box titres et boutons
    (le n° d’antenne reste contrôlé localement via AntCell.label_index)
    """
    def _apply_global_styles(self):
        self.setStyleSheet("""
            QLabel { font-size: 13px; }
            QGroupBox { font-size: 14px; font-weight: 700; }
            QPushButton { font-size: 14px; }
         """)

    # ---------- Serial helpers ----------
    def _refresh_ports(self):
        self.cmb_port.blockSignals(True)
        self.cmb_port.clear()
        for p in available_ports():
            label = f"{p.portName()}".strip(" —")
            self.cmb_port.addItem(label, p.portName())
        self.cmb_port.blockSignals(False)

    def _do_connect(self):
        name = self.cmb_port.currentData()
        if not name:
            QMessageBox.warning(self, "Connexion", "Aucun port détecté.")
            return
        if not self.serial.open_port(name):
            QMessageBox.critical(self, "Connexion", f"Impossible d’ouvrir {name}")

    def on_connected(self, name: str):
        self.lbl_status.setText(f"Connecté: {name}")
        self._set_controls(True)
        self.append_log(f"# Connecté à {name}")
        self.send(CMD_ANT_Q)

    def on_disconnected(self):
        self.lbl_status.setText("Déconnecté")
        self._set_controls(False)
        self.append_log("# Déconnecté")

    def _set_controls(self, on: bool):
        for w in [ self.btn_scan_off, self.btn_scan_on, self.btn_ant_q,
                   self.btn_uart_stop, self.btn_uart_start,
                   self.btn_dbg, self.btn_dbg_on, self.btn_dbg_off,
                   self.ed_rate, self.btn_rate_apply,
                   self.btn_list_apply, self.cb_all ] + self.cbs_list:
            w.setEnabled(on)

    def append_log(self, line: str):
        if line is None:
            return
        cursor = self.log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(line)
        if not line.endswith("\n"):
            cursor.insertText("\n")
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def send(self, cmd: str):
        try:
            self.serial.write_line(cmd)
            if self.serial.logging_enabled:
                self.append_log(f"> {cmd}")
        except Exception as e:
            self.append_log(f"# Erreur envoi: {e}")

    def _stop_uart_logs(self):
        self.serial.set_logging(False)
        self.append_log("# UART_RX LOGS: PAUSED (ANT/DEBUG masqués)")

    def _start_uart_logs(self):
        self.serial.set_logging(True)
        self.append_log("# UART_RX LOGS: RUNNING")

    def _apply_rate(self):
        t = self.ed_rate.text().strip()
        if not t: return
        try: ms = int(t)
        except ValueError:
            QMessageBox.warning(self, "Valeur invalide", "Entrez un entier."); return
        if not (10 <= ms <= 10000):
            QMessageBox.warning(self, "Valeur invalide", "Entrez un entier entre 10 et 10000 ms."); return
        self.send(CMD_RATE.format(ms=ms))

    def _apply_list(self):
        items = [str(i + 1) for i, cb in enumerate(self.cbs_list) if cb.isChecked()]
        if not items:
            QMessageBox.warning(self, "LIST", "Sélection vide, choisir au moins 1 antenne."); return
        self.send(CMD_LIST.format(items=",".join(items)))

    def _on_cell_clicked(self, n: int):
        # Retour explicite + feedback immédiat
        self.send(CMD_SEL.format(n=n))
        self._highlight(n)  # feedback local seulement (la publication réelle se fait sur ANT=n reçu)

    def on_list_echo(self, values: list):
        present = set(values)
        for i, cb in enumerate(self.cbs_list, start=1):
            cb.blockSignals(True)
            cb.setChecked(i in present)
            cb.blockSignals(False)
        self._update_master_checkbox()

    def on_debug(self, drv: int, gpio: int, *_rest):
        if 1 <= drv <= 8:
            self._highlight(drv)  # debug feedback uniquement (pas d'UIDS TX)
            if drv != gpio and 1 <= gpio <= 8:
                self.cells[drv - 1].flash_outline(ms=500)

    def _highlight(self, n: int):
        self.current_ant = n
        for i, cell in enumerate(self.cells, start=1):
            cell.set_active(i == n)

    def _on_ant_changed(self, n: int):
        # Appelé sur réception "#piANT=n" -> surligne + publie les UID de la cellule n
        self._highlight(n)
        self._publish_active_to_stm32(n)

    def _all_toggled(self, state: int):
        if state == Qt.PartiallyChecked:
            state = Qt.Checked
        checked = (state == Qt.Checked)
        for cb in self.cbs_list:
            cb.blockSignals(True)
            cb.setChecked(checked)
            cb.blockSignals(False)
        self._update_master_checkbox()

    def _children_changed(self, _state: int):
        self._update_master_checkbox()

    def _update_master_checkbox(self):
        total = len(self.cbs_list)
        n_on = sum(cb.isChecked() for cb in self.cbs_list)
        self.cb_all.blockSignals(True)
        self.cb_all.setCheckState(Qt.Unchecked if n_on == 0 else (Qt.Checked if n_on == total else Qt.PartiallyChecked))
        self.cb_all.blockSignals(False)

    def _graceful_shutdown(self) -> None:
        try:
            self.serial.write_line("SCAN 0")
        except Exception:
            pass

    def closeEvent(self, e: QCloseEvent) -> None:
        try:
            self._stop_uid_sim()     # stop timers de simulation
            self._graceful_shutdown()
        finally:
            super().closeEvent(e)

    # ======================== SIMULATION UID ========================
    def _init_uid_sim(self):
        """
        8 UID toujours affichés, durées 6–10 s, chronos indépendants.
        Contrainte: max 3 UID par cellule.
        """
        # Cell -> [UID,...] et UID -> cell
        self._cell_to_uids = {i: [] for i in range(1, 9)}
        self._uid_to_cell = {}
        self._uid_timers = {}  # uid -> QTimer single-shot

        # Distribution initiale: 1 UID par cellule (1..8)
        for i, uid in enumerate(FAKE_UIDS, start=1):
            cell = ((i - 1) % 8) + 1
            self._uid_to_cell[uid] = cell
            self._cell_to_uids[cell].append(uid)
        self._apply_uid_mapping()

        # Timer initial 3–6 s pour chaque UID
        for uid in FAKE_UIDS:
            self._schedule_uid(uid)

    def _schedule_uid(self, uid: str):
        old = self._uid_timers.get(uid)
        if old:
            try: old.stop()
            except Exception: pass
        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(lambda u=uid: self._move_uid(u))
        t.start(random.randint(15000, 20000))  # 10 à 15 s
        self._uid_timers[uid] = t

    def _pick_new_cell(self, cur_cell: int) -> int:
        """
        Choisit une cellule != cur_cell, prioritairement parmi celles ayant < 3 UID.
        """
        candidates = [i for i in range(1, 9) if i != cur_cell and len(self._cell_to_uids[i]) < 3]
        if candidates:
            return random.choice(candidates)
        # Sécurité (avec 8 UID et capacité 24, ne devrait pas arriver)
        others = [i for i in range(1, 9) if i != cur_cell]
        others.sort(key=lambda k: len(self._cell_to_uids[k]))
        return others[0] if others else cur_cell

    def _move_uid(self, uid: str):
        """
        Déplace un UID vers une autre cellule (≠ courante), en respectant max 3 UID/cell.
        Replanifie sa prochaine échéance.
        """
        cur = self._uid_to_cell.get(uid, None)
        if cur is None:
            counts = [(len(self._cell_to_uids[i]), i) for i in range(1, 9)]
            counts.sort()
            cur = counts[0][1]
            self._uid_to_cell[uid] = cur
            self._cell_to_uids[cur].append(uid)

        new_cell = self._pick_new_cell(cur)

        # Retire de l’ancienne
        try:
            self._cell_to_uids[cur].remove(uid)
        except ValueError:
            pass

        # Ajoute dans la nouvelle
        self._cell_to_uids[new_cell].append(uid)
        self._uid_to_cell[uid] = new_cell

        # Met à jour l’affichage et replanifie
        self._apply_uid_mapping()
        self._schedule_uid(uid)

    def _apply_uid_mapping(self):
        """Pousse les listes d'UID vers les 8 cellules 1..8."""
        for idx, cell in enumerate(self.cells, start=1):
            cell.set_ids(self._cell_to_uids.get(idx, []))

    def _stop_uid_sim(self):
        for t in list(self._uid_timers.values()):
            try: t.stop()
            except Exception: pass
        self._uid_timers.clear()

    # ======================== Publication vers STM32 ========================
    def _publish_active_to_stm32(self, ant_idx: int):
        #pass
        """
        Envoie au STM32 la liste d'UID présentes dans la cellule ant_idx
        sous forme de commande :  UIDS <ant_idx> <id1,id2,id3>
        (liste vide => 'UIDS <ant_idx>' sans CSV ; le STM32 renverra Z:<idx>;ID:)
        """
        if not (1 <= ant_idx <= 8):
            return
        ids = list(self._cell_to_uids.get(ant_idx, []))
        # Sécurité : ≤ 3 et nettoyage basique
        ids = [s.replace(";", "").replace(" ", "")[:48] for s in ids[:3]]
        if ids:
            self.send(f"UIDS {ant_idx} {','.join(ids)}")


# --- Entrée autonome (pour test direct de cette fenêtre) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()  # bridge injecté par l'autre UI en pratique
    win.show()
    sys.exit(app.exec_())