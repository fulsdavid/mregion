# mregion/main.py
from __future__ import annotations
import sys
from PyQt6 import QtWidgets
from .tabs.annotate import AnnotateTab
from .tabs.train import TrainTab
from .tabs.analysis import AnalysisTab

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("mregion — Modular")
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(AnnotateTab(), "Annotate")
        tabs.addTab(TrainTab(), "Train CNN")
        tabs.addTab(AnalysisTab(), "Analysis")
        self.setCentralWidget(tabs)

def main():
    app = QtWidgets.QApplication(sys.argv)
    mw = MainWindow()
    mw.resize(1200, 800)
    mw.show()
    return app.exec()

if __name__ == '__main__':
    raise SystemExit(main())
