# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets, QtGui
    
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