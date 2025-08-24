# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets
from constants import PASTEL_BG, GRID_BORDER, GREEN_ACTIVE

class GridTile(QtWidgets.QFrame):
    def __init__(self, zone_name: str, parent=None):
        super().__init__(parent)
        self.zone_name = zone_name
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setObjectName("tile")

        self.title = QtWidgets.QLabel(zone_name)
        self.title.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        self.title.setStyleSheet("font-weight: 600; font-size: 12px;")

        self.ids = QtWidgets.QLabel("")
        self.ids.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self.ids.setStyleSheet("font-size: 13px; font-weight: 600;")
        self.ids.setWordWrap(True)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(0)
        lay.addWidget(self.title)
        lay.addStretch(1)
        lay.addWidget(self.ids)
        lay.addStretch(2)

        self.set_empty()

    def set_empty(self):
        self.setStyleSheet(f"#tile {{ background: {PASTEL_BG}; border: 1px solid {GRID_BORDER}; }}")
        self.ids.setText("")

    def set_ids(self, id_list):
        if not id_list:
            self.set_empty()
            return
        self.setStyleSheet(f"#tile {{ background: {GREEN_ACTIVE}; border: 1px solid {GRID_BORDER}; }}")
        lines = [f"ID : {s}" for s in id_list]
        self.ids.setText("\n".join(lines))
