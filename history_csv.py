# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import List, Iterable, Optional, Dict
from datetime import datetime
import csv, os

@dataclass
class MouseEvent:
    ts: datetime
    mouse_id: str
    zone_idx: int
    event: str  # enter | stay | leave

class HistoryStoreCSV:
    def __init__(self, dirpath: str = "logs"):
        self.dir = dirpath
        os.makedirs(self.dir, exist_ok=True)
        self._mem: Dict[str, List[MouseEvent]] = {}

    def _file_for(self, dt: datetime) -> str:
        return os.path.join(self.dir, dt.strftime("%Y-%m-%d") + ".csv")

    def add_event(self, mouse_id: str, zone_idx: int, event: str, ts: Optional[datetime] = None):
        ts = ts or datetime.now()
        fpath = self._file_for(ts)
        newfile = not os.path.exists(fpath)
        with open(fpath, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if newfile:
                w.writerow(["timestamp", "mouse_id", "zone_idx", "event"])
            w.writerow([ts.isoformat(timespec="seconds"), mouse_id, zone_idx, event])
        self._mem.setdefault(mouse_id, []).append(MouseEvent(ts, mouse_id, zone_idx, event))

    def get_mouse_ids(self) -> List[str]:
        return sorted(self._mem.keys())

    def get_history(self, mouse_id: str) -> List[MouseEvent]:
        return list(self._mem.get(mouse_id, []))

    def export_csv(self, path: str, mouse_ids: Optional[Iterable[str]] = None):
        with open(path, "w", newline="", encoding="utf-8") as out:
            w = csv.writer(out)
            w.writerow(["timestamp", "mouse_id", "zone_idx", "event"])
            for fname in sorted(os.listdir(self.dir)):
                if not fname.endswith(".csv"): continue
                full = os.path.join(self.dir, fname)
                with open(full, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)  # skip header
                    for row in reader:
                        if not row: continue
                        if mouse_ids and row[1] not in mouse_ids: continue
                        w.writerow(row)
