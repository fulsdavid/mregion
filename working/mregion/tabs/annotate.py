from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable
import json
import math
import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt

# Project-local imports
from ..ui.fast_image import FastImageCanvas
from ..ui.dialogs import ScaleDialog
from ..common.models import ScaleInfo
from ..common.utils import load_tiff_preview, now_ts, sha256_file, APP_VERSION


# -------------------- Graphics items --------------------

class VertexHandle(QtWidgets.QGraphicsEllipseItem):
    def __init__(
        self,
        x: float,
        y: float,
        radius: float = 5.0,
        parent: Optional[QtWidgets.QGraphicsItem] = None,
        on_drag_state: Optional[Callable[[bool], None]] = None,
        on_moved: Optional[Callable[[], None]] = None,
    ):
        super().__init__(-radius, -radius, 2 * radius, 2 * radius, parent)
        self.setPos(x, y)
        self.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.yellow))
        self.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 1))
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setFlags(
            QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        self.setZValue(50)
        self._on_drag_state = on_drag_state
        self._on_moved = on_moved

    def mousePressEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        try:
            self.grabMouse()
        except Exception:
            pass
        self.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
        if self._on_drag_state:
            self._on_drag_state(True)
        event.accept()

    def mouseMoveEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        parent = self.parentItem()
        if parent is not None:
            p = parent.mapFromScene(event.scenePos())
            self.setPos(p)
            if hasattr(parent, "on_vertex_moved"):
                parent.on_vertex_moved(self)
        if self._on_moved:
            self._on_moved()
        event.accept()

    def mouseReleaseEvent(self, event: QtWidgets.QGraphicsSceneMouseEvent) -> None:
        try:
            self.ungrabMouse()
        except Exception:
            pass
        self.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
        if self._on_drag_state:
            self._on_drag_state(False)
        event.accept()


class EditablePolygon(QtWidgets.QGraphicsPathItem):
    def __init__(
        self,
        points: List[Tuple[float, float]],
        color: Tuple[float, float, float, float],
        label: str,
        on_changed: Optional[Callable[[List[Tuple[float, float]]], None]] = None,
        on_drag_state: Optional[Callable[[bool], None]] = None,
    ):
        super().__init__()
        self._on_changed = on_changed
        self._on_drag_state = on_drag_state
        self.label = label
        self.color = color
        self.setZValue(5)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        r, g, b, a = color
        pen = QtGui.QPen(QtGui.QColor.fromRgbF(r, g, b, a), 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QtGui.QBrush(QtGui.QColor.fromRgbF(r, g, b, max(0.0, min(0.3, a * 0.5)))))

        self.handles: List[VertexHandle] = []
        self._handles_visible = False
        self.set_points(points)

    def _rebuild_handles(self, pts: List[Tuple[float, float]]) -> None:
        for h in self.handles:
            h.setParentItem(None)
        self.handles = [
            VertexHandle(
                x,
                y,
                radius=5.0,
                parent=self,
                on_drag_state=self._on_drag_state,
                on_moved=lambda: self._on_changed([(hh.pos().x(), hh.pos().y()) for hh in self.handles])
                if self._on_changed
                else None,
            )
            for (x, y) in pts
        ]
        for h in self.handles:
            h.setVisible(self._handles_visible)

    def _update_path_from_handles(self) -> None:
        pts = [(h.pos().x(), h.pos().y()) for h in self.handles]
        path = QtGui.QPainterPath()
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            path.closeSubpath()
        self.setPath(path)
        if self._on_changed:
            self._on_changed(pts)

    def set_points(self, pts: List[Tuple[float, float]]) -> None:
        path = QtGui.QPainterPath()
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
            path.closeSubpath()
        self.setPath(path)
        self._rebuild_handles(pts)
        if self._on_changed:
            self._on_changed(pts)

    def on_vertex_moved(self, _h: VertexHandle) -> None:
        self._update_path_from_handles()

    def show_handles(self, visible: bool) -> None:
        self._handles_visible = visible
        for h in self.handles:
            h.setVisible(visible)


class EditablePolyline(QtWidgets.QGraphicsPathItem):
    def __init__(
        self,
        points: List[Tuple[float, float]],
        color: Tuple[float, float, float, float],
        width: int = 2,
        on_changed: Optional[Callable[[List[Tuple[float, float]]], None]] = None,
        on_drag_state: Optional[Callable[[bool], None]] = None,
    ):
        super().__init__()
        self._on_changed = on_changed
        self._on_drag_state = on_drag_state
        self._color = color
        self.setZValue(10)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        r, g, b, a = color
        pen = QtGui.QPen(QtGui.QColor.fromRgbF(r, g, b, a), width)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QtCore.Qt.GlobalColor.transparent)
        self.handles: List[VertexHandle] = []
        self._handles_visible = False
        self.set_points(points)

    def _rebuild_handles(self, pts: List[Tuple[float, float]]) -> None:
        for h in self.handles:
            h.setParentItem(None)
        self.handles = [
            VertexHandle(
                x,
                y,
                radius=5.0,
                parent=self,
                on_drag_state=self._on_drag_state,
                on_moved=lambda: self._on_changed([(hh.pos().x(), hh.pos().y()) for hh in self.handles])
                if self._on_changed
                else None,
            )
            for (x, y) in pts
        ]
        for h in self.handles:
            h.setVisible(self._handles_visible)

    def _update_path_from_handles(self) -> None:
        pts = [(h.pos().x(), h.pos().y()) for h in self.handles]
        path = QtGui.QPainterPath()
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
        self.setPath(path)
        if self._on_changed:
            self._on_changed(pts)

    def set_points(self, pts: List[Tuple[float, float]]) -> None:
        path = QtGui.QPainterPath()
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
        self.setPath(path)
        self._rebuild_handles(pts)
        if self._on_changed:
            self._on_changed(pts)

    def on_vertex_moved(self, _h: VertexHandle) -> None:
        self._update_path_from_handles()

    def to_points(self) -> List[Tuple[float, float]]:
        return [(h.pos().x(), h.pos().y()) for h in self.handles]

    def show_handles(self, visible: bool) -> None:
        self._handles_visible = visible
        for h in self.handles:
            h.setVisible(visible)


