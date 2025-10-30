from PyQt5 import QtCore
from Pilotes.stm32controle import STM32Controle
from Stockage.history_csv import HistoryStoreCSV
from datetime import datetime
from Utils.constants import resolve_idtag, antenne_to_zone

class ControleDonnee(QtCore.QObject):
    data_updated = QtCore.pyqtSignal(dict)
    ids_catalog_updated = QtCore.pyqtSignal(list)
    current_count_updated = QtCore.pyqtSignal(int)

    def __init__(self, stm32controle: STM32Controle, store=None, parent=None):
        super().__init__(parent)
        self._stm = stm32controle
        self._stm.updated.connect(self._on_raw_update)
        self._history = store or HistoryStoreCSV("logs")
        self._last_presence = {}      
        self._last_event = {}         # NEW: pour dédupliquer les 'stay'
        self._known_ids = set()

        # --- NEW: émettre id present depuis le debut 
        try:
            pre_ids = set(self._history.preload_ids_from_disk())
            if pre_ids:
                self._known_ids |= pre_ids
                self.ids_catalog_updated.emit(sorted(self._known_ids))
        except Exception:
            pass

    def start(self): self._stm.start()
    def stop(self): self._stm.stop()
    def reset(self):
        self._stm.reset()
        self._last_presence.clear()
        self._last_event.clear()

    def set_num_mice(self, n: int): pass  

    
    def get_mouse_ids(self):
        ids = set(self._history.get_mouse_ids())
        try:
            ids.update(self._history.preload_ids_from_disk())
        except Exception:
            pass
        return sorted(ids)

    def get_history(self, mouse_id: str): return self._history.get_history(mouse_id)
    def export_history_csv(self, path: str, mouse_ids=None): self._history.export_csv(path, mouse_ids)

    def clear_history(self):
        import os, glob
        for f in glob.glob("logs/*.csv"):
            try: os.remove(f)
            except: pass
        if hasattr(self._history, "_mem"): self._history._mem.clear()
        self._last_presence.clear()
        self._last_event.clear()     
        self._known_ids.clear()

    def configure_serial(self, port: str, baudrate: int):
        try:
            from stm32controle_serial import STM32ControleSerial
        except Exception:
            STM32ControleSerial = None
        if STM32ControleSerial and isinstance(self._stm, STM32ControleSerial):
            running = getattr(self._stm, "_thread", None) is not None
            if running: self._stm.stop()
            self._stm.configure(port=port, baudrate=baudrate)

    @QtCore.pyqtSlot(dict)
    def _on_raw_update(self, mapping: dict):
        now = datetime.now()
        normalized = {}

        def add(zone_idx: int, raw_idtag: str):
            zone = antenne_to_zone(zone_idx)
            name = resolve_idtag(raw_idtag)
            normalized.setdefault(zone, []).append(name) #  ici j'ajoute le nom reel de la souris pour que ce soit plus lisible dans l'interface

       
        if isinstance(mapping, dict):
            if "readings" in mapping and isinstance(mapping["readings"], list):
                for item in mapping["readings"]:
                    try: add(int(item.get("antenne")), item.get("idtag"))
                    except: continue
            else:
                for k, v in mapping.items():
                    try: key_int = int(k)
                    except: continue
                    if isinstance(v, (list, tuple)):
                        for raw_idtag in v: add(key_int, raw_idtag)
                    else: add(key_int, v)
        elif isinstance(mapping, list):
            for item in mapping:
                try: add(int(item.get("antenne")), item.get("idtag"))
                except: continue
        else:
            normalized = {}

        # Présence courante par souris
        current_presence = {}
        for zone_idx, names in normalized.items():
            for n in names:
                current_presence[n] = zone_idx

        # --- LOGIQUE D'ÉVÉNEMENTS AVEC DÉDUP DES 'stay' ---
        for mid, z in current_presence.items():
            if mid not in self._last_presence:
                # Entrée pour une nouvelle souris/présence
                self._history.add_event(mid, z, "enter", now)
                self._last_event[mid] = ("enter", z)
            else:
                prev_z = self._last_presence[mid]
                if prev_z == z:
                    # Ne loguer 'stay' qu'une seule fois tant que la souris ne quitte pas la zone
                    if self._last_event.get(mid) != ("stay", z):
                        self._history.add_event(mid, z, "stay", now)
                        self._last_event[mid] = ("stay", z)
                else:
                    # Changement de zone: leave ancienne zone + enter nouvelle
                    self._history.add_event(mid, prev_z, "leave", now)
                    self._history.add_event(mid, z, "enter", now)
                    self._last_event[mid] = ("enter", z)

        # Détections des sorties (non présentes maintenant mais présentes avant)
        for mid, prev_z in self._last_presence.items():
            if mid not in current_presence:
                self._history.add_event(mid, prev_z, "leave", now)
                self._last_event[mid] = ("leave", prev_z)

        # État pour la prochaine itération
        self._last_presence = current_presence

        # Signaux UI
        self.data_updated.emit(normalized)
        self.current_count_updated.emit(len(current_presence))

        # Nouveaux IDs découverts à chaud
        added = set(current_presence.keys()) - self._known_ids
        if added:
            self._known_ids |= added
            self.ids_catalog_updated.emit(sorted(self._known_ids))
