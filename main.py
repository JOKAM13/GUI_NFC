# -*- coding: utf-8 -*-
from PyQt5 import QtWidgets
import sys
from controle_donnee import ControleDonnee
from stm32controle_fake import STM32ControleFake
# from stm32controle_serial import STM32ControleSerial
from afficheur import Afficheur
from stm32controle_serial import STM32ControleSerial

def main():
    app = QtWidgets.QApplication(sys.argv)
    #stm32 = STM32ControleFake()  # Remplace par STM32ControleSerial(...) pour la vraie liaison
    stm32 = STM32ControleSerial(port="COM4", baudrate=115200)
    controle = ControleDonnee(stm32)
    ui = Afficheur(controle); ui.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
