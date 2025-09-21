# -*- coding: utf-8 -*-
import random
from PyQt5 import QtCore
from Pilotes.stm32controle import STM32Controle

class STM32ControleFake(STM32Controle):
    def __init__(self, parent=None, period_ms=600, pool_size=30, max_per_zone=3):
        super().__init__(parent)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.active = False
        self.period_ms = period_ms
        self.max_per_zone = max_per_zone
        self._ids_pool = self._make_ids_pool(pool_size)

    def _make_ids_pool(self, n):
        hexchars = "0123456789ABCDEF"
        return ["".join(random.choices(hexchars, k=6)) for _ in range(n)]

    def start(self):
        if self.active: return
        self.active = True
        self.timer.start(self.period_ms)

    def stop(self):
        self.active = False
        self.timer.stop()

    def reset(self):
        self.updated.emit({})

    def set_num_mice(self, n): pass  # non utilisé ici

    def _tick(self):
        total_zones = 15
        n = random.randint(0, min(10, len(self._ids_pool)))
        chosen_ids = random.sample(self._ids_pool, n)
        mapping = {}
        for mouse_id in chosen_ids:
            # essayer de limiter à 3 par zone
            for _ in range(4):
                idx = random.randrange(total_zones)
                lst = mapping.setdefault(idx, [])
                if len(lst) < self.max_per_zone:
                    lst.append(mouse_id)
                    break
        self.updated.emit(mapping)
