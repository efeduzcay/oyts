"""OYTS Launcher — tek pencere arayüzü.

Çift tıkla aç, 3 butondan birine bas, gerisi otomatik:
  • Kameralı Başlat (webcam)
  • Simülasyon Başlat (sentetik yangın)
  • Durdur (kamerayı serbest bırak)

Tkinter ile yazıldı (Python standart kütüphanesi, ek paket gerekmez).
Backend ve frontend'i subprocess olarak yönetir; arka planda thread ile
healthz polling yapar; UI thread'i bloklamaz.
"""
from __future__ import annotations

import os
import platform
import queue
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

# PyInstaller frozen modu: .exe içinde paketlenmişiz.
# _MEIPASS = geçici çıkartma klasörü; python/ ve web/ oraya kopyalanır.
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    REPO_ROOT  = Path(getattr(sys, "_MEIPASS"))
    PYTHON_DIR = REPO_ROOT / "python"
    WEB_DIR    = REPO_ROOT / "web"
else:
    REPO_ROOT  = Path(__file__).resolve().parent.parent
    PYTHON_DIR = REPO_ROOT / "python"
    WEB_DIR    = REPO_ROOT / "web"
LOG_DIR    = Path(tempfile.gettempdir()) / "oyts_demo"
LOG_DIR.mkdir(parents=True, exist_ok=True)

BACKEND_PORT  = 5050
FRONTEND_PORT = 8765
HEALTHZ_URL   = f"http://127.0.0.1:{BACKEND_PORT}/healthz"
FRONTEND_URL  = f"http://127.0.0.1:{FRONTEND_PORT}/live.html"

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"


def _force_macos_light_appearance() -> None:
    """macOS sistem Python'u Tk 8.5.9 kullanıyor; Dark Mode'da widget bg
    renkleri okunamaz hâle geliyor. NSApp.appearance'ı NSAppearanceNameAqua
    (light) yapıp tüm Tk pencerelerini light mode'a zorla."""
    if not IS_MACOS:
        return
    try:
        import ctypes
        from ctypes import c_void_p, c_char_p
        objc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.dylib")
        objc.objc_getClass.restype = c_void_p
        objc.objc_getClass.argtypes = [c_char_p]
        objc.sel_registerName.restype = c_void_p
        objc.sel_registerName.argtypes = [c_char_p]
        objc.objc_msgSend.restype = c_void_p

        def cls(name: str) -> int:
            return objc.objc_getClass(name.encode())

        def sel(name: str) -> int:
            return objc.sel_registerName(name.encode())

        # NSApp = [NSApplication sharedApplication]
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p]
        ns_app = objc.objc_msgSend(cls("NSApplication"),
                                   sel("sharedApplication"))

        # @"NSAppearanceNameAqua" -> NSString
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_char_p]
        ns_str = objc.objc_msgSend(cls("NSString"),
                                   sel("stringWithUTF8String:"),
                                   b"NSAppearanceNameAqua")

        # appearance = [NSAppearance appearanceNamed:@"…Aqua"]
        objc.objc_msgSend.argtypes = [c_void_p, c_void_p, c_void_p]
        appearance = objc.objc_msgSend(cls("NSAppearance"),
                                       sel("appearanceNamed:"),
                                       ns_str)

        # [NSApp setAppearance:appearance]
        objc.objc_msgSend(ns_app, sel("setAppearance:"), appearance)
    except Exception:
        pass

# Brand palette — live.html ile uyumlu (Piri Reis Üni.)
COLOR_BG        = "#F8FAFF"   # sayfa zemini
COLOR_CARD      = "#ffffff"
COLOR_TEXT      = "#0f172a"
COLOR_MUTED     = "#64748b"
COLOR_BORDER    = "#e2e8f0"
COLOR_PRU_DARK  = "#001f4d"   # hero gradient start
COLOR_PRU_BLUE  = "#0047AB"   # PRU mavisi (brand)
COLOR_PRU_LIGHT = "#1d4ed8"   # ikincil mavi
COLOR_ACCENT    = "#FF6B35"   # turuncu (yangın vurgu)
COLOR_FIRE      = "#dc2626"
COLOR_OK        = "#15803d"
COLOR_WARN      = "#b45309"
COLOR_BTN_CAM   = "#0047AB"   # webcam = PRU mavi
COLOR_BTN_SIM   = "#1d4ed8"   # sim = açık lacivert
COLOR_BTN_STOP  = "#dc2626"   # durdur = kırmızı


