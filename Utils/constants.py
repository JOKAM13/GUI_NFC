# -*- coding: utf-8 -*-
ZONE_NAMES = [
    "Zone 1","Zone 2","Zone 3","Zone 4","Zone 5",
    "Zone 6","Zone 7","Zone 8","Zone 9","Zone 10",
    "Zone 11","Zone 12","Zone 13","Zone 14","Zone 15",
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
     "11BEEF": "Souris Gamma",
     "C0FFEE": "Souris Delta",
     "DEAD42": "Souris Epsilon",
     "FACE01": "Souris Zeta",
     "BADA55": "Souris Eta",
     "F00DBE": "Souris Theta"
}

def resolve_idtag(idtag: str) -> str:
    return IDTAG_TO_NAME.get(str(idtag), str(idtag))

# Si 'antenne' != zone, mappe ici
ANTENNE_TO_ZONE = {
    # 0:0, 1:1, ...
}
def antenne_to_zone(antenne: int) -> int:
    return ANTENNE_TO_ZONE.get(antenne, antenne)
