"""
utils/dashboard.py — Modern analiz paneli (right-side dashboard)
================================================================
pc_vision_controller'ın yanına eklenir; canlı analitik gösterir:

  * STATE rozeti (renkli durum makinesi)
  * Fuzzy üyelik çubukları (SMALL/MEDIUM/LARGE/HUGE)
  * Öncelik göstergesi (primary target priority)
  * Tespit listesi (label, conf, track_id)
  * Telemetri (heat thermometer, voltage bar)
  * Area trend sparkline
  * Anlık komut paneli

API:
    dash = Dashboard(width=340)
    panel = dash.render(height, ctx)   # ctx: DashboardContext
    canvas = np.hstack([frame, panel])
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np


# Tema
BG          = (18, 18, 22)        # panel arka plan (koyu kömür)
CARD        = (28, 30, 36)        # kart arka planı
CARD_EDGE   = (55, 60, 70)        # kart kenarı
TEXT        = (235, 235, 240)     # birincil yazı
TEXT_DIM    = (150, 155, 165)     # ikincil yazı
TEXT_FAINT  = (95, 100, 110)      # üçüncül yazı
ACCENT      = (255, 200, 90)      # vurgu (amber)
OK          = (110, 220, 130)     # yeşil
WARN        = (90, 180, 255)      # turuncu/amber (BGR'de mavi-turuncu karışım)
DANGER      = (75, 75, 240)       # kırmızı
INFO        = (235, 195, 90)      # cyan-ish

STATE_TINT = {
    "SEARCHING":   (230, 190, 70),
    "APPROACHING": (110, 220, 130),
    "TOO_CLOSE":   (75, 75, 240),
    "HEAT_ACTION": (40, 60, 240),
    "MANUAL":      (220, 130, 240),
}


# Veri konteyneri
@dataclass
class DashboardContext:
    state: str = "SEARCHING"
    fps: float = 0.0
    cmd: str = "X"
    spd: int = 0
    heat_c: float = 25.0
    voltage: float = 0.0
    heat_threshold: float = 60.0
    voltage_nominal: float = 11.1
    voltage_min: float = 9.6
    targets: List = field(default_factory=list)      # stable track listesi
    raw_count: int = 0                                # ham YOLO tespit sayısı
    raw_max_conf: float = 0.0                         # ham en yüksek conf
    conf_threshold: float = 0.25
    memberships: Dict[str, float] = field(default_factory=dict)
    primary_priority: float = 0.0
    primary_area: float = 0.0
    area_stop: float = 25000.0
    area_history: deque = field(default_factory=lambda: deque(maxlen=120))
    sim_mode: bool = True
    recording: bool = False
    mode_label: str = "WEBCAM"


# Yardımcılar
def _put(img, text, org, scale=0.45, color=TEXT, thick=1,
         font=cv2.FONT_HERSHEY_SIMPLEX):
    cv2.putText(img, text, org, font, scale, color, thick, cv2.LINE_AA)


def _put_bold(img, text, org, scale=0.5, color=TEXT, thick=1):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_DUPLEX, scale, color,
                thick, cv2.LINE_AA)


def _filled(img, p1, p2, color):
    cv2.rectangle(img, p1, p2, color, -1)


def _rounded_card(img, x, y, w, h, title=None):
    p1, p2 = (x, y), (x + w, y + h)
    _filled(img, p1, p2, CARD)
    cv2.rectangle(img, p1, p2, CARD_EDGE, 1, cv2.LINE_AA)
    if title:
        _put(img, title.upper(), (x + 10, y + 16), 0.42, TEXT_DIM, 1)
        cv2.line(img, (x + 10, y + 22), (x + w - 10, y + 22), CARD_EDGE, 1)


def _bar(img, x, y, w, h, value: float, color, bg=(45, 48, 55)):
    """value 0..1"""
    value = max(0.0, min(1.0, value))
    _filled(img, (x, y), (x + w, y + h), bg)
    fill_w = int(w * value)
    if fill_w > 0:
        _filled(img, (x, y), (x + fill_w, y + h), color)


def _lerp_color(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# Dashboard
class Dashboard:
    def __init__(self, width: int = 340, pad: int = 12):
        self.W = width
        self.pad = pad
        self._pulse = 0.0

    # ana render
    def render(self, frame_height: int, ctx: DashboardContext) -> np.ndarray:
        self._pulse = (self._pulse + 0.08) % (2 * math.pi)
        H = frame_height
        panel = np.full((H, self.W, 3), BG, dtype=np.uint8)

        y = self.pad
        y = self._draw_header(panel, y, ctx)
        y = self._draw_state_badge(panel, y, ctx)
        y = self._draw_priority(panel, y, ctx)
        y = self._draw_fuzzy(panel, y, ctx)
        y = self._draw_detections(panel, y, ctx)
        y = self._draw_sparkline(panel, y, ctx)
        y = self._draw_telemetry(panel, y, ctx)
        y = self._draw_command(panel, y, ctx)
        self._draw_footer(panel, ctx)
        return panel

    # Header
    def _draw_header(self, img, y, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        # Logo bar
        cv2.rectangle(img, (x, y), (x + w, y + 36), CARD, -1)
        cv2.rectangle(img, (x, y), (x + 4, y + 36), ACCENT, -1)
        _put_bold(img, "FIRE-SENTINEL", (x + 14, y + 17), 0.55, TEXT, 1)
        _put(img, "v3.0  •  YOLOv8 + Fuzzy + SA", (x + 14, y + 31),
             0.38, TEXT_FAINT)
        mode_color = OK if ctx.sim_mode else DANGER
        _put(img, ctx.mode_label, (x + w - 70, y + 22), 0.42, mode_color, 1)
        # REC noktası
        if ctx.recording:
            r_alpha = 0.5 + 0.5 * math.sin(self._pulse * 4)
            col = (int(40 * r_alpha + 40), int(40 * r_alpha + 40),
                   int(255 * r_alpha + 0))
            cv2.circle(img, (x + w - 14, y + 13), 5, col, -1)
        return y + 36 + 8

    # State Badge
    def _draw_state_badge(self, img, y, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        h = 56
        _rounded_card(img, x, y, w, h)
        tint = STATE_TINT.get(ctx.state, TEXT_DIM)
        # Yan göstergeçubuk (state rengi)
        _filled(img, (x + 1, y + 1), (x + 6, y + h - 1), tint)
        _put(img, "ROBOT STATE", (x + 14, y + 18), 0.40, TEXT_DIM)
        _put_bold(img, ctx.state, (x + 14, y + 42), 0.7, tint, 1)
        # FPS sağ üst
        _put(img, f"{ctx.fps:5.1f} fps", (x + w - 70, y + 18),
             0.42, TEXT_DIM)
        # Nabız animasyonu
        pulse_x = x + w - 18
        pulse_y = y + 38
        r = int(4 + 2 * (0.5 + 0.5 * math.sin(self._pulse * 3)))
        cv2.circle(img, (pulse_x, pulse_y), r, tint, -1)
        cv2.circle(img, (pulse_x, pulse_y), r + 2, tint, 1)
        return y + h + 8

    # Priority Gauge
    def _draw_priority(self, img, y, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        h = 72
        _rounded_card(img, x, y, w, h, "PRIMARY PRIORITY")
        p = ctx.primary_priority
        # Renk priority'ye göre OK→AMBER→DANGER
        if p < 0.4:
            color = OK
        elif p < 0.75:
            color = ACCENT
        else:
            color = DANGER
        # Büyük sayı
        _put_bold(img, f"{p:.2f}", (x + 14, y + 55), 1.1, color, 2)
        # Yan bilgi
        if ctx.targets:
            primary_label = ctx.targets[0].label.upper()
            _put(img, primary_label, (x + 110, y + 42), 0.45, TEXT, 1)
            close_ratio = min(1.0, ctx.primary_area / max(1.0, ctx.area_stop))
            _put(img, f"area: {int(ctx.primary_area):>6}",
                 (x + 110, y + 58), 0.40, TEXT_DIM)
            # Yaklaşma çubuğu
            _bar(img, x + 14, y + 62, w - 28, 4, close_ratio,
                 _lerp_color(OK, DANGER, close_ratio))
        else:
            _put(img, "no target", (x + 110, y + 50), 0.45, TEXT_FAINT, 1)
        return y + h + 8

    # Fuzzy Membership
    def _draw_fuzzy(self, img, y, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        rows = ["SMALL", "MEDIUM", "LARGE", "HUGE"]
        h = 28 + len(rows) * 18 + 8
        _rounded_card(img, x, y, w, h, "FUZZY  μ(area)")
        row_y = y + 36
        bar_x = x + 78
        bar_w = w - 78 - 50
        for label in rows:
            mu = float(ctx.memberships.get(label, 0.0))
            mu = max(0.0, min(1.0, mu))
            color = _lerp_color(TEXT_FAINT, ACCENT, mu)
            if mu > 0.6:
                color = OK
            _put(img, label, (x + 12, row_y + 9), 0.42, TEXT, 1)
            _bar(img, bar_x, row_y, bar_w, 10, mu, color)
            _put(img, f"{mu:.2f}", (bar_x + bar_w + 6, row_y + 9),
                 0.40, TEXT_DIM)
            row_y += 18
        return y + h + 8

    # Detections
    def _draw_detections(self, img, y, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        max_rows = 3
        rows = ctx.targets[:max_rows] if ctx.targets else []
        h = 50 + max(1, len(rows)) * 18 + 10
        title = f"DETECTIONS  raw:{ctx.raw_count}  stable:{len(ctx.targets)}"
        _rounded_card(img, x, y, w, h, title)
        # Raw conf göstergesi (modelin gördüğü en güçlü tespit)
        raw_y = y + 30
        raw_col = OK if ctx.raw_max_conf >= ctx.conf_threshold else TEXT_FAINT
        _put(img, "max raw conf", (x + 12, raw_y + 9), 0.40, TEXT_DIM)
        _bar(img, x + 110, raw_y + 1, w - 160, 9,
             ctx.raw_max_conf, raw_col)
        _put(img, f"{ctx.raw_max_conf:.2f}",
             (x + w - 42, raw_y + 9), 0.40, TEXT, 1)
        # threshold ip işareti
        thr_x = x + 110 + int((w - 160) * ctx.conf_threshold)
        cv2.line(img, (thr_x, raw_y - 1), (thr_x, raw_y + 11),
                 ACCENT, 1, cv2.LINE_AA)
        row_y = y + 50
        if not rows:
            msg = ("model görüyor, henüz stable değil"
                   if ctx.raw_count > 0
                   else "— no detections —")
            _put(img, msg, (x + 14, row_y + 9), 0.40, TEXT_FAINT)
        else:
            for i, t in enumerate(rows):
                tag = "★" if i == 0 else f"#{i+1}"
                row_color = DANGER if "fire" in t.label.lower() else ACCENT
                _put_bold(img, tag, (x + 12, row_y + 10), 0.45,
                          row_color, 1)
                _put(img, f"{t.label.upper():<6}",
                     (x + 38, row_y + 10), 0.42, TEXT, 1)
                _put(img, f"id:{t.track_id:<3}",
                     (x + 110, row_y + 10), 0.40, TEXT_DIM)
                # confidence mini-bar
                _bar(img, x + 160, row_y + 2, w - 175, 10, t.conf,
                     _lerp_color(TEXT_FAINT, OK, t.conf))
                _put(img, f"{t.conf:.2f}",
                     (x + w - 38, row_y + 10), 0.38, TEXT_DIM)
                row_y += 18
        return y + h + 8

    # Sparkline
    def _draw_sparkline(self, img, y, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        h = 60
        _rounded_card(img, x, y, w, h, "AREA TREND (last 120 frames)")
        plot_x = x + 12
        plot_y = y + 28
        plot_w = w - 24
        plot_h = h - 36
        hist = list(ctx.area_history)
        if len(hist) >= 2:
            m = max(max(hist), ctx.area_stop, 1.0)
            pts = []
            n = len(hist)
            for i, v in enumerate(hist):
                px = plot_x + int(i * (plot_w - 1) / max(1, n - 1))
                py = plot_y + plot_h - int((v / m) * plot_h)
                pts.append((px, py))
            # stop threshold çizgisi
            stop_y = plot_y + plot_h - int(
                (ctx.area_stop / m) * plot_h)
            if 0 <= stop_y - plot_y <= plot_h:
                cv2.line(img, (plot_x, stop_y),
                         (plot_x + plot_w, stop_y),
                         DANGER, 1, cv2.LINE_AA)
            # eğri
            arr = np.array(pts, dtype=np.int32)
            cv2.polylines(img, [arr], False, ACCENT, 2, cv2.LINE_AA)
            # son nokta vurgu
            cv2.circle(img, pts[-1], 3, OK, -1)
        else:
            _put(img, "collecting…", (plot_x, plot_y + plot_h // 2 + 4),
                 0.4, TEXT_FAINT)
        return y + h + 8

    # Telemetri
    def _draw_telemetry(self, img, y, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        h = 64
        _rounded_card(img, x, y, w, h, "TELEMETRY")
        # HEAT
        heat_t = min(1.0, max(0.0, ctx.heat_c / max(1.0, ctx.heat_threshold)))
        heat_col = _lerp_color(OK, DANGER, heat_t)
        _put(img, "HEAT", (x + 12, y + 38), 0.40, TEXT_DIM)
        _bar(img, x + 56, y + 30, w - 122, 10, heat_t, heat_col)
        _put(img, f"{ctx.heat_c:5.1f}°C",
             (x + w - 60, y + 38), 0.42, TEXT, 1)
        # VOLT
        if ctx.voltage > 0:
            v_norm = (ctx.voltage - ctx.voltage_min) / max(
                0.1, ctx.voltage_nominal + 1.0 - ctx.voltage_min)
            v_norm = max(0.0, min(1.0, v_norm))
            v_col = _lerp_color(DANGER, OK, v_norm)
            v_txt = f"{ctx.voltage:5.2f}V"
        else:
            v_norm, v_col, v_txt = 0.0, TEXT_FAINT, "  N/A"
        _put(img, "VOLT", (x + 12, y + 56), 0.40, TEXT_DIM)
        _bar(img, x + 56, y + 48, w - 122, 10, v_norm, v_col)
        _put(img, v_txt, (x + w - 60, y + 56), 0.42, TEXT, 1)
        return y + h + 8

    # Komut
    def _draw_command(self, img, y, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        h = 60
        _rounded_card(img, x, y, w, h, "MOTOR COMMAND")
        name = {"W": "FORWARD", "S": "REVERSE", "A": "LEFT",
                "D": "RIGHT", "X": "STOP"}.get(ctx.cmd, ctx.cmd)
        cmd_col = DANGER if ctx.cmd == "X" else OK
        # büyük komut kutusu
        cx = x + 12
        cy = y + 30
        _filled(img, (cx, cy), (cx + 50, cy + 22), cmd_col)
        _put_bold(img, ctx.cmd, (cx + 16, cy + 17), 0.7, BG, 2)
        _put_bold(img, name, (cx + 62, cy + 17), 0.55, TEXT, 1)
        # hız
        _put(img, "SPD", (cx, y + 56), 0.4, TEXT_DIM)
        _bar(img, cx + 30, y + 49, w - 70, 8, ctx.spd / 255.0,
             _lerp_color(TEXT_FAINT, ACCENT, ctx.spd / 255.0))
        _put(img, f"{ctx.spd:>3}", (x + w - 30, y + 56), 0.42, TEXT, 1)
        return y + h + 8

    # Footer (kısayollar)
    def _draw_footer(self, img, ctx):
        x = self.pad
        w = self.W - 2 * self.pad
        h = 38
        H = img.shape[0]
        fy = H - h - self.pad
        _filled(img, (x, fy), (x + w, fy + h), CARD)
        cv2.rectangle(img, (x, fy), (x + w, fy + h), CARD_EDGE, 1)
        _put(img, "KEYS", (x + 10, fy + 14), 0.38, TEXT_DIM)
        _put(img, "M auto/man  R rec  Q quit",
             (x + 10, fy + 30), 0.40, TEXT, 1)