# Backend lifecycle
class DemoController:
    def __init__(self, log_cb):
        self.backend: subprocess.Popen | None = None
        self.frontend: subprocess.Popen | None = None
        self.source: str | None = None     # "webcam" | "synthetic" | None
        self.log_cb = log_cb
        self._lock = threading.Lock()

    def log(self, msg: str) -> None:
        self.log_cb(msg)

    # Process helpers
    @staticmethod
    def _kill_pattern(pattern: str) -> int:
        """Eski instansları öldür; öldürülen sayısını döner.

        Frozen .exe modunda komut satırı python.exe ile başlamadığı için
        WMIC pattern eşleşmez — orphan temizliği atlanır (popen handle
        ile yapılan normal stop() yeterli).
        """
        if FROZEN:
            return 0
        killed = 0
        if IS_WINDOWS:
            try:
                # WMIC yerine taskkill + findstr (daha hızlı + WMIC deprecated)
                out = subprocess.run(
                    ["wmic", "process", "where",
                     f"name='python.exe' and commandline like '%{pattern}%'",
                     "get", "ProcessId"],
                    capture_output=True, text=True, timeout=5,
                )
                for line in out.stdout.splitlines():
                    pid = line.strip()
                    if pid.isdigit():
                        subprocess.run(["taskkill", "/F", "/PID", pid],
                                       capture_output=True)
                        killed += 1
            except Exception:
                pass
        else:
            try:
                subprocess.run(["pkill", "-f", f"python.*{pattern}"],
                               capture_output=True)
                killed = 1
            except Exception:
                pass
        return killed

    def _python(self) -> str:
        """Aktif Python yorumlayıcısının yolu."""
        return sys.executable

    # Subprocess komut üretici — frozen .exe self-dispatch eder
    def _cmd_webapp(self, *extra: str) -> list[str]:
        if FROZEN:
            return [sys.executable, "--oyts-mode=webapp", *extra]
        return [self._python(), str(PYTHON_DIR / "web_app.py"), *extra]

    def _cmd_serve(self, *extra: str) -> list[str]:
        if FROZEN:
            return [sys.executable, "--oyts-mode=serve", *extra]
        return [self._python(), str(WEB_DIR / "serve.py"), *extra]

    # Setup (paketler + model)
    def run_setup(self) -> bool:
        if FROZEN:
            # .exe'de bağımlılıklar zaten gömülü; pip kurulumu gerekmez.
            return True
        self.log("• Ortam kontrolü...")
        try:
            result = subprocess.run(
                [self._python(), "-m", "utils.setup_env", "--quiet"],
                cwd=str(PYTHON_DIR), capture_output=True, text=True, timeout=300,
            )
            if result.returncode != 0:
                self.log("✗ Kurulum başarısız:")
                for line in (result.stdout + result.stderr).strip().splitlines()[-6:]:
                    self.log(f"  {line}")
                return False
            self.log("✓ Ortam hazır.")
            return True
        except Exception as e:
            self.log(f"✗ Setup hatası: {e}")
            return False

    # Doctor preflight
    def run_doctor(self, source: str = "any") -> bool:
        if FROZEN:
            # Doctor pip / venv kontrolü yapıyor — .exe'de anlamsız. Geç.
            return True
        self.log(f"• Preflight ({source})...")
        try:
            result = subprocess.run(
                [self._python(), "-m", "utils.doctor",
                 "--source", source,
                 "--ports", f"{BACKEND_PORT},{FRONTEND_PORT}",
                 "--open-settings"],
                cwd=str(PYTHON_DIR), capture_output=True, text=True, timeout=30,
            )
            for line in result.stdout.strip().splitlines():
                self.log(f"  {line}")
            return result.returncode == 0
        except Exception as e:
            self.log(f"✗ Doctor hatası: {e}")
            return False

    # Backend + frontend
    def start(self, source: str, on_ready, on_failed) -> None:
        """Arka planda başlatır; bittiğinde callback'i UI thread'inde çağırır."""
        thread = threading.Thread(target=self._start_worker,
                                  args=(source, on_ready, on_failed),
                                  daemon=True)
        thread.start()

    def _start_worker(self, source: str, on_ready, on_failed) -> None:
        with self._lock:
            self.stop(silent=True)  # önce eski instansları temizle

            if not self.run_setup():
                on_failed("Kurulum tamamlanamadı.")
                return
            if not self.run_doctor(source):
                on_failed("Preflight başarısız. Yukarıdaki ipuçlarını oku.")
                return

            cfg_args = []
            if source in ("webcam", "esp32"):
                cfg_args = ["--config",
                            str(PYTHON_DIR / "configs" / "config_webcam.yaml")]

            backend_log = open(LOG_DIR / "backend.log", "w")
            frontend_log = open(LOG_DIR / "frontend.log", "w")

            self.log(f"• Backend başlıyor (source={source})...")
            self.backend = subprocess.Popen(
                self._cmd_webapp(
                    *cfg_args,
                    "--port", str(BACKEND_PORT),
                    "--source", source,
                    "--autostart",
                ),
                cwd=str(PYTHON_DIR) if not FROZEN else None,
                stdout=backend_log, stderr=subprocess.STDOUT,
            )

            self.log("• Frontend başlıyor...")
            self.frontend = subprocess.Popen(
                self._cmd_serve(str(FRONTEND_PORT)),
                cwd=str(REPO_ROOT) if not FROZEN else None,
                stdout=frontend_log, stderr=subprocess.STDOUT,
            )

            self.log("• Backend hazır olması bekleniyor...")
            ready = self._wait_healthz(timeout=40)
            if not ready:
                tail = self._tail_log(LOG_DIR / "backend.log", 8)
                self.log("✗ Backend 40 sn'de hazır olmadı. Log son satırlar:")
                for line in tail:
                    self.log(f"  {line}")
                self.stop(silent=True)
                on_failed("Backend hazır olmadı.")
                return

            self.source = source
            self.log(f"✓ Hazır → {FRONTEND_URL}")
            on_ready(source)

    def _wait_healthz(self, timeout: int) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(HEALTHZ_URL, timeout=1) as r:
                    if r.status == 200:
                        return True
            except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError):
                pass
            time.sleep(0.5)
        return False

    def _tail_log(self, path: Path, n: int) -> list[str]:
        try:
            with open(path) as f:
                return f.read().strip().splitlines()[-n:]
        except Exception:
            return []

    # Stop
    def stop(self, silent: bool = False) -> None:
        had = self.backend is not None or self.frontend is not None
        for proc, name in ((self.backend, "backend"), (self.frontend, "frontend")):
            if proc is None:
                continue
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception:
                pass
        self.backend = None
        self.frontend = None
        # Repo dışından başlatılmış instansları da temizle (önceki çift tıkla)
        self._kill_pattern("web_app.py")
        self._kill_pattern("serve.py")
        self.source = None
        if had and not silent:
            self.log("✓ Sunucular durduruldu.")

    # Live status
    def health_check(self) -> str:
        """UI polling — 'running:<source>' | 'stopped' | 'orphan'."""
        try:
            with urllib.request.urlopen(HEALTHZ_URL, timeout=0.5) as r:
                if r.status == 200:
                    if self.source:
                        return f"running:{self.source}"
                    return "orphan"  # backend açık ama biz başlatmadık
        except Exception:
            return "stopped"
        return "stopped"


