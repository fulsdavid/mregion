# mregion/tabs/train.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any
import json
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

# Re-export UNet for compatibility with analysis.py
try:
    from .unet_model import UNet  # preferred source of the model
except Exception:
    UNet = None  # type: ignore

def _load_annotations(path: str) -> dict:
    """Load unified annotations JSON (or legacy) and return only regions + labels."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    regions: List[Dict[str, Any]] = []
    labels: List[str] = []

    if isinstance(data, dict) and ("regions" in data or "polygons" in data):
        raw_regions = data.get("regions", data.get("polygons", []))
        for r in raw_regions:
            if not isinstance(r, dict):
                continue
            pts = r.get("points") or r.get("pts") or r.get("xy") or []
            if pts:
                regions.append({"label": r.get("label", "object"), "points": pts})
        if isinstance(data.get("labels"), list):
            labels = [str(x) for x in data["labels"]]
        else:
            labels = sorted({r["label"] for r in regions})
    elif isinstance(data, list):
        for r in data:
            if isinstance(r, dict) and r.get("points"):
                regions.append({"label": r.get("label", "object"), "points": r["points"]})
        labels = sorted({r["label"] for r in regions})

    return {"regions": regions, "labels": labels}

class TrainTab(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        v = QtWidgets.QVBoxLayout(self)

        top = QtWidgets.QHBoxLayout()
        self.btn_load = QtWidgets.QPushButton("Open Annotations…")
        self.cmb_label = QtWidgets.QComboBox()
        self.btn_train = QtWidgets.QPushButton("Train")
        top.addWidget(self.btn_load)
        top.addWidget(QtWidgets.QLabel("Label:"))
        top.addWidget(self.cmb_label)
        top.addWidget(self.btn_train)
        v.addLayout(top)

        self.txt_log = QtWidgets.QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        v.addWidget(self.txt_log, 1)

        self._regions: List[Dict[str, Any]] = []
        self._labels: List[str] = []

        self.btn_load.clicked.connect(self._on_load_regions)
        self.btn_train.clicked.connect(self._on_train)

    def _on_load_regions(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open annotations", str(Path.cwd()), "JSON (*.json)"
        )
        if not path:
            return
        try:
            ann = _load_annotations(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load error", f"Failed to load: {e}")
            return
        # Only Regions are recorded here; boundary/scale are ignored by design
        self._regions = ann["regions"]
        self._labels = ann["labels"] or ["object"]

        self.cmb_label.clear()
        self.cmb_label.addItems(self._labels)
        self.txt_log.appendPlainText(
            f"Loaded {len(self._regions)} regions; labels={self._labels}"
        )

    def _on_train(self) -> None:
        if not self._regions:
            QtWidgets.QMessageBox.information(self, "No regions", "Load annotations first.")
            return
        label = self.cmb_label.currentText().strip()
        if not label:
            QtWidgets.QMessageBox.information(self, "No label", "Choose a label to train.")
            return
        # TODO: build dataset/masks using only self._regions filtered by 'label'
        self.txt_log.appendPlainText(f"Training with label='{label}' on {len(self._regions)} regions…")
        # ... your existing training logic ...
