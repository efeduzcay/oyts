#!/usr/bin/env python3
"""
fire_scene_generator.py — Foto-gerçekçi sentetik yangın sahnesi
================================================================
v2: Render boru hattı tamamen yenilendi.

Katmanlar (alttan üste):
    1) Arka plan: gradient + zemin dokusu + duvar lekeleri
    2) Yer ışık yansıması: alev altına geniş turuncu glow
    3) Duman: parçacık sistemi (yükselen + fade out gri puflar)
    4) Alev: çok-oktavlı value noise field, yukarı doğru damla şekli
       + iç-çekirdek beyaz-sarı, dış kırmızı palette
    5) Heat haze: alev üstündeki bölgede frame'i hafif distort et
    6) Kıvılcımlar: yukarı fırlayan minik parlak noktacıklar
    7) Bloom: parlak bölgeler → downscale → blur → screen blend
    8) Vignette + film grain

Performans: 960x540'ta MacBook M1 üzerinde ~25-40 FPS (NumPy + OpenCV).

Standalone:
    python sim/fire_scene_generator.py
    python sim/fire_scene_generator.py --targets 3 --width 1280 --height 720
"""

from __future__ import annotations

import argparse
import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np


# Yardımcı: ucuz value noise (low-res grid + bilinear upsample)
class ValueNoise:
    def __init__(self, w: int, h: int, low_res: int = 48, seed: int = 1):
        self.w, self.h = w, h
        self.rng = np.random.default_rng(seed)
        ratio = h / w
        self.lr_w = low_res
        self.lr_h = max(8, int(low_res * ratio))
        self._cache: dict = {}

    def field(self, octaves: int = 3, phase: float = 0.0,
              v_scroll: float = 0.0) -> np.ndarray:
        """Çoklu oktav, yukarı doğru kayan noise. [0,1]."""
        out = np.zeros((self.h, self.w), dtype=np.float32)
        amp_sum = 0.0
        for o in range(octaves):
            amp = 1.0 / (2 ** o)
            amp_sum += amp
            f = self._layer(o, phase, v_scroll)
            out += amp * f
        return np.clip(out / amp_sum, 0, 1)

    def _layer(self, o: int, phase: float, v_scroll: float) -> np.ndarray:
        scale = 2 ** o
        lw = max(4, self.lr_w * scale // 2)
        lh = max(4, self.lr_h * scale // 2)
        key = (o, lw, lh)
        if key not in self._cache:
            # 4 farklı snapshot → faza göre interpolate edilir
            self._cache[key] = self.rng.random((4, lh, lw), dtype=np.float32)
        stack = self._cache[key]
        # Faza göre seçim
        t = (phase * (0.5 + o * 0.4)) % 4
        i = int(t)
        f = t - i
        a = stack[i]
        b = stack[(i + 1) % 4]
        grid = a * (1 - f) + b * f
        # Yukarı kayma: y ekseninde roll
        shift = int(v_scroll * (o + 1) * 4) % lh
        if shift:
            grid = np.roll(grid, -shift, axis=0)
        # Bilinear upsample
        up = cv2.resize(grid, (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        return up


# Veri yapıları
@dataclass
class FireSpot:
    cx: float
    cy: float
    base_radius: float
    phase: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    intensity: float = 1.0
    smoke: bool = True
    age: float = 0.0
    # Her yangının kendi noise'u olsun → benzersiz görünüm
    seed: int = 1

    def step(self, dt: float, bounds: Tuple[int, int]):
        self.phase += dt * (1.2 + 0.4 * random.random())
        self.cx += self.vx * dt
        self.cy += self.vy * dt
        self.age += dt
        w, h = bounds
        m = self.base_radius
        if self.cx < m or self.cx > w - m:
            self.vx = -self.vx
        if self.cy < h * 0.30 or self.cy > h - m * 0.5:
            self.vy = -self.vy

    def current_radius(self) -> float:
        flick = 1.0 + 0.10 * math.sin(self.phase * 3.0) \
                    + 0.05 * math.sin(self.phase * 7.3)
        return self.base_radius * self.intensity * flick


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    age: float = 0.0


@dataclass
class SmokePuff:
    x: float
    y: float
    vx: float
    vy: float
    r: float
    life: float
    age: float = 0.0
    darkness: float = 0.7   # 0..1


@dataclass
class SceneConfig:
    width: int = 960
    height: int = 540
    bg_path: Optional[str] = None
    n_targets: int = 2
    moving: bool = True
    smoke: bool = True
    seed: Optional[int] = None
    approach_zoom: float = 1.0
    approach_cx: float = 0.5
    approach_cy: float = 0.5
    min_radius: int = 28
    max_radius: int = 70
    target_speed: float = 28.0
    growth_rate: float = 0.0
    enable_keys: bool = True
    # Görsel kalite (kapatılırsa CPU rahatlar)
    enable_bloom: bool = True
    enable_haze: bool = True
    enable_grain: bool = True
    enable_dynamic_light: bool = True   # alev → duvar titreşimli ışık
    enable_tone_map: bool = True        # ACES filmic tone mapping
    # Otomatik etiketleme
    emit_labels: bool = False           # last_labels() üzerinden geri döner
    show_labels: bool = False           # debug: bbox'ları frame üzerine çiz


# Sahne üreticisi
class FireSceneGenerator:
    KEYMAP_HELP = (
        "[+/-] yaklas/uzaklas  [n] yeni sahne  [1-5] hedef  "
        "[t] hareket  [g] buyume  [b] bloom  [k] haze  [h] yardim"
    )

    def __init__(self, cfg: Optional[SceneConfig] = None):
        self.cfg = cfg or SceneConfig()
        if self.cfg.seed is not None:
            random.seed(self.cfg.seed)
            np.random.seed(self.cfg.seed)

        self._spots: List[FireSpot] = []
        self._sparks: List[Spark] = []
        self._smoke: List[SmokePuff] = []
        self._last_t = time.perf_counter()
        self._show_help = False
        self._growing = self.cfg.growth_rate > 0

        # Kalıcı yapılar
        self._noise = ValueNoise(self.cfg.width, self.cfg.height, low_res=36,
                                 seed=random.randint(1, 10_000))
        self._flame_lut = self._make_flame_lut()
        self._bg = self._make_background()
        self._vignette = self._make_vignette()
        # Tone-map LUT — float [0,2] → uint8
        self._tone_lut = self._make_tone_lut() if self.cfg.enable_tone_map else None
        # Son frame etiketleri: list of (cls_id, x1, y1, x2, y2)
        self._last_labels: List[Tuple[int, int, int, int, int]] = []
        self._respawn(self.cfg.n_targets)

    # public API
    def isOpened(self) -> bool:  # noqa: N802
        return True

    def read(self):
        now = time.perf_counter()
        dt = max(1e-3, min(0.1, now - self._last_t))
        self._last_t = now

        bounds = (self.cfg.width, self.cfg.height)
        for s in self._spots:
            if self.cfg.moving:
                s.step(dt, bounds)
            if self._growing:
                s.intensity = min(1.5, s.intensity * (1.0 + self.cfg.growth_rate * dt))

        self._spawn_sparks(dt)
        self._spawn_smoke(dt)
        self._step_particles(dt)

        # 1) Arka plan
        frame = self._bg.copy().astype(np.float32)

        # 2) Dinamik ortam ışığı: alev konumlarına göre duvar+zemin aydınlatma
        if self.cfg.enable_dynamic_light:
            self._apply_dynamic_light(frame)

        # 3) Yer ışık yansıması (alev altında yumuşak turuncu disk)
        self._draw_ground_glow(frame)

        # 4) Duman parçacıkları
        if self.cfg.smoke:
            self._draw_smoke_particles(frame)

        # 5) Alev (noise tabanlı, palette uygulanmış) — 3 oktav
        flame_mask = self._draw_flames(frame)

        # 6) Heat haze
        if self.cfg.enable_haze:
            frame = self._apply_heat_haze_f(frame, flame_mask)

        # 7) Kıvılcımlar
        self._draw_sparks_f(frame)

        # 8) Bloom — HDR-like ekleme yapar (>255 olabilir)
        if self.cfg.enable_bloom:
            self._apply_bloom_f(frame)

        # 9) Tone mapping (ACES filmic) — HDR → SDR
        if self._tone_lut is not None:
            frame = self._apply_tone_map(frame)
        else:
            frame = np.clip(frame, 0, 255)

        # 10) Vignette + grain
        frame = frame * self._vignette
        if self.cfg.enable_grain:
            grain = np.random.normal(0, 4.0, frame.shape).astype(np.float32)
            frame = frame + grain
        frame = np.clip(frame, 0, 255).astype(np.uint8)

        # Etiketler (zoom öncesi, orijinal koordinatlarda)
        if self.cfg.emit_labels or self.cfg.show_labels:
            self._last_labels = self._compute_labels()

        # Zoom (etiketler de zoom'a uyarlanır)
        if self.cfg.approach_zoom > 1.001:
            frame, self._last_labels = self._apply_zoom_with_labels(
                frame, self._last_labels
            )

        if self.cfg.show_labels:
            self._draw_label_overlay(frame, self._last_labels)
        if self._show_help:
            self._draw_help(frame)
        return True, frame

    def last_labels(self) -> List[Tuple[int, int, int, int, int]]:
        """Son frame için (cls, x1, y1, x2, y2) etiket listesi.
        cls: 0=fire, 1=smoke. emit_labels=True veya show_labels=True olmalı."""
        return list(self._last_labels)

    def release(self):
        pass

    def handle_key(self, key: int) -> bool:
        if not self.cfg.enable_keys or key in (255, -1):
            return False
        ch = chr(key) if 0 <= key < 256 else ""
        if ch == "+":
            self.cfg.approach_zoom = min(4.0, self.cfg.approach_zoom + 0.15)
        elif ch == "-":
            self.cfg.approach_zoom = max(1.0, self.cfg.approach_zoom - 0.15)
        elif ch == "n":
            self._respawn(self.cfg.n_targets)
            self._bg = self._make_background()
        elif ch in "12345":
            self.cfg.n_targets = int(ch)
            self._respawn(self.cfg.n_targets)
        elif ch == "t":
            self.cfg.moving = not self.cfg.moving
        elif ch == "g":
            self._growing = not self._growing
            if self._growing and self.cfg.growth_rate == 0:
                self.cfg.growth_rate = 0.05
        elif ch == "b":
            self.cfg.enable_bloom = not self.cfg.enable_bloom
        elif ch == "k":
            self.cfg.enable_haze = not self.cfg.enable_haze
        elif ch == "h":
            self._show_help = not self._show_help
        else:
            return False
        return True

    # arka plan
    def _make_background(self) -> np.ndarray:
        if self.cfg.bg_path:
            img = cv2.imread(self.cfg.bg_path)
            if img is not None:
                return cv2.resize(img, (self.cfg.width, self.cfg.height))

        h, w = self.cfg.height, self.cfg.width
        # Loş bir oda: koyu lacivert-gri → siyah üst, hafif kahverengi alt
        bg = np.zeros((h, w, 3), dtype=np.float32)
        floor_y = int(h * 0.74)
        for y in range(h):
            if y < floor_y:
                # üst: duvar
                t = y / floor_y
                top    = np.array([22, 18, 14], dtype=np.float32)
                bottom = np.array([38, 32, 28], dtype=np.float32)
                bg[y, :] = top * (1 - t) + bottom * t
            else:
                # alt: zemin (kahverengi-gri, perspektif gradyanı)
                t = (y - floor_y) / max(1, h - floor_y)
                top    = np.array([42, 38, 36], dtype=np.float32)
                bottom = np.array([18, 16, 15], dtype=np.float32)
                bg[y, :] = top * (1 - t) + bottom * t

        # Duvar üzerinde leke/gölge dokusu
        rng = np.random.default_rng(11)
        for _ in range(70):
            x = int(rng.integers(0, w))
            y = int(rng.integers(int(h * 0.05), floor_y))
            r = int(rng.integers(30, 110))
            c = float(rng.integers(-12, 12))
            mask = np.zeros((h, w), dtype=np.float32)
            cv2.circle(mask, (x, y), r, 1.0, -1)
            mask = cv2.GaussianBlur(mask, (0, 0), r * 0.5)
            bg[..., 0] = np.clip(bg[..., 0] + c * mask, 0, 255)
            bg[..., 1] = np.clip(bg[..., 1] + c * mask, 0, 255)
            bg[..., 2] = np.clip(bg[..., 2] + c * mask, 0, 255)

        # Zemin çatlak/leke
        for _ in range(35):
            x = int(rng.integers(0, w))
            y = int(rng.integers(floor_y, h))
            r = int(rng.integers(8, 40))
            c = float(rng.integers(-15, 8))
            mask = np.zeros((h, w), dtype=np.float32)
            cv2.circle(mask, (x, y), r, 1.0, -1)
            mask = cv2.GaussianBlur(mask, (0, 0), r * 0.7)
            bg[..., 0] = np.clip(bg[..., 0] + c * mask, 0, 255)
            bg[..., 1] = np.clip(bg[..., 1] + c * mask, 0, 255)
            bg[..., 2] = np.clip(bg[..., 2] + c * mask, 0, 255)

        # Hafif duvar-zemin sınır çizgisi
        cv2.line(bg, (0, floor_y), (w, floor_y), (28, 25, 22), 1, cv2.LINE_AA)

        return bg.astype(np.uint8)

    def _make_vignette(self) -> np.ndarray:
        h, w = self.cfg.height, self.cfg.width
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        cx, cy = w / 2, h / 2
        d = np.sqrt(((xx - cx) / (w * 0.7)) ** 2 + ((yy - cy) / (h * 0.7)) ** 2)
        v = np.clip(1.0 - 0.45 * d ** 2, 0.45, 1.0)
        return v[..., None]

    # alev paleti
    def _make_flame_lut(self) -> np.ndarray:
        """256 girişli BGR alev paleti.
        0=şeffaf, 50=koyu kırmızı, 130=parlak turuncu, 220=sarı, 255=beyaz çekirdek."""
        pal = np.zeros((256, 3), dtype=np.uint8)
        stops = [
            (0,   (0,   0,   0)),       # şeffaf
            (40,  (0,   8,   45)),      # çok koyu kor
            (80,  (5,   28,  140)),     # koyu kırmızı
            (130, (15,  85,  235)),     # turuncu
            (180, (60,  170, 255)),     # sarı-turuncu
            (220, (140, 230, 255)),     # parlak sarı
            (255, (240, 250, 255)),     # beyaz çekirdek
        ]
        for i in range(len(stops) - 1):
            i0, c0 = stops[i]
            i1, c1 = stops[i + 1]
            for k in range(i0, i1 + 1):
                t = (k - i0) / max(1, (i1 - i0))
                pal[k] = [int(c0[j] * (1 - t) + c1[j] * t) for j in range(3)]
        return pal

    # spawn & step
    def _respawn(self, n: int):
        self._spots.clear()
        self._sparks.clear()
        self._smoke.clear()
        w, h = self.cfg.width, self.cfg.height
        for _ in range(n):
            cx = random.uniform(w * 0.18, w * 0.82)
            cy = random.uniform(h * 0.55, h * 0.82)
            r = random.uniform(self.cfg.min_radius, self.cfg.max_radius)
            vx = random.uniform(-self.cfg.target_speed, self.cfg.target_speed) \
                if self.cfg.moving else 0.0
            vy = random.uniform(-8, 8) if self.cfg.moving else 0.0
            self._spots.append(FireSpot(
                cx=cx, cy=cy, base_radius=r,
                phase=random.uniform(0, 6.28),
                vx=vx, vy=vy,
                intensity=random.uniform(0.75, 1.1),
                smoke=self.cfg.smoke and random.random() > 0.15,
                seed=random.randint(1, 9999),
            ))

    def _spawn_sparks(self, dt: float):
        for s in self._spots:
            n = int(s.intensity * 4 + 2)
            if random.random() > dt * 30:   # ortalama oran kontrolü
                n = max(0, n - 2)
            for _ in range(n):
                if random.random() > 0.5:
                    continue
                r = s.current_radius()
                self._sparks.append(Spark(
                    x=s.cx + random.uniform(-r * 0.4, r * 0.4),
                    y=s.cy - r * 0.4 + random.uniform(-r * 0.2, 0),
                    vx=random.uniform(-25, 25),
                    vy=random.uniform(-160, -60) * s.intensity,
                    life=random.uniform(0.4, 1.1),
                ))

    def _spawn_smoke(self, dt: float):
        if not self.cfg.smoke:
            return
        for s in self._spots:
            if not s.smoke:
                continue
            rate = 3.0 + 4.0 * s.intensity   # puf/sn
            n = np.random.poisson(rate * dt)
            for _ in range(int(n)):
                r = s.current_radius()
                self._smoke.append(SmokePuff(
                    x=s.cx + random.uniform(-r * 0.5, r * 0.5),
                    y=s.cy - r * 0.6,
                    vx=random.uniform(-12, 12),
                    vy=random.uniform(-55, -25),
                    r=random.uniform(r * 0.7, r * 1.2),
                    life=random.uniform(1.8, 3.0),
                    darkness=random.uniform(0.5, 0.85),
                ))

    def _step_particles(self, dt: float):
        for s in self._sparks:
            s.age += dt
            s.x += s.vx * dt
            s.y += s.vy * dt
            s.vy += 60 * dt   # hafif yer çekimi (yukarı yavaşlar)
        self._sparks = [s for s in self._sparks if s.age < s.life]

        for p in self._smoke:
            p.age += dt
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.r += 25 * dt    # yayılır
            p.vx *= 0.99
        self._smoke = [p for p in self._smoke if p.age < p.life]

    # render katmanları
    def _apply_dynamic_light(self, frame: np.ndarray):
        """Alev konumlarına göre yakın duvar+zeminde titreşen turuncu ışık.
        Lokal kalsın, tüm sahneyi boyamasın."""
        h, w = frame.shape[:2]
        sw, sh = w // 2, h // 2
        canvas = np.zeros((sh, sw), dtype=np.float32)
        for s in self._spots:
            r = s.current_radius() * 3.5 / 2
            if r < 2:
                continue
            cx = int(s.cx / 2)
            cy = int(s.cy / 2)
            flick = 1.0 + 0.18 * math.sin(s.phase * 4.7) \
                        + 0.10 * math.sin(s.phase * 9.1)
            cv2.circle(canvas, (cx, cy), int(r), float(s.intensity * flick), -1)
        if canvas.max() <= 0:
            return
        canvas = cv2.GaussianBlur(canvas, (0, 0), 14)
        canvas = cv2.resize(canvas, (w, h), interpolation=cv2.INTER_LINEAR)
        # BGR: hafif amber — tonu bozmasın
        color = np.array([12, 38, 80], dtype=np.float32) * 0.55
        frame += canvas[..., None] * color

    def _draw_ground_glow(self, frame: np.ndarray):
        """Alev altında yumuşak eliptik turuncu yer yansıması."""
        h, w = frame.shape[:2]
        sw, sh = w // 2, h // 2
        disk = np.zeros((sh, sw), dtype=np.float32)
        intensities = []
        for s in self._spots:
            r = int(s.current_radius() * 3.5 / 2)
            if r < 2:
                continue
            cx = int(s.cx / 2)
            cy = int(min(sh - 2, (s.cy + s.base_radius * 0.6) / 2))
            cv2.ellipse(disk, (cx, cy), (r, r // 2), 0, 0, 360,
                        float(s.intensity), -1)
            intensities.append(s.intensity)
        if not intensities:
            return
        disk = cv2.GaussianBlur(disk, (0, 0), 14)
        disk = cv2.resize(disk, (w, h), interpolation=cv2.INTER_LINEAR)
        color = np.array([20, 90, 220], dtype=np.float32) * 0.85
        frame += disk[..., None] * color

    def _draw_smoke_particles(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        sw, sh = w // 2, h // 2
        canvas = np.zeros((sh, sw), dtype=np.float32)
        for p in self._smoke:
            x, y = int(p.x / 2), int(p.y / 2)
            r = int(p.r / 2)
            if x < -r or x > sw + r or y < -r or y > sh + r:
                continue
            life_t = p.age / p.life
            alpha = (1 - life_t) * p.darkness * 0.6
            cv2.circle(canvas, (x, y), r, alpha, -1)
        if canvas.max() <= 0:
            return
        canvas = cv2.GaussianBlur(canvas, (0, 0), 7)
        canvas = cv2.resize(canvas, (w, h), interpolation=cv2.INTER_LINEAR)
        canvas = np.clip(canvas, 0, 0.85)
        gray = np.full((h, w, 3), [70, 70, 75], dtype=np.float32)
        a = canvas[..., None]
        frame[:] = frame * (1 - a) + gray * a

    def _draw_flames(self, frame: np.ndarray) -> np.ndarray:
        """Tüm alevleri tek bir intensity field'inde topla, palette uygula.
        Geri dön: float32 mask (0..1) — bloom ve haze için kullanılır."""
        h, w = frame.shape[:2]
        # Global noise field — tüm sahnede aynı, ucuz
        noise_phase = sum(s.phase for s in self._spots) / max(1, len(self._spots))
        noise = self._noise.field(octaves=3, phase=noise_phase, v_scroll=0.7)

        intensity_field = np.zeros((h, w), dtype=np.float32)

        for s in self._spots:
            r = max(8.0, s.current_radius())
            cx, cy = s.cx, s.cy
            # Bounding box — performans için
            pad = int(r * 3.0)
            x0 = max(0, int(cx - pad))
            x1 = min(w, int(cx + pad))
            y0 = max(0, int(cy - pad * 1.6))
            y1 = min(h, int(cy + pad * 0.7))
            if x1 <= x0 or y1 <= y0:
                continue
            # Sadece bbox içinde grid üret — global mgrid'den daha ucuz
            sub_yy, sub_xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            sub_xx = sub_xx - cx
            sub_yy = sub_yy - cy

            # Damla / sivri tepe şekli:
            # - Yatay genişlik: r
            # - Dikey: yukarı doğru daralan, aşağıda hafif geniş taban
            # dist_y >0 = aşağı, <0 = yukarı
            up = -sub_yy
            up_norm = up / (r * 1.8)         # >0 yukarı
            # Yukarı sivri için yatay genişliği azalt
            width_factor = np.where(
                up_norm > 0,
                1.0 - 0.6 * np.clip(up_norm, 0, 1.4) ** 1.2,
                1.0 + 0.25 * np.clip(-up_norm, 0, 1),
            )
            wx = np.maximum(0.2, width_factor) * r
            dx_n = sub_xx / wx
            dy_n = sub_yy / (r * 1.6)
            shape_dist = np.sqrt(dx_n * dx_n + dy_n * dy_n)
            base = np.clip(1.0 - shape_dist, 0, 1)
            base = base ** 0.85

            # Noise modülasyonu — alev hareketli görünür
            n_sub = noise[y0:y1, x0:x1]
            # Yukarı doğru kayan, alev kenarını parçalayan
            modulated = base * (0.55 + 0.55 * n_sub)
            # Üst kuyrukta noise daha güçlü
            tail_boost = np.clip(up_norm, 0, 1.3) * 0.35
            modulated += tail_boost * (n_sub - 0.5)
            modulated = np.clip(modulated, 0, 1.3) * s.intensity

            intensity_field[y0:y1, x0:x1] = np.maximum(
                intensity_field[y0:y1, x0:x1], modulated
            )

        if intensity_field.max() <= 0:
            return intensity_field

        # Palette
        idx = np.clip(intensity_field * 255, 0, 255).astype(np.uint8)
        flame = self._flame_lut[idx].astype(np.float32)

        # Screen blend
        a = np.clip(intensity_field, 0, 1)[..., None] ** 1.1
        frame[:] = frame * (1 - a) + flame * a
        # Sıcak çekirdek için additive HDR boost (>1.0 değerler tone-map için)
        hot = np.clip(intensity_field - 0.85, 0, 1)[..., None] * 1.8
        frame += flame * hot

        return intensity_field

    def _apply_heat_haze_f(self, frame: np.ndarray,
                           flame_mask: np.ndarray) -> np.ndarray:
        """Alev üstündeki bölgede yatay sinüsoidal distorsiyon. float32 in/out."""
        h, w = frame.shape[:2]
        haze_strength = cv2.GaussianBlur(flame_mask, (0, 0), 8)
        haze_strength = np.roll(haze_strength, -int(h * 0.05), axis=0)
        if haze_strength.max() < 0.05:
            return frame
        t = time.perf_counter() * 4.0
        yy = np.arange(h, dtype=np.float32)[:, None]
        wave = np.sin(yy * 0.08 + t) * 3.5 * haze_strength
        map_x, map_y = np.meshgrid(np.arange(w, dtype=np.float32),
                                   np.arange(h, dtype=np.float32))
        map_x = map_x + wave
        return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_REFLECT)

    def _draw_sparks_f(self, frame: np.ndarray):
        """float32 frame üstüne additive parlak nokta + glow."""
        for s in self._sparks:
            t = s.age / s.life
            if t >= 1:
                continue
            alpha = 1.0 - t
            x, y = int(s.x), int(s.y)
            if 0 <= x < frame.shape[1] and 0 <= y < frame.shape[0]:
                core = (240.0 * alpha, 250.0 * alpha, 255.0 * alpha)
                outer = (60.0 * alpha, 180.0 * alpha, 255.0 * alpha)
                cv2.circle(frame, (x, y), 3, outer, -1, cv2.LINE_AA)
                cv2.circle(frame, (x, y), 1, core, -1, cv2.LINE_AA)

    def _apply_bloom_f(self, frame: np.ndarray):
        """HDR-friendly bloom — in-place additive. frame float32."""
        bright = np.clip(frame - 165, 0, None)
        if bright.max() < 5:
            return
        small = cv2.resize(bright, None, fx=0.25, fy=0.25,
                           interpolation=cv2.INTER_LINEAR)
        small = cv2.GaussianBlur(small, (0, 0), 8)
        bloom = cv2.resize(small, (frame.shape[1], frame.shape[0]),
                           interpolation=cv2.INTER_LINEAR)
        frame += bloom * 0.9

    # ACES filmic tone mapping
    def _make_tone_lut(self) -> np.ndarray:
        """[0, 1.5] HDR aralığını [0, 255]'e map eden ACES filmic LUT."""
        n = 2049
        x = np.linspace(0, 1.5, n).astype(np.float32)
        # ACES filmic (kısa form)
        a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
        # Exposure compensation: girdi yumuşatıldı (0.85x)
        xs = x * 0.85
        y = (xs * (a * xs + b)) / (xs * (c * xs + d) + e)
        y = np.clip(y, 0, 1.0)
        return (y * 255.0).astype(np.float32)

    def _apply_tone_map(self, frame: np.ndarray) -> np.ndarray:
        # Normalize 0..255 → 0..1.5 (HDR aralığı dar)
        norm = np.clip(frame / 255.0, 0, 1.5)
        idx = np.clip(norm * (2048 / 1.5), 0, 2048).astype(np.int32)
        return self._tone_lut[idx]

    def _apply_zoom(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        z = self.cfg.approach_zoom
        cw, ch = int(w / z), int(h / z)
        cx = int(self.cfg.approach_cx * w)
        cy = int(self.cfg.approach_cy * h)
        x0 = max(0, min(w - cw, cx - cw // 2))
        y0 = max(0, min(h - ch, cy - ch // 2))
        crop = frame[y0:y0 + ch, x0:x0 + cw]
        return cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)

    def _apply_zoom_with_labels(self, frame, labels):
        h, w = frame.shape[:2]
        z = self.cfg.approach_zoom
        cw, ch = int(w / z), int(h / z)
        cx = int(self.cfg.approach_cx * w)
        cy = int(self.cfg.approach_cy * h)
        x0 = max(0, min(w - cw, cx - cw // 2))
        y0 = max(0, min(h - ch, cy - ch // 2))
        crop = frame[y0:y0 + ch, x0:x0 + cw]
        out = cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)
        sx = w / cw
        sy = h / ch
        new_lbls = []
        for (cls, lx1, ly1, lx2, ly2) in labels:
            nx1 = int((lx1 - x0) * sx)
            ny1 = int((ly1 - y0) * sy)
            nx2 = int((lx2 - x0) * sx)
            ny2 = int((ly2 - y0) * sy)
            # Crop alanı dışında kalanı at
            nx1 = max(0, min(w - 1, nx1))
            nx2 = max(0, min(w - 1, nx2))
            ny1 = max(0, min(h - 1, ny1))
            ny2 = max(0, min(h - 1, ny2))
            if nx2 - nx1 < 4 or ny2 - ny1 < 4:
                continue
            new_lbls.append((cls, nx1, ny1, nx2, ny2))
        return out, new_lbls

    # Etiketler
    def _compute_labels(self) -> List[Tuple[int, int, int, int, int]]:
        """Her FireSpot için fire(0) bbox + her duman bulutu için smoke(1) bbox.
        Sıkı bbox: alev damla formuna göre, duman parçacık demetine göre."""
        h, w = self.cfg.height, self.cfg.width
        labels: List[Tuple[int, int, int, int, int]] = []

        for s in self._spots:
            r = s.current_radius()
            # Damla: yukarı 1.6r, aşağı 0.55r, yana 1.0r
            x1 = max(0, int(s.cx - r * 1.0))
            y1 = max(0, int(s.cy - r * 1.6))
            x2 = min(w - 1, int(s.cx + r * 1.0))
            y2 = min(h - 1, int(s.cy + r * 0.55))
            if x2 - x1 >= 6 and y2 - y1 >= 6:
                labels.append((0, x1, y1, x2, y2))

        # Duman: her spot için aktif duman parçacıklarını grupla → tek bbox
        if self.cfg.smoke and self._smoke:
            # Her spot'a yakın parçacıkları topla
            for s in self._spots:
                if not s.smoke:
                    continue
                near = [
                    p for p in self._smoke
                    if abs(p.x - s.cx) < s.base_radius * 4
                    and p.y < s.cy + 10
                    and p.age < p.life * 0.95
                ]
                if len(near) < 3:
                    continue
                xs = [p.x for p in near]
                ys = [p.y for p in near]
                rs = [p.r for p in near]
                x1 = max(0, int(min(x - r for x, r in zip(xs, rs))))
                y1 = max(0, int(min(y - r for y, r in zip(ys, rs))))
                x2 = min(w - 1, int(max(x + r for x, r in zip(xs, rs))))
                y2 = min(h - 1, int(max(y + r for y, r in zip(ys, rs))))
                if x2 - x1 >= 20 and y2 - y1 >= 20:
                    labels.append((1, x1, y1, x2, y2))
        return labels

    def _draw_label_overlay(self, frame, labels):
        for (cls, x1, y1, x2, y2) in labels:
            if cls == 0:
                color = (0, 200, 0)
                name = "fire"
            else:
                color = (180, 180, 180)
                name = "smoke"
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)
            cv2.putText(frame, name, (x1 + 2, y1 - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

    def _draw_help(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        ov = frame.copy()
        cv2.rectangle(ov, (10, 10), (w - 10, 80), (0, 0, 0), -1)
        cv2.addWeighted(ov, 0.65, frame, 0.35, 0, frame)
        cv2.putText(frame, "SYNTHETIC FIRE SCENE — SIMULATION",
                    (24, 38), cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 200, 255), 1)
        cv2.putText(frame, self.KEYMAP_HELP, (24, 64),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1)


# Otomatik etiketleme: dataset dump helper
def dump_synthetic_dataset(
    out_dir: str,
    n_frames: int = 1000,
    width: int = 960,
    height: int = 540,
    n_targets_range: Tuple[int, int] = (1, 4),
    skip_warmup: int = 8,
    smoke_prob: float = 0.85,
    seed: int = 0,
):
    """N tane senaryo üretip her birinden birkaç kare çek, YOLO formatında yaz.

    Çıktı:
        out_dir/images/*.jpg
        out_dir/labels/*.txt   (cls cx_n cy_n w_n h_n)
        out_dir/classes.txt    (fire\\nsmoke)
    """
    import os
    from pathlib import Path
    out = Path(out_dir)
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(parents=True, exist_ok=True)
    (out / "classes.txt").write_text("fire\nsmoke\n")

    rng = random.Random(seed)
    written = 0
    scene_idx = 0
    while written < n_frames:
        scene_idx += 1
        cfg = SceneConfig(
            width=width, height=height,
            n_targets=rng.randint(*n_targets_range),
            smoke=rng.random() < smoke_prob,
            moving=True,
            emit_labels=True,
            enable_keys=False,
            seed=rng.randint(1, 10_000_000),
        )
        gen = FireSceneGenerator(cfg)
        # Sahne başına 6-10 kare al, faz değişsin
        for _ in range(skip_warmup):
            gen.read()
        per_scene = rng.randint(6, 10)
        for _ in range(per_scene):
            if written >= n_frames:
                break
            ok, frame = gen.read()
            labels = gen.last_labels()
            if not labels:
                continue
            stem = f"syn_{written:06d}"
            img_path = out / "images" / f"{stem}.jpg"
            lbl_path = out / "labels" / f"{stem}.txt"
            cv2.imwrite(str(img_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            lines = []
            for (cls, x1, y1, x2, y2) in labels:
                cxn = ((x1 + x2) / 2) / width
                cyn = ((y1 + y2) / 2) / height
                wn = (x2 - x1) / width
                hn = (y2 - y1) / height
                lines.append(f"{cls} {cxn:.6f} {cyn:.6f} {wn:.6f} {hn:.6f}")
            lbl_path.write_text("\n".join(lines) + "\n")
            written += 1
            if written % 50 == 0:
                print(f"  yazildi: {written}/{n_frames}")
    print(f"[OK] {written} kare yazildi → {out}")


def _selftest():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--height", type=int, default=540)
    ap.add_argument("--targets", type=int, default=2)
    ap.add_argument("--bg", default=None, help="Arkaplan görseli yolu")
    ap.add_argument("--no-smoke", action="store_true")
    ap.add_argument("--no-move", action="store_true")
    ap.add_argument("--no-bloom", action="store_true")
    ap.add_argument("--no-haze", action="store_true")
    ap.add_argument("--no-light", action="store_true",
                    help="Dinamik ortam ışığını kapat")
    ap.add_argument("--no-tone", action="store_true",
                    help="ACES tone-map'i kapat")
    ap.add_argument("--show-labels", action="store_true",
                    help="bbox etiketlerini frame üzerine çiz")
    ap.add_argument("--seed", type=int, default=None)
    # Dataset dump modu
    ap.add_argument("--dump", default=None,
                    help="Çıktı dizini — dataset üretir, görüntü açmaz")
    ap.add_argument("--dump-frames", type=int, default=500)
    args = ap.parse_args()

    if args.dump:
        dump_synthetic_dataset(
            args.dump, n_frames=args.dump_frames,
            width=args.width, height=args.height,
        )
        return

    cfg = SceneConfig(
        width=args.width, height=args.height,
        n_targets=args.targets,
        bg_path=args.bg,
        smoke=not args.no_smoke,
        moving=not args.no_move,
        enable_bloom=not args.no_bloom,
        enable_haze=not args.no_haze,
        enable_dynamic_light=not args.no_light,
        enable_tone_map=not args.no_tone,
        show_labels=args.show_labels,
        emit_labels=args.show_labels,
        seed=args.seed,
    )
    gen = FireSceneGenerator(cfg)
    print("Sentetik sahne testi. q=cik. " + FireSceneGenerator.KEYMAP_HELP)
    if args.show_labels:
        print("Label overlay ACIK (yeşil=fire, gri=smoke)")
    t0 = time.perf_counter()
    n = 0
    fps_disp = 0.0
    while True:
        ok, frame = gen.read()
        if not ok:
            break
        n += 1
        if n % 15 == 0:
            fps_disp = n / (time.perf_counter() - t0)
        cv2.putText(frame, f"render FPS: {fps_disp:.1f}",
                    (12, frame.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        cv2.imshow("FireSceneGenerator v2", frame)
        k = cv2.waitKey(20) & 0xFF
        if k == ord("q"):
            break
        if k == ord("L") or k == ord("l"):
            # canlı 'l' tuşu ile label aç/kapa
            cfg.show_labels = not cfg.show_labels
            cfg.emit_labels = cfg.show_labels
        gen.handle_key(k)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    _selftest()
