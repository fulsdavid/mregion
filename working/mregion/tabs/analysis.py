from __future__ import annotations

from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import json
import numpy as np

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

# Use same fast PyQtGraph display as Annotate
from ..ui.fast_image import FastImageCanvas
from ..common.utils import load_tiff_preview


class DisplayPolygon(QtWidgets.QGraphicsPathItem):
    """Closed (optionally filled) polygon for display only."""
    def __init__(self,
                 pts: List[Tuple[float, float]],
                 color: Tuple[float, float, float, float] = (1, 0, 0, 0.9),
                 width: int = 2,
                 closed: bool = True,
                 fill: bool = True,
                 z: float = 10):
        super().__init__()
        r, g, b, a = color
        pen = QtGui.QPen(QtGui.QColor.fromRgbF(r, g, b, a), width)
        pen.setCosmetic(True)
        self.setPen(pen)

        if closed and fill:
            self.setBrush(QtGui.QBrush(QtGui.QColor.fromRgbF(r, g, b, min(0.3, a * 0.5))))
        else:
            self.setBrush(QtCore.Qt.GlobalColor.transparent)

        self.setZValue(z)

        path = QtGui.QPainterPath()
        if pts:
            path.moveTo(*pts[0])
            for p in pts[1:]:
                path.lineTo(*p)
            if closed:
                path.closeSubpath()
        self.setPath(path)


class DisplayPolyline(DisplayPolygon):
    """Open polyline for display only (e.g. scale, measurements)."""
    def __init__(self, pts, color=(0, 1, 0, 1), width=2, z=12):
        super().__init__(pts, color=color, width=width, closed=False, fill=False, z=z)


