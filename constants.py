# -*- coding: utf-8 -*-
ZONE_NAMES = [
    "Zone A","Zone B","Zone C","Zone D","Zone E",
    "Zone F","Zone G","Zone H","Zone I","Zone J",
    "Zone K","Zone L","Zone M","Zone N","Zone O",
]

PASTEL_BG   = "#EFEFEF"   # fond neutre pour cases vides
GRID_BORDER = "#3C3C3C"   # bordures
GREEN_ACTIVE= "#78D46A"   # vert pour détection
TITLE_BG    = "#6D6D6D"   # barre de titre
TITLE_FG    = "#FFFFFF"
PANEL_BG    = "#EDEDED"
APP_BG      = "#D0D0D0"


MOUSE_IMAGE_PATH = "assets/mouse.jpg"

# Table de correspondance idtag -> nom lisible
IDTAG_TO_NAME = {
    "ABC123": "Souris Alpha",
     "00F1A2": "Souris Beta",
}

def resolve_idtag(idtag: str) -> str:
    return IDTAG_TO_NAME.get(str(idtag), str(idtag))

# Si 'antenne' != zone, mappe ici
ANTENNE_TO_ZONE = {
    # 0:0, 1:1, ...
}
def antenne_to_zone(antenne: int) -> int:
    return ANTENNE_TO_ZONE.get(antenne, antenne)