# -------------------- Annotate Tab --------------------

class AnnotateTab(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()

        root = QtWidgets.QVBoxLayout(self)

        # Toolbar
        top = QtWidgets.QHBoxLayout()
        self.btn_open = QtWidgets.QPushButton("Open Image…")
        self.cmb_label = QtWidgets.QComboBox()
        self.btn_add_label = QtWidgets.QPushButton("New Label…")
        self.btn_load_ann = QtWidgets.QPushButton("Load Annotations…")
        self.btn_save_all = QtWidgets.QPushButton("Save Annotations…")
        for w in [self.btn_open, self.cmb_label, self.btn_add_label, self.btn_load_ann, self.btn_save_all]:
            top.addWidget(w)
        root.addLayout(top)

        # Split
        split = QtWidgets.QSplitter(Qt.Orientation.Horizontal)

        # Canvas
        canvas_wrap = QtWidgets.QWidget()
        canvas_v = QtWidgets.QVBoxLayout(canvas_wrap)
        self.canvas = FastImageCanvas()
        self.toolbar = self.canvas.make_toolbar(self)
        canvas_v.addWidget(self.toolbar)
        canvas_v.addWidget(self.canvas, 1)
        split.addWidget(canvas_wrap)

        # Side panel
        side = QtWidgets.QWidget()
        sv = QtWidgets.QVBoxLayout(side)

        # Regions
        sv.addWidget(QtWidgets.QLabel("Regions"))
        self.list_regions = QtWidgets.QListWidget()
        self.list_regions.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.list_regions.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_regions.setWordWrap(False)
        sv.addWidget(self.list_regions, 3)
        self.btn_draw = QtWidgets.QPushButton("Draw Region")
        self.btn_del_region = QtWidgets.QPushButton("Delete Selected Region")
        sv.addWidget(self.btn_draw)
        sv.addWidget(self.btn_del_region)

        # Measurements
        sv.addWidget(QtWidgets.QLabel("Measurements"))
        self.list_measure = QtWidgets.QListWidget()
        self.list_measure.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.list_measure.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        meas_line = self.list_measure.fontMetrics().height()
        self.list_measure.setFixedHeight(int(meas_line * 4.2))
        self.list_measure.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sv.addWidget(self.list_measure)
        self.btn_measure = QtWidgets.QPushButton("Measure")
        self.btn_del_measure = QtWidgets.QPushButton("Delete Measurement")
        sv.addWidget(self.btn_measure)
        sv.addWidget(self.btn_del_measure)

        # Boundary
        sv.addWidget(QtWidgets.QLabel("Boundary"))
        self.list_boundary = QtWidgets.QListWidget()
        self.list_boundary.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.list_boundary.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_boundary.setFixedHeight(self.list_boundary.fontMetrics().height() + 10)
        self.list_boundary.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sv.addWidget(self.list_boundary)
        self.btn_draw_boundary = QtWidgets.QPushButton("Draw Boundary")
        self.btn_del_boundary = QtWidgets.QPushButton("Delete Boundary")
        sv.addWidget(self.btn_draw_boundary)
        sv.addWidget(self.btn_del_boundary)

        # Scale
        sv.addWidget(QtWidgets.QLabel("Scale"))
        self.list_scale = QtWidgets.QListWidget()
        self.list_scale.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.list_scale.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scale_line = self.list_scale.fontMetrics().height()
        self.list_scale.setFixedHeight(int(scale_line * 1.4))
        self.list_scale.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sv.addWidget(self.list_scale)
        self.btn_scale = QtWidgets.QPushButton("Scale")
        self.btn_del_scale = QtWidgets.QPushButton("Delete Scale")
        sv.addWidget(self.btn_scale)
        sv.addWidget(self.btn_del_scale)

        # Log
        sv.addWidget(QtWidgets.QLabel("Log"))
        self.txt_log = QtWidgets.QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setMaximumHeight(120)
        sv.addWidget(self.txt_log, 0)

        split.addWidget(side)
        split.setStretchFactor(0, 4)
        split.setStretchFactor(1, 2)
        root.addWidget(split, 1)

        # State
        self.image_path: Optional[Path] = None
        self.image_size: Tuple[int, int] = (0, 0)
        self.base_img: Optional[np.ndarray] = None

        self.labels: List[str] = ["object"]
        self.colors: Dict[str, Tuple[float, float, float, float]] = {"object": (1.0, 0.0, 0.0, 0.9)}
        self.cmb_label.addItems(self.labels)

        self.polygons: List[EditablePolygon] = []
        self.boundary: Optional[EditablePolygon] = None
        self.scale: Optional[ScaleInfo] = None
        self.scale_item: Optional[EditablePolyline] = None
        self.measure_items: List[EditablePolyline] = []

        # Interaction
        self._drag_active: bool = False

        # Drawing states
        self._drawing: bool = False
        self._draw_pts: List[Tuple[float, float]] = []
        self._draw_path_item: Optional[QtWidgets.QGraphicsPathItem] = None
        self._draw_point_markers: List[QtWidgets.QGraphicsEllipseItem] = []
        self._snap_ring: Optional[QtWidgets.QGraphicsEllipseItem] = None

        self._drawing_boundary: bool = False
        self._boundary_pts: List[Tuple[float, float]] = []
        self._boundary_path_item: Optional[QtWidgets.QGraphicsPathItem] = None

        # Scale drawing
        self._scaling: bool = False
        self._scale_pts: List[Tuple[float, float]] = []
        self._scale_temp_item: Optional[QtWidgets.QGraphicsPathItem] = None
        self._scale_point_markers: List[QtWidgets.QGraphicsEllipseItem] = []

        # Measurement drawing
        self._measuring: bool = False
        self._measure_pts: List[Tuple[float, float]] = []
        self._measure_temp_item: Optional[QtWidgets.QGraphicsPathItem] = None
        self._measure_point_markers: List[QtWidgets.QGraphicsEllipseItem] = []

        # Signals
        self.btn_open.clicked.connect(self._on_load_image)
        self.btn_add_label.clicked.connect(self._on_add_label)
        self.btn_draw.clicked.connect(self._on_start_draw)
        self.btn_del_region.clicked.connect(self._on_delete_selected_region)
        self.btn_draw_boundary.clicked.connect(self._on_start_draw_boundary)
        self.btn_del_boundary.clicked.connect(self._on_delete_boundary)
        self.btn_scale.clicked.connect(self._on_set_scale)
        self.btn_del_scale.clicked.connect(self._on_delete_scale)
        self.btn_save_all.clicked.connect(self._on_save_all)
        self.btn_load_ann.clicked.connect(self._on_load_annotations)
        self.btn_measure.clicked.connect(self._on_start_measure)
        self.btn_del_measure.clicked.connect(self._on_delete_measure)

        self.list_regions.currentRowChanged.connect(self._on_select_region)
        self.list_boundary.itemSelectionChanged.connect(self._on_select_boundary)
        self.list_scale.itemSelectionChanged.connect(self._on_select_scale)
        self.list_measure.itemSelectionChanged.connect(self._on_select_measure)

        self.canvas._glw.scene().sigMouseClicked.connect(self._on_scene_click)
        self.canvas._glw.scene().sigMouseMoved.connect(self._on_scene_move)

    # ------------ helpers ------------
    def _log(self, msg: str) -> None:
        self.txt_log.appendPlainText(msg)

    def _view_snap_threshold(self, pixels: int = 10) -> float:
        dx, dy = self.canvas._vb.viewPixelSize()
        return max(dx, dy) * float(pixels)

    def _first_point(self) -> Optional[tuple[float, float]]:
        return tuple(self._draw_pts[0]) if self._draw_pts else None

    def _near_first_point(self, pt: tuple[float, float], pixels: int = 10) -> bool:
        fp = self._first_point()
        if fp is None or len(self._draw_pts) < 2:
            return False
        thr = self._view_snap_threshold(pixels)
        dx = pt[0] - fp[0]
        dy = pt[1] - fp[1]
        return (dx * dx + dy * dy) ** 0.5 <= thr

    def _ensure_snap_ring(self, center: Optional[Tuple[float, float]] = None) -> None:
        if self._snap_ring is None and (self._draw_pts or self._boundary_pts) and center is not None:
            r = 6.0
            ring = QtWidgets.QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
            ring.setPos(center[0], center[1])
            pen = QtGui.QPen(QtCore.Qt.GlobalColor.magenta, 2)
            pen.setCosmetic(True)
            ring.setPen(pen)
            ring.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.transparent))
            ring.setZValue(25)
            self.canvas._vb.addItem(ring)
            self._snap_ring = ring

    def _update_snap_ring(self, show: bool) -> None:
        if self._snap_ring is not None:
            self._snap_ring.setVisible(show)

    def _clear_snap_ring(self) -> None:
        if self._snap_ring is not None:
            self.canvas._vb.removeItem(self._snap_ring)
            self._snap_ring = None

    def _clear_all_overlays(self) -> None:
        try:
            for poly in self.polygons:
                self.canvas._vb.removeItem(poly)
        except Exception:
            pass
        self.polygons = []
        if self.boundary is not None:
            try:
                self.canvas._vb.removeItem(self.boundary)
            except Exception:
                pass
            self.boundary = None
        if self.scale_item is not None:
            try:
                self.canvas._vb.removeItem(self.scale_item)
            except Exception:
                pass
            self.scale_item = None
        self.scale = None
        for it in self.measure_items:
            try:
                self.canvas._vb.removeItem(it)
            except Exception:
                pass
        self.measure_items = []

    def _set_item_highlight(self, item: QtWidgets.QGraphicsPathItem, on: bool) -> None:
        if item is None:
            return
        pen = item.pen()
        if on:
            pen.setWidth(3)
            item.setZValue(30)
        else:
            pen.setWidth(2)
            item.setZValue(10)
        item.setPen(pen)

    def _clear_all_highlights(self) -> None:
        for poly in self.polygons:
            self._set_item_highlight(poly, False)
            poly.show_handles(False)
        if self.boundary is not None:
            self._set_item_highlight(self.boundary, False)
            self.boundary.show_handles(False)
        if self.scale_item is not None:
            self._set_item_highlight(self.scale_item, False)
            self.scale_item.show_handles(False)
        for it in self.measure_items:
            self._set_item_highlight(it, False)
            it.show_handles(False)

    def _on_drag_state(self, dragging: bool) -> None:
        self._drag_active = dragging
        try:
            self.canvas._vb.setMouseEnabled(x=not dragging, y=not dragging)
        except Exception:
            pass
        if not dragging:
            self._refresh_lists()

    def _scale_pixels_length(self) -> float:
        try:
            if self.scale_item is not None:
                pts = self.scale_item.to_points()
                if len(pts) >= 2:
                    dx = pts[1][0] - pts[0][0]
                    dy = pts[1][1] - pts[0][1]
                    return (dx*dx + dy*dy) ** 0.5
            if self.scale is not None and self.scale.p1 and self.scale.p2:
                dx = self.scale.p2[0] - self.scale.p1[0]
                dy = self.scale.p2[1] - self.scale.p1[1]
                return (dx*dx + dy*dy) ** 0.5
        except Exception:
            pass
        return 0.0

    def _units_per_pixel(self) -> Optional[float]:
        """Return real-world units per pixel, based on current scale."""
        if self.scale is None:
            return None
        pix = self._scale_pixels_length()
        if pix <= 0:
            return None
        try:
            return float(self.scale.value) / float(pix)
        except Exception:
            return None
    # --------------- Fill control helper ---------------
    def _make_outline(self, gitem):
        """
        Force a graphics item (or an EditablePolygon wrapper) to render with no fill.
        Works whether 'gitem' is a QGraphicsPathItem itself or a wrapper that keeps
        the actual path item on an attribute like 'path_item' or '_item'.
        """
        candidates = [gitem]
        for attr in ('path_item', '_item', 'item', '_path_item'):
            try:
                candidates.append(getattr(gitem, attr))
            except Exception:
                pass

        for obj in candidates:
            if obj is None:
                continue
            try:
                # Prefer no brush at all
                #obj.setBrush(QtCore.Qt.NoBrush)
                obj.setBrush(QtGui.QBrush(Qt.BrushStyle.NoBrush))
                return
            except Exception:
                pass
            try:
                # Fallback: fully transparent brush
                obj.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.transparent))
                return
            except Exception:
                pass

    # --------------- unified save ---------------
    def _collect_annotations(self) -> dict:
        regions = []
        for poly in self.polygons:
            regions.append(
                {
                    "label": poly.label,
                    "color": [float(c) for c in self.colors.get(poly.label, (1,0,0,1))],
                    "points": [[float(h.pos().x()), float(h.pos().y())] for h in poly.handles],
                }
            )
        boundary = None
        if self.boundary is not None:
            boundary = {
                "label": "boundary",
                "points": [[float(h.pos().x()), float(h.pos().y())] for h in self.boundary.handles],
            }
        scale = None
        if self.scale_item is not None and self.scale is not None:
            pts = self.scale_item.to_points()
            scale = {
                "p1": [float(pts[0][0]), float(pts[0][1])] if len(pts) >= 1 else [0.0, 0.0],
                "p2": [float(pts[1][0]), float(pts[1][1])] if len(pts) >= 2 else [0.0, 0.0],
                "value": float(self.scale.value),
                "unit": str(self.scale.unit),
            }
        measurements = []
        for it in self.measure_items:
            pts = it.to_points()
            px_len = 0.0
            if len(pts) >= 2:
                dx = pts[1][0] - pts[0][0]
                dy = pts[1][1] - pts[0][1]
                px_len = (dx*dx + dy*dy) ** 0.5
            u_per_px = self._units_per_pixel()
            val = px_len * u_per_px if u_per_px is not None else None
            measurements.append({
                "p1": [float(pts[0][0]), float(pts[0][1])] if len(pts) >= 1 else [0.0,0.0],
                "p2": [float(pts[1][0]), float(pts[1][1])] if len(pts) >= 2 else [0.0,0.0],
                "pixel_length": float(px_len),
                "value": float(val) if val is not None else None,
                "unit": self.scale.unit if (self.scale is not None and u_per_px is not None) else "",
            })

        H, W = self.image_size
        return {
            "app_version": APP_VERSION,
            "created_at": now_ts(),
            "image": {
                "path": str(self.image_path) if self.image_path else "",
                "size": [int(W), int(H)],
                "sha256": sha256_file(self.image_path) if self.image_path else "",
            },
            "labels": list(self.labels),
            "regions": regions,
            "boundary": boundary,
            "scale": scale,
            "measurements": measurements,
        }

    def _on_save_all(self) -> None:
        if self.image_path is None or self.base_img is None:
            QtWidgets.QMessageBox.information(self, "No data", "Open an image and annotate first.")
            return
        default = str((self.image_path or Path.cwd()).with_suffix(".annotations.json"))
        out, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Annotations", default, "JSON (*.json)"
        )
        if not out:
            return
        data = self._collect_annotations()
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self._log(f"Saved annotations → {out}")

    def _on_load_annotations(self) -> None:
        fname, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Annotations", str(Path.cwd()), "JSON (*.json)")
        if not fname:
            return
        try:
            with open(fname, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Load failed", f"Could not read file:\n{e}")
            return

        # Labels
        file_labels = data.get("labels", []) or []
        added = False
        for lbl in file_labels:
            if lbl not in self.labels:
                self.labels.append(lbl)
                added = True
        if added:
            self.cmb_label.clear()
            self.cmb_label.addItems(self.labels)

        # Clear overlays
        self._clear_all_overlays()

        # Regions
        for reg in (data.get("regions") or []):
            pts = reg.get("points") or []
            label = reg.get("label", "object")
            col = tuple(reg.get("color", self.colors.get(label, (1.0, 0.0, 0.0, 0.9))))
            if label not in self.colors:
                try:
                    r,g,b,a = col
                    self.colors[label] = (float(r), float(g), float(b), float(a))
                except Exception:
                    pass
            poly = EditablePolygon(
                [(float(x), float(y)) for x, y in pts],
                color=self.colors.get(label, (1.0, 0.0, 0.0, 0.9)),
                label=label,
                on_changed=lambda _pts: self._refresh_lists(),
                on_drag_state=self._on_drag_state,
            )
            self.canvas._vb.addItem(poly)
            self.polygons.append(poly)

        # Boundary
        bnd = data.get("boundary")
        if bnd and bnd.get("points"):
            bpts = [(float(x), float(y)) for x, y in bnd["points"]]
            bpoly = EditablePolygon(
                bpts,
                color=(0.1, 0.7, 1.0, 0.9),
                label="boundary",
                on_changed=lambda _pts: self._refresh_lists(),
                on_drag_state=self._on_drag_state,
            )
            self._make_outline(bpoly)
            self.canvas._vb.addItem(bpoly)
            self.boundary = bpoly

        # Scale
        scl = data.get("scale")
        if scl and (scl.get("p1") and scl.get("p2")):
            try:
                p1 = tuple(map(float, scl.get("p1", [0.0, 0.0])))
                p2 = tuple(map(float, scl.get("p2", [0.0, 0.0])))
                value = float(scl.get("value", 1.0))
                unit = str(scl.get("unit", ""))

                def on_scale_changed(pts: List[Tuple[float, float]]) -> None:
                    if self.scale is not None and len(pts) >= 2:
                        self.scale.p1 = tuple(pts[0])
                        self.scale.p2 = tuple(pts[1])
                    if not self._drag_active:
                        self._refresh_lists()

                self.scale_item = EditablePolyline(
                    [p1, p2],
                    color=(0.0, 1.0, 0.0, 1.0),
                    width=2,
                    on_changed=on_scale_changed,
                    on_drag_state=self._on_drag_state,
                )
                self.canvas._vb.addItem(self.scale_item)
                self.scale = ScaleInfo(p1=p1, p2=p2, value=value, unit=unit)
            except Exception:
                pass

        # Measurements
        self.measure_items = []
        for m in (data.get("measurements") or []):
            p1 = tuple(map(float, (m.get("p1") or [0.0, 0.0])))
            p2 = tuple(map(float, (m.get("p2") or [0.0, 0.0])))
            def on_measure_changed(_pts: List[Tuple[float,float]]) -> None:
                if not self._drag_active:
                    self._refresh_lists()
            item = EditablePolyline(
                [p1, p2],
                color=(1.0, 0.5, 0.0, 1.0),
                width=2,
                on_changed=on_measure_changed,
                on_drag_state=self._on_drag_state,
            )
            self.canvas._vb.addItem(item)
            self.measure_items.append(item)

        self._log(f"Loaded annotations ← {Path(fname).name}")
        self._refresh_lists()

    # --------------- image + drawing ---------------
    def _on_load_image(self) -> None:
        p, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open image", str(Path.cwd()), "Images (*.tif *.tiff *.png *.jpg)"
        )
        if not p:
            return
        self.image_path = Path(p)
        prev, _scale, (H, W) = load_tiff_preview(self.image_path, max_side=4096)
        self.image_size = (H, W)
        self.base_img = prev
        self.canvas.set_image(prev, extent=(0, W, H, 0))
        self._log(f"Loaded {self.image_path.name} [{W}x{H}] preview")
        self._refresh_lists()

    def _on_add_label(self) -> None:
        text, ok = QtWidgets.QInputDialog.getText(self, "New label", "Label name:")
        if not ok or not text.strip():
            return
        name = text.strip()
        if name in self.labels:
            return
        self.labels.append(name)
        hue = (len(self.labels) * 0.17) % 1.0
        color = QtGui.QColor.fromHsvF(hue, 0.8, 0.9, 1.0)
        self.colors[name] = (color.redF(), color.greenF(), color.blueF(), 0.9)
        self.cmb_label.addItem(name)

    def _on_start_draw(self) -> None:
        if self.image_path is None:
            QtWidgets.QMessageBox.information(self, "No image", "Please open an image first.")
            return
        self._scaling = False
        self._measuring = False
        self._drawing_boundary = False
        self._drawing = True
        self._draw_pts = []
        self._clear_point_markers()
        self._clear_snap_ring()
        if self._draw_path_item is None:
            self._draw_path_item = QtWidgets.QGraphicsPathItem()
            pen = QtGui.QPen(QtCore.Qt.GlobalColor.cyan, 2)
            pen.setCosmetic(True)
            self._draw_path_item.setPen(pen)
            self._draw_path_item.setZValue(20)
            self.canvas._vb.addItem(self._draw_path_item)
        self._log("Drawing Region: left-click add point, right-click finish.")

    def _on_start_draw_boundary(self) -> None:
        if self.image_path is None:
            QtWidgets.QMessageBox.information(self, "No image", "Please open an image first.")
            return
        self._scaling = False
        self._measuring = False
        self._drawing = False
        self._drawing_boundary = True
        self._boundary_pts = []
        self._clear_point_markers()
        self._clear_snap_ring()
        if self._boundary_path_item is None:
            self._boundary_path_item = QtWidgets.QGraphicsPathItem()
            pen = QtGui.QPen(QtCore.Qt.GlobalColor.yellow, 2)
            pen.setCosmetic(True)
            self._boundary_path_item.setPen(pen)
            #self._boundary_path_item.setBrush(QtCore.Qt.NoBrush)
            self._boundary_path_item.setBrush(QtGui.QBrush(Qt.BrushStyle.NoBrush))
            self._boundary_path_item.setZValue(21)
            self.canvas._vb.addItem(self._boundary_path_item)
        self._log("Drawing Boundary: left-click add point, right-click finish.")

    def _on_finish_draw(self) -> None:
        if not self._drawing or len(self._draw_pts) < 3:
            self._drawing = False
            self._clear_temp_path()
            self._clear_point_markers()
            self._clear_snap_ring()
            return
        label = self.cmb_label.currentText()
        color = self.colors.get(label, (1.0, 0.0, 0.0, 0.9))
        poly = EditablePolygon(
            self._draw_pts,
            color=color,
            label=label,
            on_changed=lambda _pts: self._refresh_lists(),
            on_drag_state=self._on_drag_state,
        )
        self.canvas._vb.addItem(poly)
        self.polygons.append(poly)
        self._drawing = False
        self._clear_temp_path()
        self._clear_point_markers()
        self._clear_snap_ring()
        self._log(f"Added polygon ({label}) with {len(poly.handles)} vertices.")
        self._add_region_to_list(poly)

    def _finish_boundary(self) -> None:
        if not self._drawing_boundary or len(self._boundary_pts) < 3:
            self._drawing_boundary = False
            self._clear_boundary_temp_path()
            self._clear_point_markers()
            self._clear_snap_ring()
            return
        poly = EditablePolygon(
            self._boundary_pts,
            color=(0.1, 0.7, 1.0, 0.9),
            label="boundary",
            on_changed=lambda _pts: self._refresh_lists(),
            on_drag_state=self._on_drag_state,
        )
        self._make_outline(poly)
        if self.boundary is not None:
            self.canvas._vb.removeItem(self.boundary)
        self.canvas._vb.addItem(poly)
        self.boundary = poly
        self._drawing_boundary = False
        self._clear_boundary_temp_path()
        self._clear_point_markers()
        self._clear_snap_ring()
        self._log(f"Boundary added with {len(poly.handles)} vertices.")
        self._refresh_lists()

    def _on_cancel_draw(self) -> None:
        self._drawing = False
        self._drawing_boundary = False
        self._draw_pts = []
        self._boundary_pts = []
        self._clear_temp_path()
        self._clear_boundary_temp_path()
        self._clear_point_markers()
        self._clear_snap_ring()
        self._log("Drawing canceled.")

    def _on_set_scale(self) -> None:
        if self.image_path is None:
            QtWidgets.QMessageBox.information(self, "No image", "Please open an image first.")
            return
        self._drawing = False
        self._drawing_boundary = False
        self._measuring = False
        self._scaling = True
        self._scale_pts = []
        self._clear_scale_temp()
        self._log("Scale: left-click start, move to preview, left-click end; right-click to cancel.")

    def _on_start_measure(self) -> None:
        if self.image_path is None:
            QtWidgets.QMessageBox.information(self, "No image", "Please open an image first.")
            return
        self._drawing = False
        self._drawing_boundary = False
        self._scaling = False
        self._measuring = True
        self._measure_pts = []
        self._clear_measure_temp()
        self._log("Measure: left-click start, move to preview, left-click end; right-click to cancel.")

    def _clear_temp_path(self) -> None:
        if self._draw_path_item is not None:
            self.canvas._vb.removeItem(self._draw_path_item)
            self._draw_path_item = None

    def _clear_boundary_temp_path(self) -> None:
        if self._boundary_path_item is not None:
            self.canvas._vb.removeItem(self._boundary_path_item)
            self._boundary_path_item = None

    # --------------- Input handling ---------------
    def _on_scene_click(self, ev: Any) -> None:
        # If clicking a handle, let it process events
        try:
            items = self.canvas._glw.scene().items(ev.scenePos())
            for it in items:
                cur = it
                while cur is not None:
                    if isinstance(cur, VertexHandle):
                        return
                    cur = cur.parentItem()
        except Exception:
            pass

        # Scaling
        if self._scaling:
            if ev.button() == QtCore.Qt.MouseButton.RightButton:
                self._scaling = False
                self._scale_pts = []
                self._clear_scale_temp()
                self._log("Scale canceled.")
                return
            if ev.button() == QtCore.Qt.MouseButton.LeftButton:
                v = self.canvas._vb.mapSceneToView(ev.scenePos())
                pt = (v.x(), v.y())
                self._scale_pts.append(pt)
                self._add_scale_point_marker(pt)
                if len(self._scale_pts) == 2:
                    dlg = ScaleDialog(self)
                    got = dlg.get()
                    if not got:
                        self._scaling = False
                        self._scale_pts = []
                        self._clear_scale_temp()
                        return
                    value, unit = got
                    if self.scale_item is not None:
                        self.canvas._vb.removeItem(self.scale_item)
                        self.scale_item = None

                    def on_scale_changed(pts: List[Tuple[float, float]]) -> None:
                        if self.scale is not None and len(pts) >= 2:
                            self.scale.p1 = tuple(pts[0])
                            self.scale.p2 = tuple(pts[1])
                        if not self._drag_active:
                            self._refresh_lists()

                    self.scale_item = EditablePolyline(
                        self._scale_pts,
                        color=(0.0, 1.0, 0.0, 1.0),
                        width=2,
                        on_changed=on_scale_changed,
                        on_drag_state=self._on_drag_state,
                    )
                    self.canvas._vb.addItem(self.scale_item)
                    self.scale = ScaleInfo(
                        p1=self._scale_pts[0], p2=self._scale_pts[1], value=float(value), unit=str(unit)
                    )
                    self._log(f"Scale set: {value} {unit}")
                    self._scaling = False
                    self._scale_pts = []
                    self._clear_scale_temp()
                    self._refresh_lists()
                else:
                    self._update_scale_temp()
                return

        # Measuring
        if self._measuring:
            if ev.button() == QtCore.Qt.MouseButton.RightButton:
                self._measuring = False
                self._measure_pts = []
                self._clear_measure_temp()
                self._log("Measurement canceled.")
                return
            if ev.button() == QtCore.Qt.MouseButton.LeftButton:
                v = self.canvas._vb.mapSceneToView(ev.scenePos())
                pt = (v.x(), v.y())
                self._measure_pts.append(pt)
                self._add_measure_point_marker(pt)
                if len(self._measure_pts) == 2:
                    def on_measure_changed(_pts: List[Tuple[float, float]]) -> None:
                        if not self._drag_active:
                            self._refresh_lists()
                    item = EditablePolyline(
                        self._measure_pts,
                        color=(1.0, 0.5, 0.0, 1.0),
                        width=2,
                        on_changed=on_measure_changed,
                        on_drag_state=self._on_drag_state,
                    )
                    self.canvas._vb.addItem(item)
                    self.measure_items.append(item)
                    self._measuring = False
                    self._measure_pts = []
                    self._clear_measure_temp()
                    self._refresh_lists()
                else:
                    self._update_measure_temp()
                return

        # Region / Boundary drawing
        if not (self._drawing or self._drawing_boundary):
            return
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            pos = ev.scenePos()
            v = self.canvas._vb.mapSceneToView(pos)
            pt = (v.x(), v.y())
            if self._drawing:
                if self._near_first_point(pt, pixels=10) and len(self._draw_pts) >= 3:
                    self._on_finish_draw()
                    return
                self._draw_pts.append(pt)
                self._add_point_marker(pt)
                self._update_temp_path()
                if len(self._draw_pts) == 1:
                    self._ensure_snap_ring(self._draw_pts[0])
                    self._update_snap_ring(True)
            else:
                first = self._boundary_pts[0] if self._boundary_pts else None

                def near(a, b):
                    if a is None or b is None:
                        return False
                    thr = self._view_snap_threshold(10)
                    dx = a[0] - b[0]
                    dy = a[1] - b[1]
                    return math.hypot(dx, dy) <= thr

                if near(first, pt) and len(self._boundary_pts) >= 3:
                    self._finish_boundary()
                    return
                self._boundary_pts.append(pt)
                self._add_point_marker(pt)
                self._update_boundary_temp_path()
                if len(self._boundary_pts) == 1 and self._boundary_pts[0]:
                    self._ensure_snap_ring(self._boundary_pts[0])
                    self._update_snap_ring(True)
        elif ev.button() == QtCore.Qt.MouseButton.RightButton:
            if self._drawing:
                self._on_finish_draw()
            elif self._drawing_boundary:
                self._finish_boundary()

    def _on_scene_move(self, pos: 'QtCore.QPointF') -> None:
        if self._scaling:
            v = self.canvas._vb.mapSceneToView(pos)
            cur = (v.x(), v.y())
            self._update_scale_temp(cursor=cur)
            return
        if self._measuring:
            v = self.canvas._vb.mapSceneToView(pos)
            cur = (v.x(), v.y())
            self._update_measure_temp(cursor=cur)
            return
        if self._drawing and self._draw_path_item is not None:
            v = self.canvas._vb.mapSceneToView(pos)
            cur = (v.x(), v.y())
            snap = self._near_first_point(cur, pixels=10) and len(self._draw_pts) >= 2
            if self._draw_pts:
                self._ensure_snap_ring(self._draw_pts[0])
                self._update_snap_ring(True)
            pen = QtGui.QPen(QtCore.Qt.GlobalColor.magenta if snap else QtCore.Qt.GlobalColor.cyan, 2)
            pen.setCosmetic(True)
            self._draw_path_item.setPen(pen)
            if snap:
                cur = self._draw_pts[0]
            self._update_temp_path(cursor=cur)
            return
        if self._drawing_boundary and self._boundary_path_item is not None:
            v = self.canvas._vb.mapSceneToView(pos)
            cur = (v.x(), v.y())

            def near(a, b):
                if a is None or b is None:
                    return False
                thr = self._view_snap_threshold(10)
                return math.hypot(a[0] - b[0], a[1] - b[1]) <= thr

            first = self._boundary_pts[0] if self._boundary_pts else None
            snap = near(first, cur) and len(self._boundary_pts) >= 2
            if first is not None:
                self._ensure_snap_ring(first)
                self._update_snap_ring(True)
            pen = QtGui.QPen(QtCore.Qt.GlobalColor.magenta if snap else QtCore.Qt.GlobalColor.yellow, 2)
            pen.setCosmetic(True)
            self._boundary_path_item.setPen(pen)
            if snap and first is not None:
                cur = first
            self._update_boundary_temp_path(cursor=cur)
            return

    def _update_temp_path(self, cursor: tuple[float, float] | None = None) -> None:
        if self._draw_path_item is None:
            return
        path = QtGui.QPainterPath()
        pts = list(self._draw_pts)
        if cursor is not None:
            pts = pts + [cursor]
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
        self._draw_path_item.setPath(path)

    def _update_boundary_temp_path(self, cursor: tuple[float, float] | None = None) -> None:
        if self._boundary_path_item is None:
            return
        path = QtGui.QPainterPath()
        pts = list(self._boundary_pts)
        if cursor is not None:
            pts = pts + [cursor]
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
        self._boundary_path_item.setPath(path)

    # --------------- Point markers for Region/Boundary drawing ---------------
    def _add_point_marker(self, pt: tuple[float, float]) -> None:
        """Add a small visual dot at a click location while drawing."""
        r = 3.5
        dot = QtWidgets.QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
        dot.setPos(pt[0], pt[1])
        # Blue marker works for both Region and Boundary drawing modes
        dot.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.blue))
        pen = QtGui.QPen(QtCore.Qt.GlobalColor.black, 1)
        pen.setCosmetic(True)
        dot.setPen(pen)
        dot.setZValue(26)
        self.canvas._vb.addItem(dot)
        self._draw_point_markers.append(dot)

    def _clear_point_markers(self) -> None:
        """Remove any temporary point markers shown during drawing."""
        for m in self._draw_point_markers:
            try:
                self.canvas._vb.removeItem(m)
            except Exception:
                pass
        self._draw_point_markers.clear()

    # --------------- List & selection ---------------
    def _add_region_to_list(self, poly: EditablePolygon) -> None:
        idx = len(self.polygons) - 1
        item = QtWidgets.QListWidgetItem(f"{idx + 1}: {poly.label} ({len(poly.handles)} pts)")
        self.list_regions.addItem(item)
        self.list_regions.setCurrentItem(item)

    def _refresh_lists(self) -> None:
        if self._drag_active:
            return
        self.list_regions.clear()
        for i, poly in enumerate(self.polygons):
            self.list_regions.addItem(f"{i + 1}: {poly.label} ({len(poly.handles)} pts)")
        self.list_boundary.clear()
        if self.boundary is not None:
            self.list_boundary.addItem(f"Boundary ({len(self.boundary.handles)} pts)")
        self.list_scale.clear()
        if self.scale is not None:
            self.list_scale.addItem(f"{self._scale_pixels_length():.1f}px — {self.scale.value:g} {self.scale.unit}")
        # Measurements
        self.list_measure.clear()
        u_per_px = self._units_per_pixel()
        for i, it in enumerate(self.measure_items):
            pts = it.to_points()
            px = 0.0
            if len(pts) >= 2:
                dx = pts[1][0] - pts[0][0]
                dy = pts[1][1] - pts[0][1]
                px = (dx*dx + dy*dy) ** 0.5
            if u_per_px is None:
                self.list_measure.addItem(f"{i+1}: {px:.1f}px — set Scale")
            else:
                val = px * u_per_px
                self.list_measure.addItem(f"{i+1}: {px:.1f}px — {val:g} {self.scale.unit}")

    def _on_select_region(self, row: int) -> None:
        self._clear_all_highlights()
        if 0 <= row < len(self.polygons):
            poly = self.polygons[row]
            self._set_item_highlight(poly, True)
            poly.show_handles(True)

    def _on_select_boundary(self) -> None:
        self._clear_all_highlights()
        if self.boundary is not None and self.list_boundary.currentRow() == 0:
            self._set_item_highlight(self.boundary, True)
            self.boundary.show_handles(True)

    def _on_select_scale(self) -> None:
        self._clear_all_highlights()
        if self.scale_item is not None and self.list_scale.currentRow() == 0:
            self._set_item_highlight(self.scale_item, True)
            self.scale_item.show_handles(True)

    def _on_select_measure(self) -> None:
        self._clear_all_highlights()
        row = self.list_measure.currentRow()
        if 0 <= row < len(self.measure_items):
            it = self.measure_items[row]
            self._set_item_highlight(it, True)
            it.show_handles(True)

    # --------------- Delete ---------------
    def _on_delete_selected_region(self) -> None:
        row = self.list_regions.currentRow()
        if 0 <= row < len(self.polygons):
            poly = self.polygons.pop(row)
            self.canvas._vb.removeItem(poly)
            self._refresh_lists()

    def _on_delete_boundary(self) -> None:
        if self.boundary is not None:
            self.canvas._vb.removeItem(self.boundary)
            self.boundary = None
            self._refresh_lists()

    def _on_delete_scale(self) -> None:
        self.scale = None
        if self.scale_item is not None:
            self.canvas._vb.removeItem(self.scale_item)
            self.scale_item = None
        self._refresh_lists()

    def _on_delete_measure(self) -> None:
        row = self.list_measure.currentRow()
        if 0 <= row < len(self.measure_items):
            it = self.measure_items.pop(row)
            self.canvas._vb.removeItem(it)
            self._refresh_lists()

    # --------------- Scale & Measure temp ---------------
    def _add_scale_point_marker(self, pt: tuple[float, float]) -> None:
        r = 3.5
        dot = QtWidgets.QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
        dot.setPos(pt[0], pt[1])
        dot.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.red))
        pen = QtGui.QPen(QtCore.Qt.GlobalColor.black, 1)
        pen.setCosmetic(True)
        dot.setPen(pen)
        dot.setZValue(26)
        self.canvas._vb.addItem(dot)
        self._scale_point_markers.append(dot)

    def _update_scale_temp(self, cursor: Optional[tuple[float, float]] = None) -> None:
        if not self._scaling:
            return
        if self._scale_temp_item is None:
            self._scale_temp_item = QtWidgets.QGraphicsPathItem()
            pen = QtGui.QPen(QtCore.Qt.GlobalColor.red, 2)
            pen.setCosmetic(True)
            self._scale_temp_item.setPen(pen)
            self._scale_temp_item.setZValue(25)
            self.canvas._vb.addItem(self._scale_temp_item)
        path = QtGui.QPainterPath()
        pts = list(self._scale_pts)
        if cursor is not None:
            pts = pts + [cursor]
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
        self._scale_temp_item.setPath(path)

    def _clear_scale_temp(self) -> None:
        if self._scale_temp_item is not None:
            self.canvas._vb.removeItem(self._scale_temp_item)
            self._scale_temp_item = None
        for m in self._scale_point_markers:
            self.canvas._vb.removeItem(m)
        self._scale_point_markers.clear()

    # Measure temp helpers
    def _add_measure_point_marker(self, pt: tuple[float, float]) -> None:
        r = 3.5
        dot = QtWidgets.QGraphicsEllipseItem(-r, -r, 2 * r, 2 * r)
        dot.setPos(pt[0], pt[1])
        dot.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.green))
        pen = QtGui.QPen(QtCore.Qt.GlobalColor.black, 1)
        pen.setCosmetic(True)
        dot.setPen(pen)
        dot.setZValue(26)
        self.canvas._vb.addItem(dot)
        self._measure_point_markers.append(dot)

    def _update_measure_temp(self, cursor: Optional[tuple[float, float]] = None) -> None:
        if not self._measuring:
            return
        if self._measure_temp_item is None:
            self._measure_temp_item = QtWidgets.QGraphicsPathItem()
            pen = QtGui.QPen(QtCore.Qt.GlobalColor.green, 2)
            pen.setCosmetic(True)
            self._measure_temp_item.setPen(pen)
            self._measure_temp_item.setZValue(25)
            self.canvas._vb.addItem(self._measure_temp_item)
        path = QtGui.QPainterPath()
        pts = list(self._measure_pts)
        if cursor is not None:
            pts = pts + [cursor]
        if pts:
            path.moveTo(pts[0][0], pts[0][1])
            for x, y in pts[1:]:
                path.lineTo(x, y)
        self._measure_temp_item.setPath(path)

    def _clear_measure_temp(self) -> None:
        if self._measure_temp_item is not None:
            self.canvas._vb.removeItem(self._measure_temp_item)
            self._measure_temp_item = None
        for m in self._measure_point_markers:
            self.canvas._vb.removeItem(m)
        self._measure_point_markers.clear()
