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
    # "Souris-01": "Souris Alpha",
    #  "Souris-02": "Souris Beta",
    #  "Souris-03": "Souris Gamma",
    #  "Souris-04": "Souris Delta",
    #  "Souris-05": "Souris Epsilon",
    #  "Souris-06": "Souris Zeta",
    #  "Souris-07": "Souris Eta",
    #  "Souris-08": "Souris Theta"
}

# ======== Commandes du multiplexeur PE42582A-X========
CMD_SCAN_ON  = "SCAN 1"
CMD_SCAN_OFF = "SCAN 0"
CMD_SEL      = "SEL {n}"
CMD_RATE     = "RATE {ms}"
CMD_ANT_Q    = "ANT?"
CMD_LIST     = "LIST {items}"
CMD_DEBUG    = "DEBUG"
CMD_DEBUG_ON = "DEBUG ON"
CMD_DEBUG_OFF= "DEBUG OFF"

# ======== 8 UID factices pour MUX PE42582A-X ========
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

def resolve_idtag(idtag: str) -> str:
    return IDTAG_TO_NAME.get(str(idtag), str(idtag))

# Si 'antenne' != zone, mappe ici
ANTENNE_TO_ZONE = {
    # 0:0, 1:1, ...
}
def antenne_to_zone(antenne: int) -> int:
    return ANTENNE_TO_ZONE.get(antenne, antenne)
