# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets, QtGui
from constants import APP_BG, TITLE_BG, TITLE_FG, PANEL_BG, GRID_BORDER, ZONE_NAMES, MOUSE_IMAGE_PATH
from widgets import GridTile
from controle_donnee import ControleDonnee
from qtlogger import setup_logger

EVENT_LABELS_FR = {"enter": "Entree", "stay": "Presence", "leave": "Sortie"}

def _list_serial_ports():
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except Exception:
        import sys
        if sys.platform.startswith("win"):
            return [f"COM{i}" for i in range(1, 21)]
        elif sys.platform.startswith("linux"):
            return ["/dev/ttyUSB0","/dev/ttyUSB1","/dev/ttyACM0","/dev/ttyACM1"]
        elif sys.platform.startswith("darwin"):
            return ["/dev/tty.usbserial","/dev/tty.usbmodem"]
        return []

class Afficheur(QtWidgets.QMainWindow):
    def __init__(self, controle: ControleDonnee):
        super().__init__()
        self._controle = controle
        self._controle.data_updated.connect(self.on_update)
        self._controle.ids_catalog_updated.connect(self.on_ids_catalog_updated)
        self._controle.current_count_updated.connect(self.on_current_count)

        # Logger
        self.logger, self.log_emitter = setup_logger("app")
        self.log_emitter.log_record.connect(self.append_log)

        self.setWindowTitle("Détection des souris – Grille 3x5")
        self.resize(1200, 780)

        central = QtWidgets.QWidget(); self.setCentralWidget(central)
        central.setObjectName("central")
        central.setStyleSheet(f"#central {{ background: {APP_BG}; }}")
        root = QtWidgets.QVBoxLayout(central); root.setContentsMargins(12,12,12,12); root.setSpacing(10)

        # Titre
        title = QtWidgets.QLabel("Détection des souris")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet(f"background: {TITLE_BG}; color: {TITLE_FG}; font-size: 22px; font-weight: 700; padding: 10px; border-radius: 8px;")
        root.addWidget(title)

        # Zone centrale: grille + panneau droit
        center = QtWidgets.QHBoxLayout(); center.setSpacing(12); root.addLayout(center)

        # Grille 3x5
        grid_wrap = QtWidgets.QFrame(); grid_wrap.setObjectName("gridwrap")
        grid_wrap.setStyleSheet(f"#gridwrap {{ background: {GRID_BORDER}; border-radius: 6px; }}")
        grid_lay = QtWidgets.QGridLayout(grid_wrap); grid_lay.setContentsMargins(1,1,1,1); grid_lay.setHorizontalSpacing(0); grid_lay.setVerticalSpacing(0)
        self.tiles = []; idx = 0
        for r in range(3):
            for c in range(5):
                tile = GridTile(ZONE_NAMES[idx]); tile.setMinimumSize(120, 120)
                self.tiles.append(tile); grid_lay.addWidget(tile, r, c); idx += 1
        center.addWidget(grid_wrap, 1)

        # Panneau droit
        side = QtWidgets.QFrame(); side.setObjectName("side")
        side.setStyleSheet(f"#side {{ background: {PANEL_BG}; border: 1px solid {GRID_BORDER}; border-radius: 8px; }}")
        side_lay = QtWidgets.QVBoxLayout(side); side_lay.setContentsMargins(14,14,14,14); side_lay.setSpacing(14)

        # Image décorative
        self.img_mouse = QtWidgets.QLabel(); self.img_mouse.setAlignment(QtCore.Qt.AlignCenter)
        pm = QtGui.QPixmap(MOUSE_IMAGE_PATH)
        if not pm.isNull():
            pm = pm.scaledToWidth(220, QtCore.Qt.SmoothTransformation)
            self.img_mouse.setPixmap(pm)
        else:
            self.img_mouse.setText("🖼️ (Ajoute assets/mouse.png)")
        side_lay.addWidget(self.img_mouse)

        # Connexion STM32
        conn_box = QtWidgets.QGroupBox("Connexion STM32")
        conn = QtWidgets.QGridLayout(conn_box)
        conn.addWidget(QtWidgets.QLabel("Port :"), 0, 0)
        self.cb_port = QtWidgets.QComboBox(); self.cb_port.setEditable(True)
        ports = _list_serial_ports()
        if ports: self.cb_port.addItems(ports)
        if self.cb_port.count() == 0:
            import sys
            self.cb_port.addItem("COM3" if sys.platform.startswith("win") else "/dev/ttyUSB0")
        conn.addWidget(self.cb_port, 0, 1)
        self.btn_refresh_ports = QtWidgets.QPushButton("↻"); self.btn_refresh_ports.setFixedWidth(36)
        self.btn_refresh_ports.clicked.connect(self._refresh_ports); conn.addWidget(self.btn_refresh_ports, 0, 2)

        conn.addWidget(QtWidgets.QLabel("Baudrate :"), 1, 0)
        self.cb_baud = QtWidgets.QComboBox(); self.cb_baud.setEditable(True)
        self.cb_baud.addItems(["9600","19200","38400","57600","115200","230400","460800","921600"])
        self.cb_baud.setCurrentText("115200")
        conn.addWidget(self.cb_baud, 1, 1, 1, 2)
        side_lay.addWidget(conn_box)

        # Compteur temps réel
        rt_box = QtWidgets.QGroupBox("Souris détectées (temps réel)")
        rt_lay = QtWidgets.QHBoxLayout(rt_box)
        self.lbl_realtime = QtWidgets.QLabel("0"); self.lbl_realtime.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl_realtime.setStyleSheet("font-weight: 900; font-size: 24px; color: #2D7FF9;")
        rt_lay.addWidget(self.lbl_realtime)
        side_lay.addWidget(rt_box)

        # Boutons
        self.btn_start = self._mk_button("START"); self.btn_stop = self._mk_button("STOP"); self.btn_reset = self._mk_button("RESET")
        self.btn_start.clicked.connect(self.on_start); self.btn_stop.clicked.connect(self.on_stop); self.btn_reset.clicked.connect(self.on_reset)
        side_lay.addWidget(self.btn_start); side_lay.addWidget(self.btn_stop); side_lay.addWidget(self.btn_reset)

        # Historique
        hist_box = QtWidgets.QGroupBox("Historique par souris")
        hl = QtWidgets.QVBoxLayout(hist_box)
        row = QtWidgets.QHBoxLayout()
        self.cb_mouse = QtWidgets.QComboBox(); self.cb_mouse.setEditable(False); self.cb_mouse.setPlaceholderText("Sélectionner une souris…")
        row.addWidget(self.cb_mouse)
        self.btn_show_hist = self._mk_button("Afficher l'historique"); self.btn_show_hist.clicked.connect(self.on_show_history)
        row.addWidget(self.btn_show_hist)
        hl.addLayout(row)
        self.btn_export_csv = self._mk_button("Exporter tout (CSV)"); self.btn_export_csv.clicked.connect(self.on_export_csv); hl.addWidget(self.btn_export_csv)
        self.btn_clear_hist = self._mk_button("Vider l'historique"); self.btn_clear_hist.clicked.connect(self.on_clear_history); hl.addWidget(self.btn_clear_hist)
        side_lay.addWidget(hist_box)

        side_lay.addStretch(1)
        center.addWidget(side)

        # Zone de logs en bas
        log_box = QtWidgets.QGroupBox("Logs"); v = QtWidgets.QVBoxLayout(log_box)
        self.txt_logs = QtWidgets.QPlainTextEdit(); self.txt_logs.setReadOnly(True)
        self.txt_logs.setMaximumBlockCount(2000); self.txt_logs.setStyleSheet("font-family: Consolas, Menlo, monospace; font-size: 12px;")
        v.addWidget(self.txt_logs)
        btns = QtWidgets.QHBoxLayout(); self.btn_copy_logs = QtWidgets.QPushButton("Copier"); self.btn_clear_logs = QtWidgets.QPushButton("Effacer")
        self.btn_copy_logs.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.txt_logs.toPlainText()))
        self.btn_clear_logs.clicked.connect(self.txt_logs.clear)
        btns.addStretch(1); btns.addWidget(self.btn_copy_logs); btns.addWidget(self.btn_clear_logs); v.addLayout(btns)
        root.addWidget(log_box)

        # Précharger la liste des souris déjà connues (depuis les logs présents)
        try:
            initial_ids = self._controle.get_mouse_ids()
            if initial_ids:
                for mid in initial_ids:
                    self.cb_mouse.addItem(mid)
        except Exception:
            pass

        self._set_running(False)
        self.logger.info("UI démarrée.")

    # helpers
    def _mk_button(self, text:str):
        b = QtWidgets.QPushButton(text); b.setMinimumHeight(40)
        b.setStyleSheet("QPushButton { font-size: 14px; font-weight: 700; border-radius: 10px; padding: 6px 12px; border: 1px solid #707070; background: #FFFFFF; }")
        return b

    def _refresh_ports(self):
        self.cb_port.clear()
        ports = _list_serial_ports()
        if ports: self.cb_port.addItems(ports)
        else:
            import sys
            self.cb_port.addItem("COM3" if sys.platform.startswith("win") else "/dev/ttyUSB0")

    def _set_running(self, running: bool):
        self.btn_start.setEnabled(not running); self.btn_stop.setEnabled(running)
        self.cb_port.setEnabled(not running); self.cb_baud.setEnabled(not running); self.btn_refresh_ports.setEnabled(not running)

    # slots UI
    @QtCore.pyqtSlot()
    def on_start(self):
        port = self.cb_port.currentText().strip()
        try: baud = int(self.cb_baud.currentText().strip())
        except ValueError: baud = 115200; self.cb_baud.setCurrentText(str(baud))
        try: self._controle.configure_serial(port, baud)
        except Exception: pass
        self.logger.info(f"START -> port={port}, baud={baud}")
        self._controle.start(); self._set_running(True)

    @QtCore.pyqtSlot()
    def on_stop(self):
        self.logger.info("STOP cliqué.")
        self._controle.stop(); self._set_running(False)

    @QtCore.pyqtSlot()
    def on_reset(self):
        self.logger.warning("RESET: nettoyage UI et état.")
        self._controle.reset()
        for t in self.tiles: t.set_empty()

    @QtCore.pyqtSlot()
    def on_export_csv(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Exporter l'historique", "historique.csv", "CSV (*.csv)")
        if not path: return
        try:
            self._controle.export_history_csv(path)
            QtWidgets.QMessageBox.information(self, "Export", f"Export OK: {path}")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export", f"Erreur: {e}")

    @QtCore.pyqtSlot()
    def on_clear_history(self):
        confirm = QtWidgets.QMessageBox.question(self, "Vider l'historique", "Effacer tous les fichiers de logs ?", QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if confirm == QtWidgets.QMessageBox.Yes:
            self._controle.clear_history()
            self.cb_mouse.clear()  # vider la liste visible
            QtWidgets.QMessageBox.information(self, "Historique", "Historique vidé.")

    # slots data
    @QtCore.pyqtSlot(dict)
    def on_update(self, mapping):
        import time
        self.logger.debug(f"Update reçu: zones={list(mapping.keys())}")
        for t in self.tiles:
            t.set_empty()
        for idx, ids in mapping.items():
            if 0 <= idx < len(self.tiles):
                self.tiles[idx].set_ids(ids)

    @QtCore.pyqtSlot(list)
    def on_ids_catalog_updated(self, ids_list):
        current = {self.cb_mouse.itemText(i) for i in range(self.cb_mouse.count())}
        for mid in ids_list:
            if mid not in current: self.cb_mouse.addItem(mid)

    @QtCore.pyqtSlot(int)
    def on_current_count(self, n: int):
        self.lbl_realtime.setText(str(n))

    # logs
    @QtCore.pyqtSlot(str)
    def append_log(self, line: str):
        self.txt_logs.appendPlainText(line)

    # historique
    def on_show_history(self):
        mid = self.cb_mouse.currentText().strip()
        if not mid:
            QtWidgets.QMessageBox.information(self, "Historique", "Choisis une souris dans la liste."); return
        events = self._controle.get_history(mid)
        self._show_history_dialog(mid, events)

    def _show_history_dialog(self, mouse_id, events):
        dlg = QtWidgets.QDialog(self); dlg.setWindowTitle(f"Historique – {mouse_id}")
        h = QtWidgets.QHBoxLayout(dlg)

        table = QtWidgets.QTableWidget(len(events), 3, dlg)
        table.setHorizontalHeaderLabels(["Heure", "Zone", "Événement"])
        table.horizontalHeader().setStretchLastSection(True)
        for r, ev in enumerate(events):
            table.setItem(r, 0, QtWidgets.QTableWidgetItem(ev.ts.strftime("%Y-%m-%d %H:%M:%S")))
            table.setItem(r, 1, QtWidgets.QTableWidgetItem(str(ev.zone_idx + 1)))
            table.setItem(r, 2, QtWidgets.QTableWidgetItem(EVENT_LABELS_FR.get(ev.event, ev.event)))
        table.resizeColumnsToContents()
        h.addWidget(table, 1)

        view = TrajectoryWidget(); view.set_events(events); view.setMinimumSize(420, 360)
        h.addWidget(view, 1)

        vfooter = QtWidgets.QVBoxLayout()
        btn_close = QtWidgets.QPushButton("Fermer"); btn_close.clicked.connect(dlg.accept)
        vfooter.addStretch(1); vfooter.addWidget(btn_close, alignment=QtCore.Qt.AlignRight)
        h.addLayout(vfooter)

        dlg.resize(950, 480); dlg.exec_()

class TrajectoryWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._points = []   # [(r,c), ...] points compacts (par case)
        self._seq = []      # [1..N] numérotation d'affichage
        self._zones = []    # [z_idx, ...] zones correspondantes

    def set_events(self, events):
        # Construit la séquence (r,c) à partir des événements
        seq_pts = []
        for ev in events:
            if ev.event in ("enter", "stay"):
                z = ev.zone_idx
                r, c = divmod(z, 5)
                seq_pts.append((r, c, z))

        # Compacte: garde un seul point lorsque la case ne change pas
        compact = []
        for p in seq_pts:
            if not compact or compact[-1][:2] != p[:2]:
                compact.append(p)

        self._points = [(r, c) for (r, c, _) in compact]
        self._zones  = [z for (_, _, z) in compact]
        self._seq    = list(range(1, len(self._points) + 1))
        self.update()

    def paintEvent(self, e):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Géométrie de la grille
        w, h = self.width(), self.height()
        margin = 20
        grid_w, grid_h = w - 2 * margin, h - 2 * margin
        cols, rows = 5, 3
        cw, rh = grid_w / cols, grid_h / rows

        # Fond
        p.fillRect(self.rect(), QtGui.QColor("#FFFFFF"))

        # Grille
        pen_grid = QtGui.QPen(QtGui.QColor("#3C3C3C"))
        pen_grid.setWidth(1)
        p.setPen(pen_grid)
        for r in range(rows):
            for c in range(cols):
                x = margin + c * cw
                y = margin + r * rh
                p.drawRect(QtCore.QRectF(x, y, cw, rh))

        def center_of(r, c):
            return QtCore.QPointF(margin + c * cw + cw / 2,
                                  margin + r * rh + rh / 2)

        # Chemin (lignes) — relié aux centres des cases
        if len(self._points) >= 2:
            pen_path = QtGui.QPen(QtGui.QColor("#2D7FF9"))
            pen_path.setWidth(3)
            p.setPen(pen_path)
            for i in range(len(self._points) - 1):
                p.drawLine(center_of(*self._points[i]),
                           center_of(*self._points[i + 1]))

        # --- Déplacement des pastilles lors de revisites d'une même case ---
        from collections import defaultdict
        visit_idx = defaultdict(int)  # (r,c) -> 0,1,2,...

        # Taille de la pastille et amplitude du décalage
        radius = min(cw, rh) * 0.12
        step = max(8.0, radius * 0.9)  # ajuste si besoin

        # Suite d'offsets (cycle) pour écarter les revisites
        offsets = [
            QtCore.QPointF(0, 0),
            QtCore.QPointF(+step, -step),
            QtCore.QPointF(-step, +step),
            QtCore.QPointF(+step, +step),
            QtCore.QPointF(-step, -step),
            QtCore.QPointF(0, +step),
            QtCore.QPointF(+step, 0),
            QtCore.QPointF(-step, 0),
            QtCore.QPointF(0, -step),
        ]

        # Pastilles + numéros
        p.setPen(QtCore.Qt.NoPen)
        brush_node = QtGui.QBrush(QtGui.QColor("#78D46A"))

        for i, (r, c) in enumerate(self._points):
            base = center_of(r, c)
            k = (r, c)
            k_idx = visit_idx[k]
            visit_idx[k] += 1

            off = offsets[k_idx % len(offsets)]
            center = QtCore.QPointF(base.x() + off.x(), base.y() + off.y())

            # pastille
            p.setBrush(brush_node)
            p.drawEllipse(center, radius, radius)

            # numéro (1..N)
            p.setPen(QtGui.QPen(QtGui.QColor("#000")))
            p.setFont(QtGui.QFont("", 10, QtGui.QFont.DemiBold))
            rect = QtCore.QRectF(center.x() - radius, center.y() - radius,
                                 2 * radius, 2 * radius)
            p.drawText(rect, QtCore.Qt.AlignCenter, str(i + 1))