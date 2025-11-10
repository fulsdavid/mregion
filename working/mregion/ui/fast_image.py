# mregion/ui/fast_image.py
from __future__ import annotations

from typing import List, Tuple, Optional
from PyQt6 import QtCore, QtGui, QtWidgets

try:
    import pyqtgraph as pg
    HAVE_PG = True
except Exception:
    HAVE_PG = False
    pg = None  # type: ignore

class FastImageCanvas(QtWidgets.QWidget):
    """Fast image viewer using PyQtGraph."""

    view_changed = QtCore.pyqtSignal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        if not HAVE_PG:
            raise RuntimeError("pyqtgraph is required for FastImageCanvas. Install with: pip install pyqtgraph")

        pg.setConfigOptions(useOpenGL=True, enableExperimental=True, antialias=False)
        self.setLayout(QtWidgets.QVBoxLayout())
        self._glw = pg.GraphicsLayoutWidget()
        self._vb = self._glw.addViewBox(lockAspect=True, enableMenu=False)
        self._vb.invertY(True)
        self._vb.setMouseEnabled(x=True, y=True)
        self._img = pg.ImageItem(axisOrder='row-major')
        self._img.setAutoDownsample(True)
        self._vb.addItem(self._img)

        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._glw)

        self._polys: List[QtWidgets.QGraphicsPathItem] = []
        self._W = 0
        self._H = 0

        self._vb.sigRangeChanged.connect(lambda *_: self.view_changed.emit())

    def set_image(self, arr, extent: Tuple[float, float, float, float] | None = None) -> None:
        """Display an image array. Accepts uint8 or float arrays; coerces to uint8."""
        import numpy as np
        if np.issubdtype(arr.dtype, np.floating):
            a = arr
            try:
                amax = float(np.nanmax(a))
            except Exception:
                amax = 1.0
            if amax <= 1.0:
                arr = (np.clip(a, 0.0, 1.0) * 255.0).astype(np.uint8)
            else:
                arr = np.clip(a, 0.0, 255.0).astype(np.uint8)
        elif arr.dtype != np.uint8:
            arr = arr.astype(np.uint8, copy=False)

        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        if arr.ndim == 3 and arr.shape[2] > 3:
            arr = arr[:, :, :3]
        if not arr.flags.c_contiguous:
            arr = np.ascontiguousarray(arr)

        self._H, self._W = int(arr.shape[0]), int(arr.shape[1])
        self._img.setImage(arr, autoLevels=False, levels=(0, 255))
        if extent is None:
            self._vb.setRange(xRange=(0, self._W), yRange=(0, self._H), padding=0.0)
        else:
            x0, x1, y1, y0 = extent
            self._vb.setRange(xRange=(x0, x1), yRange=(y0, y1), padding=0.0)

    def set_limits(self, W: int, H: int) -> None:
        self._W, self._H = int(W), int(H)
        self._vb.setRange(xRange=(0, self._W), yRange=(0, self._H), padding=0.0)

    def clear_overlays(self) -> None:
        for it in self._polys:
            it.setParentItem(None)
            self._vb.removeItem(it)
        self._polys.clear()

    def add_polygon(self, points: List[Tuple[float, float]], color_rgba=(1.0, 0.0, 0.0, 0.8), width: int = 2) -> QtWidgets.QGraphicsPathItem:
        path = QtGui.QPainterPath()
        if points:
            path.moveTo(points[0][0], points[0][1])
            for x, y in points[1:]:
                path.lineTo(x, y)
            path.closeSubpath()
        item = QtWidgets.QGraphicsPathItem(path)
        r, g, b, a = color_rgba
        pen = QtGui.QPen(QtGui.QColor.fromRgbF(r, g, b, a), width)
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setBrush(QtGui.QBrush(QtGui.QColor.fromRgbF(r, g, b, max(0.0, min(0.4, a*0.5)))))
        self._vb.addItem(item)
        self._polys.append(item)
        return item

    def make_toolbar(self, parent: Optional[QtWidgets.QWidget] = None) -> QtWidgets.QWidget:
        bar = QtWidgets.QToolBar(parent)
        act_fit = bar.addAction("Fit")
        act_reset = bar.addAction("Reset")
        act_zoom_in = bar.addAction("Zoom+")
        act_zoom_out = bar.addAction("Zoom-")

        def fit():
            self._vb.autoRange(items=[self._img])

        def reset():
            self._vb.setRange(xRange=(0, self._W), yRange=(0, self._H), padding=0.0)

        def zoom(factor: float):
            xr = self._vb.viewRange()[0]
            yr = self._vb.viewRange()[1]
            cx = (xr[0] + xr[1]) * 0.5
            cy = (yr[0] + yr[1]) * 0.5
            w = (xr[1] - xr[0]) * factor
            h = (yr[1] - yr[0]) * factor
            self._vb.setRange(xRange=(cx - w/2, cx + w/2), yRange=(cy - h/2, cy + h/2), padding=0.0)

        act_fit.triggered.connect(fit)
        act_reset.triggered.connect(reset)
        act_zoom_in.triggered.connect(lambda: zoom(0.8))
        act_zoom_out.triggered.connect(lambda: zoom(1.25))
        return bar