# UI
class LauncherUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OYTS — Piri Reis Üniversitesi")
        self.geometry("720x620")
        self.minsize(660, 560)
        self.configure(bg=COLOR_BG)

        # macOS Dark Mode tk.Frame/tk.Label bg renklerini override eder
        # → pencereyi zorla "aqua" (light) appearance'a sok.
        if IS_MACOS:
            for cmd in (
                ("::tk::unsupported::MacWindowStyle", "appearance",
                 self._w, "aqua"),
                ("::tk::unsupported::MacWindowStyle", "appearance",
                 self._w, "light"),
            ):
                try:
                    self.tk.call(*cmd)
                    break
                except tk.TclError:
                    continue

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.ctrl = DemoController(self._enqueue_log)

        self._build_ui()
        self._poll_log_queue()
        self._poll_status()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # Layout
    def _build_ui(self) -> None:
        title_font   = tkfont.Font(family="Helvetica", size=20, weight="bold")
        brand_font   = tkfont.Font(family="Helvetica", size=11, weight="bold")
        sub_font     = tkfont.Font(family="Helvetica", size=11)
        tiny_font    = tkfont.Font(family="Helvetica", size=10)
        btn_font     = tkfont.Font(family="Helvetica", size=13, weight="bold")
        status_font  = tkfont.Font(family="Helvetica", size=12, weight="bold")
        emblem_font  = tkfont.Font(family="Helvetica", size=14, weight="bold")
        log_font     = tkfont.Font(family="Menlo" if IS_MACOS else "Consolas",
                                   size=10)

        # Hero header (PRU mavi banner + amblem)
        # Tk 8.5.9 Canvas bg renkleri güvenilmez → Frame + Label kullan
        hero = tk.Frame(self, bg=COLOR_PRU_BLUE, height=130)
        hero.pack(fill="x")
        hero.pack_propagate(False)

        # Sol: amblem (beyaz daire yerine kare PRÜ rozeti)
        emblem = tk.Frame(hero, bg="#ffffff", width=64, height=64,
                          highlightthickness=0)
        emblem.pack(side="left", padx=(24, 16), pady=33)
        emblem.pack_propagate(False)
        tk.Label(emblem, text="PRÜ", bg="#ffffff", fg=COLOR_PRU_BLUE,
                 font=tkfont.Font(family="Helvetica", size=18,
                                  weight="bold")).pack(expand=True)

        # Orta: başlık + alt yazılar
        titles = tk.Frame(hero, bg=COLOR_PRU_BLUE)
        titles.pack(side="left", fill="y", pady=24)
        tk.Label(titles, text="OYTS", bg=COLOR_PRU_BLUE, fg="#ffffff",
                 font=title_font).pack(anchor="w")
        tk.Label(titles, text="Otonom Yangın Tespit Sistemi",
                 bg=COLOR_PRU_BLUE, fg="#dbeafe",
                 font=brand_font).pack(anchor="w")
        tk.Label(titles, text="Piri Reis Üniversitesi  •  BIP 2012",
                 bg=COLOR_PRU_BLUE, fg="#93c5fd",
                 font=tiny_font).pack(anchor="w", pady=(2, 0))

        # Sağ: versiyon rozeti
        ver = tk.Frame(hero, bg=COLOR_PRU_BLUE)
        ver.pack(side="right", padx=24, pady=24)
        tk.Label(ver, text=" v3.1.3 ", bg="#ffffff", fg=COLOR_PRU_BLUE,
                 font=brand_font, padx=8, pady=2).pack()

        # Durum kartı
        card = tk.Frame(self, bg=COLOR_CARD, padx=18, pady=14,
                        highlightbackground=COLOR_BORDER, highlightthickness=1)
        card.pack(fill="x", padx=24, pady=(20, 16))
        self.status_dot = tk.Label(card, text="●", fg=COLOR_MUTED,
                                   bg=COLOR_CARD, font=("Helvetica", 18))
        self.status_dot.pack(side="left")
        self.status_text = tk.Label(card, text="Sistem kapalı",
                                    font=status_font, bg=COLOR_CARD,
                                    fg=COLOR_TEXT, padx=8)
        self.status_text.pack(side="left")
        self.open_btn = tk.Button(card, text="🌐 Tarayıcıyı Aç",
                                  command=self._open_browser,
                                  state="disabled", relief="flat", bd=0,
                                  bg="#e2e8f0", activebackground="#cbd5e1",
                                  fg=COLOR_TEXT, padx=12, pady=6, cursor="hand2")
        self.open_btn.pack(side="right")

        # Action buttons (3 large)
        actions = tk.Frame(self, bg=COLOR_BG, padx=24, pady=0)
        actions.pack(fill="x", pady=(0, 8))
        for i in range(3):
            actions.columnconfigure(i, weight=1, uniform="btn")

        self.cam_btn  = self._big_button(actions, "📷  Kameralı Başlat",
                                         COLOR_BTN_CAM, self._on_webcam, btn_font)
        self.sim_btn  = self._big_button(actions, "🎬  Simülasyon",
                                         COLOR_BTN_SIM, self._on_synthetic, btn_font)
        self.stop_btn = self._big_button(actions, "⏹  Durdur",
                                         COLOR_BTN_STOP, self._on_stop, btn_font)
        self.cam_btn.grid (row=0, column=0, sticky="ew", padx=(0, 6))
        self.sim_btn.grid (row=0, column=1, sticky="ew", padx=6)
        self.stop_btn.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        # Secondary actions
        sec = tk.Frame(self, bg=COLOR_BG, padx=24, pady=10)
        sec.pack(fill="x")
        self._small_button(sec, "🔧 Sistem Kontrolü", self._on_doctor).pack(side="left")
        self._small_button(sec, "📂 Log Klasörünü Aç", self._open_logs).pack(side="left", padx=8)

        # Log panel
        log_card = tk.Frame(self, bg=COLOR_CARD, padx=12, pady=10,
                            highlightbackground=COLOR_BORDER, highlightthickness=1)
        log_card.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        tk.Label(log_card, text="Durum / Olaylar", font=sub_font,
                 bg=COLOR_CARD, fg=COLOR_MUTED).pack(anchor="w", pady=(0, 4))

        self.log_text = tk.Text(log_card, height=10, wrap="word",
                                bg="#0f172a", fg="#e2e8f0", font=log_font,
                                relief="flat", padx=10, pady=8,
                                insertbackground="#e2e8f0")
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")

        # Footer (live.html ile aynı kredi satırı)
        footer = tk.Frame(self, bg=COLOR_BG)
        footer.pack(fill="x", padx=24, pady=(4, 12))
        tk.Label(footer,
                 text="Piri Reis Üniversitesi  •  BIP 2012  •  "
                      "Sema Nur Işık & Efe Düzçay",
                 font=tiny_font, bg=COLOR_BG, fg=COLOR_MUTED
                 ).pack(side="left")

    def _big_button(self, parent, text, color, command, font):
        return tk.Button(parent, text=text, command=command,
                         bg=color, fg="white", font=font,
                         activebackground=color, activeforeground="white",
                         relief="flat", bd=0, padx=8, pady=18, cursor="hand2",
                         highlightthickness=0)

    def _small_button(self, parent, text, command):
        return tk.Button(parent, text=text, command=command,
                         bg="#eef2ff", fg=COLOR_PRU_BLUE,
                         activebackground="#dbeafe",
                         activeforeground=COLOR_PRU_DARK,
                         relief="flat", bd=0,
                         padx=14, pady=8, cursor="hand2",
                         highlightthickness=0)

    @staticmethod
    def _draw_gradient(canvas: tk.Canvas, height: int,
                       c1: str, c2: str, width: int | None = None) -> None:
        """Yatay gradient (sol → sağ). Ucuz: 60 dikey şerit."""
        w = width if (width and width > 50) else (canvas.winfo_width() or 720)
        if w < 50:
            w = 720
        r1, g1, b1 = canvas.winfo_rgb(c1)
        r2, g2, b2 = canvas.winfo_rgb(c2)
        steps = 60
        for i in range(steps):
            t = i / (steps - 1)
            r = int(r1 + (r2 - r1) * t) >> 8
            g = int(g1 + (g2 - g1) * t) >> 8
            b = int(b1 + (b2 - b1) * t) >> 8
            x0 = int(i * w / steps)
            x1 = int((i + 1) * w / steps) + 1
            canvas.create_rectangle(x0, 0, x1, height,
                                    fill=f"#{r:02x}{g:02x}{b:02x}",
                                    outline="")

    # Handlers
    def _on_webcam(self):    self._start_mode("webcam")
    def _on_synthetic(self): self._start_mode("synthetic")

    def _on_stop(self):
        self._set_buttons_running(False)
        self._log("• Durduruluyor...")
        threading.Thread(target=self.ctrl.stop, daemon=True).start()

    def _on_doctor(self):
        self._log("• Sistem kontrolü çalıştırılıyor...")
        threading.Thread(
            target=lambda: self.ctrl.run_doctor("any"),
            daemon=True,
        ).start()

    def _open_browser(self):
        webbrowser.open(FRONTEND_URL)

    def _open_logs(self):
        try:
            if IS_MACOS:
                subprocess.run(["open", str(LOG_DIR)])
            elif IS_WINDOWS:
                subprocess.run(["explorer", str(LOG_DIR)])
            else:
                subprocess.run(["xdg-open", str(LOG_DIR)])
        except Exception as e:
            self._log(f"Log klasörü açılamadı: {e}")

    def _start_mode(self, source: str):
        self._set_buttons_running(True)
        self._update_status("starting", source)
        self.ctrl.start(
            source,
            on_ready=lambda src: self.after(0, self._on_ready, src),
            on_failed=lambda msg: self.after(0, self._on_failed, msg),
        )

    def _on_ready(self, source: str):
        self._update_status("running", source)
        self.open_btn.configure(state="normal")
        webbrowser.open(FRONTEND_URL)

    def _on_failed(self, msg: str):
        self._update_status("stopped", None)
        self._set_buttons_running(False)
        self._log(f"✗ {msg}")

    # Status display
    def _update_status(self, state: str, source: str | None):
        if state == "running":
            self.status_dot.configure(fg=COLOR_OK)
            label = "Webcam" if source == "webcam" else "Simülasyon"
            self.status_text.configure(text=f"Çalışıyor — {label}",
                                       fg=COLOR_TEXT)
        elif state == "starting":
            self.status_dot.configure(fg=COLOR_WARN)
            self.status_text.configure(text="Başlatılıyor...", fg=COLOR_TEXT)
        elif state == "orphan":
            self.status_dot.configure(fg=COLOR_WARN)
            self.status_text.configure(
                text="Backend çalışıyor (başka pencereden) — Durdur ile temizle",
                fg=COLOR_TEXT)
        else:
            self.status_dot.configure(fg=COLOR_MUTED)
            self.status_text.configure(text="Sistem kapalı", fg=COLOR_TEXT)

    def _set_buttons_running(self, running: bool):
        state = "disabled" if running else "normal"
        self.cam_btn.configure(state=state)
        self.sim_btn.configure(state=state)
        # Durdur her zaman aktif

    # Logging (thread-safe queue)
    def _enqueue_log(self, msg: str):
        self.log_queue.put(msg)

    def _log(self, msg: str):
        self.log_queue.put(msg)

    def _poll_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert("end", msg + "\n")
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(120, self._poll_log_queue)

    # Background health poll
    def _poll_status(self):
        def worker():
            status = self.ctrl.health_check()
            self.after(0, self._reflect_status, status)
        threading.Thread(target=worker, daemon=True).start()
        self.after(3000, self._poll_status)

    def _reflect_status(self, status: str):
        if status.startswith("running:"):
            src = status.split(":", 1)[1]
            # Sadece durum değiştiyse güncelle (gereksiz redraw'a karşı)
            if self.status_text.cget("text") != \
               f"Çalışıyor — {'Webcam' if src == 'webcam' else 'Simülasyon'}":
                self._update_status("running", src)
                self.open_btn.configure(state="normal")
                self._set_buttons_running(True)
        elif status == "orphan":
            self._update_status("orphan", None)
            self.open_btn.configure(state="normal")
        else:
            if self.status_dot.cget("fg") not in (COLOR_MUTED, COLOR_WARN):
                self._update_status("stopped", None)
                self.open_btn.configure(state="disabled")
                self._set_buttons_running(False)

    # Close
    def _on_close(self):
        # Pencere kapanırken backend'i durdur (kullanıcı şaşırmasın)
        try:
            self.ctrl.stop(silent=True)
        finally:
            self.destroy()


def main():
    app = LauncherUI()
    # Tk NSApplication'ı oluşturduktan SONRA appearance'ı light'a çevir
    _force_macos_light_appearance()
    app.mainloop()


if __name__ == "__main__":
    main()
