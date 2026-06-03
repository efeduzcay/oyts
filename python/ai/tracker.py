"""IoU tabanlı hafif çoklu hedef takipçisi.

YOLOv8 her karede bağımsız bbox'lar çıkartır; titreme önlemek ve "kararlı
hedef" kararı vermek için karelerin arasında basit bir eşleştirme yaparız.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Track:
    track_id: int
    bbox: Tuple[int, int, int, int]   # x1,y1,x2,y2
    label: str
    conf: float
    hits: int = 1
    missed: int = 0
    age: int = 0

    @property
    def cx(self) -> int:
        return (self.bbox[0] + self.bbox[2]) // 2

    @property
    def cy(self) -> int:
        return (self.bbox[1] + self.bbox[3]) // 2

    @property
    def area(self) -> int:
        return max(0, (self.bbox[2] - self.bbox[0])) * \
               max(0, (self.bbox[3] - self.bbox[1]))


def _iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    a_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    b_area = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = a_area + b_area - inter
    return inter / union if union > 0 else 0.0


class IoUTracker:
    def __init__(self,
                 iou_threshold: float = 0.30,
                 max_missed: int = 10,
                 min_hits: int = 3,
                 stable_grace_frames: int = 2):
        """IoU-based multi-target tracker.

        Args:
            iou_threshold: minimum IoU to associate a detection with a track.
            max_missed: drop a track after this many consecutive missed frames.
            min_hits: minimum total hits before a track is considered stable.
            stable_grace_frames: a stable track stays "stable" for this many
                missed frames before being demoted. Smoothes brief detection
                gaps so the decision FSM doesn't oscillate.
        """
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.min_hits = min_hits
        self.stable_grace_frames = max(0, stable_grace_frames)
        self._tracks: List[Track] = []
        self._next_id = 1

    def update(self, detections: List[Tuple[Tuple[int, int, int, int], str, float]]
               ) -> List[Track]:
        """detections = [(bbox, label, conf), ...]. Geri stable track listesi.

        Stable = `hits >= min_hits` AND `missed <= stable_grace_frames`.
        Brief detection gaps (≤ grace frames) keep the target visible so the
        decision FSM doesn't flap between SEARCHING and APPROACHING.
        """
        # Greedy IoU eşleştirme
        unmatched_dets = list(range(len(detections)))
        for trk in self._tracks:
            best_iou, best_j = 0.0, -1
            for j in unmatched_dets:
                bbox, label, _ = detections[j]
                if label != trk.label:
                    continue
                iou = _iou(trk.bbox, bbox)
                if iou > best_iou:
                    best_iou, best_j = iou, j
            if best_iou >= self.iou_threshold and best_j >= 0:
                bbox, label, conf = detections[best_j]
                trk.bbox = bbox
                trk.conf = conf
                trk.hits += 1
                trk.missed = 0
                trk.age += 1
                unmatched_dets.remove(best_j)
            else:
                trk.missed += 1
                trk.age += 1

        # Yeni track'lar
        for j in unmatched_dets:
            bbox, label, conf = detections[j]
            self._tracks.append(Track(
                track_id=self._next_id, bbox=bbox, label=label, conf=conf
            ))
            self._next_id += 1

        # Eskimişleri at
        self._tracks = [t for t in self._tracks if t.missed <= self.max_missed]

        # Stable olanları dön — kısa missed gap'lerinde target görünmeye devam eder
        return [
            t for t in self._tracks
            if t.hits >= self.min_hits and t.missed <= self.stable_grace_frames
        ]

    def reset(self) -> None:
        """Forget all tracks. Useful when the camera source switches."""
        self._tracks.clear()