class AnalysisTab(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.image_path: Optional[Path] = None
        self.base_img: Optional[np.ndarray] = None
        self.image_size = (0, 0)
        self.annotations: Dict[str, Any] = {}

        # UI layout ---------------------------------------------------------
        root = QtWidgets.QVBoxLayout(self)

        hb = QtWidgets.QHBoxLayout()
        self.btn_open = QtWidgets.QPushButton("Open Image…")
        self.btn_load_annotations = QtWidgets.QPushButton("Load Annotations…")
        self.btn_clear = QtWidgets.QPushButton("Clear Overlays")
        self.btn_report = QtWidgets.QPushButton("Generate Report")
        hb.addWidget(self.btn_open)
        hb.addWidget(self.btn_load_annotations)
        hb.addStretch(1)
        hb.addWidget(self.btn_clear)
        hb.addWidget(self.btn_report)
        root.addLayout(hb)

        # Shared FastImageCanvas used in Annotate
        self.canvas = FastImageCanvas()
        self.toolbar = self.canvas.make_toolbar(self)
        root.addWidget(self.toolbar)
        root.addWidget(self.canvas, 1)

        # Status console
        self.txt_log = QtWidgets.QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(160)
        root.addWidget(self.txt_log)

        # Overlay storage
        self._regions: List[QtWidgets.QGraphicsPathItem] = []
        self._boundary: Optional[QtWidgets.QGraphicsPathItem] = None
        self._scale: Optional[QtWidgets.QGraphicsPathItem] = None
        self._measures: List[QtWidgets.QGraphicsPathItem] = []

        # Connect buttons
        self.btn_open.clicked.connect(self._on_open_image)
        self.btn_load_annotations.clicked.connect(self._on_load_ann)
        self.btn_clear.clicked.connect(self._clear_overlays)
        self.btn_report.clicked.connect(self._on_generate_report)

    # --- Helpers ---------------------------------------------------------

    def _log(self, msg: str):
        self.txt_log.appendPlainText(msg)

    # --- Image Load ------------------------------------------------------

    def _on_open_image(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open image", str(Path.cwd()),
            "Images (*.tif *.tiff *.png *.jpg)"
        )
        if not p:
            return
        self.image_path = Path(p)

        arr, _, (H, W) = load_tiff_preview(self.image_path, max_side=4096)
        self.base_img = arr
        self.image_size = (H, W)

        self.canvas.set_image(arr, extent=(0, W, H, 0))
        self._log(f"Loaded: {self.image_path.name} [{W}x{H}]")

        if self.annotations:
            self._draw_annotations()

    # --- Annotations Load -------------------------------------------------

    def _on_load_ann(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Annotations", str(Path.cwd()),
            "JSON (*.json)"
        )
        if not p:
            return

        try:
            with open(p, "r", encoding="utf-8") as f:
                ann = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error",
                                          f"Failed to read file:\n{e}")
            return

        self.annotations = ann or {}
        self._log(f"Annotations loaded: {Path(p).name}")
        self._draw_annotations()

    # --- Clearing Overlays -----------------------------------------------

    def _clear_overlays(self):
        vb = self.canvas._vb
        for item in self._regions:
            vb.removeItem(item)
        self._regions.clear()

        if self._boundary:
            vb.removeItem(self._boundary)
            self._boundary = None

        if self._scale:
            vb.removeItem(self._scale)
            self._scale = None

        for item in self._measures:
            vb.removeItem(item)
        self._measures.clear()

        self._log("Overlays cleared.")

    # --- Drawing overlays ------------------------------------------------

    def _draw_annotations(self):
        if not self.annotations:
            return

        self._clear_overlays()
        vb = self.canvas._vb

        # Regions (closed + lightly filled)
        for reg in self.annotations.get("regions", []):
            pts = [(float(x), float(y)) for x, y in reg.get("points", [])]
            col = tuple(reg.get("color", (1, 0, 0, 0.9)))
            item = DisplayPolygon(pts, color=col, closed=True, fill=True, width=2, z=15)
            vb.addItem(item)
            self._regions.append(item)

        # Boundary (CLOSED loop, NO fill)
        b = self.annotations.get("boundary")
        if b and b.get("points"):
            pts = [(float(x), float(y)) for x, y in b.get("points")]
            item = DisplayPolygon(
                pts,
                color=(0.2, 0.7, 1, 1),
                closed=True,
                fill=False,
                width=2,
                z=18
            )
            vb.addItem(item)
            self._boundary = item

        # Scale (open polyline)
        s = self.annotations.get("scale")
        if s and s.get("p1") and s.get("p2"):
            p1 = tuple(map(float, s["p1"]))
            p2 = tuple(map(float, s["p2"]))
            item = DisplayPolyline([p1, p2], color=(0, 1, 0, 1), width=2, z=20)
            vb.addItem(item)
            self._scale = item

        # Measurements (open polylines)
        for m in self.annotations.get("measurements", []):
            p1 = tuple(map(float, m.get("p1", [0, 0])))
            p2 = tuple(map(float, m.get("p2", [0, 0])))
            item = DisplayPolyline([p1, p2], color=(1, 0.5, 0, 1), width=2, z=16)
            vb.addItem(item)
            self._measures.append(item)

        try:
            self.canvas.fit_to_image()
        except Exception:
            pass

        self._log("Overlay drawing complete.")

    # --- Report generation -----------------------------------------------

    def _on_generate_report(self):
        if not self.annotations:
            QtWidgets.QMessageBox.information(self, "No annotations", "Load an annotations file first.")
            return

        boundary = self.annotations.get("boundary")
        if not boundary or not boundary.get("points"):
            QtWidgets.QMessageBox.information(self, "No boundary", "Report requires a Boundary polygon.")
            return

        regions = self.annotations.get("regions") or []
        if not regions:
            QtWidgets.QMessageBox.information(self, "No regions", "There are no Regions to report on.")
            return

        # --- Rasterize on the *actual image pixel grid* (full resolution) ---
        if self.base_img is not None:
            H, W = int(self.base_img.shape[0]), int(self.base_img.shape[1])
        else:
            W = int(self.image_size[1] or 0)
            H = int(self.image_size[0] or 0)

        if W <= 0 or H <= 0:
            # Fallback: derive a conservative canvas from geometry bounds
            all_pts = []
            all_pts += [(float(x), float(y)) for x, y in (boundary.get("points") or [])]
            for r in regions:
                all_pts += [(float(x), float(y)) for x, y in (r.get("points") or [])]
            if not all_pts:
                QtWidgets.QMessageBox.information(self, "No geometry", "No polygon coordinates found.")
                return
            xs = [p[0] for p in all_pts]
            ys = [p[1] for p in all_pts]
            W = max(2, int(max(xs)) + 2)
            H = max(2, int(max(ys)) + 2)

        rw, rh = W, H

        def make_mask(poly_pts):
            img = QtGui.QImage(rw, rh, QtGui.QImage.Format.Format_Grayscale8)
            img.fill(0)
            qp = QtGui.QPainter(img)
            qp.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)
            qp.setPen(QtCore.Qt.PenStyle.NoPen)
            qp.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.white))
            qpoly = QtGui.QPolygonF([QtCore.QPointF(float(x), float(y)) for (x, y) in poly_pts])
            qp.drawPolygon(qpoly, QtCore.Qt.FillRule.WindingFill)
            qp.end()
            ptr = img.bits()
            ptr.setsize(rw * rh)
            arr = np.frombuffer(ptr, dtype=np.uint8).reshape((rh, rw))
            return arr > 0

        # Boundary mask & area in *image pixels*
        b_pts = [(float(x), float(y)) for x, y in (boundary.get("points") or [])]
        b_mask = make_mask(b_pts)
        b_area_px = int(b_mask.sum())
        if b_area_px == 0:
            QtWidgets.QMessageBox.information(self, "Empty boundary", "Boundary area is zero after rasterization.")
            return

        # Scale (units per original pixel) — compute using original coords
        u_per_px = None
        unit = ""
        s = self.annotations.get("scale")
        if s and s.get("p1") and s.get("p2") and ("value" in s):
            p1 = tuple(map(float, s["p1"]))
            p2 = tuple(map(float, s["p2"]))
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            pix_len = (dx*dx + dy*dy) ** 0.5
            if pix_len > 0:
                u_per_px = float(s["value"]) / pix_len
                unit = str(s.get("unit", ""))

        # Aggregate by label using ONLY the intersection area with the boundary
        totals_px: Dict[str, int] = {}
        totals_count: Dict[str, int] = {}

        for reg in regions:
            r_pts = [(float(x), float(y)) for x, y in (reg.get("points") or [])]
            if len(r_pts) < 3:
                continue
            r_mask = make_mask(r_pts)
            inter = r_mask & b_mask  # only the portion inside boundary
            area_px = int(inter.sum())
            if area_px == 0:
                continue
            label = reg.get("label", "unlabeled")
            totals_px[label] = totals_px.get(label, 0) + area_px
            totals_count[label] = totals_count.get(label, 0) + 1

        # Build report (aggregated by label)
        lines = []
        lines.append(f"Boundary area (px): {b_area_px}")
        if u_per_px is not None:
            b_area_phys = (u_per_px ** 2) * float(b_area_px)
            lines.append(f"Boundary area ({unit}^2): {b_area_phys:g}")

        lines.append("")
        lines.append("Totals by Region type (clipped to boundary):")

        if not totals_px:
            lines.append("  (No region area fell within the boundary.)")
        else:
            for label, total_px in sorted(totals_px.items()):
                pct = 100.0 * float(total_px) / float(b_area_px)
                if u_per_px is None:
                    lines.append(f"  {label:15s}  count={totals_count[label]:3d}  total_px={total_px:8d}  %boundary={pct:6.2f}%")
                else:
                    total_phys = (u_per_px ** 2) * float(total_px)
                    lines.append(f"  {label:15s}  count={totals_count[label]:3d}  total_px={total_px:8d}  %boundary={pct:6.2f}%  area={total_phys:g} {unit}^2")

        report = "\n".join(lines)

        # Show in dialog
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Area Report")
        lay = QtWidgets.QVBoxLayout(dlg)
        txt = QtWidgets.QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setPlainText(report)
        lay.addWidget(txt)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Save)
        lay.addWidget(btns)

        def on_save():
            out, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Report", "area_report.txt", "Text (*.txt)")
            if out:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(report)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        btns.button(QtWidgets.QDialogButtonBox.StandardButton.Save).clicked.connect(on_save)

        dlg.resize(720, 420)
        dlg.exec()

        self._log("Report generated (full image pixel grid; zoom-invariant).")
