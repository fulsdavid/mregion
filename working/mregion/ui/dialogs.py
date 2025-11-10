# mregion/ui/dialogs.py
from __future__ import annotations
from PyQt6 import QtWidgets

class ScaleDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scale")
        self.setLayout(QtWidgets.QVBoxLayout())
        form = QtWidgets.QFormLayout()
        self.val = QtWidgets.QDoubleSpinBox()
        self.val.setRange(1e-12, 1e12)
        self.val.setDecimals(6)
        self.val.setValue(1.0)
        self.units = QtWidgets.QComboBox()
        self.units.addItems(["cm", "mm", "um", "nm"])
        form.addRow("Value", self.val)
        form.addRow("Units", self.units)
        self.layout().addLayout(form)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                          QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self.layout().addWidget(btns)

    def get(self):
        # Returns (value, unit) on OK; None on Cancel
        if self.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return float(self.val.value()), self.units.currentText()
        return None
