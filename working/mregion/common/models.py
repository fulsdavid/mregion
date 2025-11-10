# mregion/common/models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

@dataclass
class RegionPolygon:
    label: str
    points: List[Tuple[float, float]]
    color: Tuple[float, float, float, float]

@dataclass
class ScaleInfo:
    p1: Tuple[float, float]
    p2: Tuple[float, float]
    value: float
    unit: str

@dataclass
class RegionFile:
    image_path: str
    image_sha256: str
    image_size: Tuple[int, int]
    app_version: str
    created_at: str
    labels: List[str]
    polygons: List[RegionPolygon]

    def to_json(self) -> Dict[str, Any]:
        return {
            "image_path": self.image_path,
            "image_sha256": self.image_sha256,
            "image_size": self.image_size,
            "app_version": self.app_version,
            "created_at": self.created_at,
            "labels": self.labels,
            "polygons": [
                {"label": p.label, "points": p.points, "color": p.color}
                for p in self.polygons
            ],
        }

    @staticmethod
    def from_json(d: Dict[str, Any]) -> "RegionFile":
        polys = [
            RegionPolygon(
                label=p["label"],
                points=[tuple(map(float, xy)) for xy in p["points"]],
                color=tuple(map(float, p.get("color", (1, 0, 0, 0.4)))),
            )
            for p in d.get("polygons", [])
        ]
        return RegionFile(
            image_path=d["image_path"],
            image_sha256=d.get("image_sha256", ""),
            image_size=tuple(d["image_size"]),
            app_version=d.get("app_version", "unknown"),
            created_at=d.get("created_at", ""),
            labels=list(d.get("labels", [])),
            polygons=polys,
        )
