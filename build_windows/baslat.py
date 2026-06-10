"""Baslat.exe — Windows tek-dosya giriş noktası.

Çift tıklandığında Tkinter launcher penceresini açar (python/launcher.py).
Aynı .exe, ek argümanlarla çalıştırıldığında launcher tarafından
arka plan servisleri (web_app + frontend serve) olarak da kullanılır:

    Baslat.exe                            → Tkinter launcher (varsayılan)
    Baslat.exe --oyts-mode=webapp ...     → python/web_app.py main()
    Baslat.exe --oyts-mode=serve PORT     → web/serve.py main()

PyInstaller frozen modunda `sys.executable` = Baslat.exe olduğu için
launcher.py subprocess'leri yine kendi .exe'sine "--oyts-mode=..." ile
çağırır. Geliştirme modunda (python build_windows/baslat.py) doğrudan
launcher penceresi gelir.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _resource_root() -> Path:
    """Bundle kökü — frozen'da _MEIPASS, kaynak modda repo kökü."""
    if _is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent.parent


def _prepare_sys_path(root: Path) -> None:
    for sub in ("python", "web"):
        p = str(root / sub)
        if p not in sys.path:
            sys.path.insert(0, p)


def _run_webapp(root: Path) -> None:
    _prepare_sys_path(root)
    os.environ.setdefault("OPENCV_AVFOUNDATION_SKIP_AUTH", "1")
    import web_app
    web_app.main()


def _run_serve(root: Path) -> None:
    web_dir = root / "web"
    # serve.py kendi __file__.parent'ini WEB_DIR olarak kullanıyor → spec'ten yükle
    spec = importlib.util.spec_from_file_location(
        "oyts_serve", str(web_dir / "serve.py"))
    if spec is None or spec.loader is None:
        raise SystemExit(f"serve.py yüklenemedi: {web_dir / 'serve.py'}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def _run_launcher(root: Path) -> None:
    _prepare_sys_path(root)
    import launcher  # python/launcher.py
    launcher.main()


def main() -> None:
    root = _resource_root()

    # Mode dispatch — ilk argv "--oyts-mode=..." ise alt-servis modu
    mode = None
    if len(sys.argv) > 1 and sys.argv[1].startswith("--oyts-mode="):
        mode = sys.argv[1].split("=", 1)[1]
        # Mode bayrağını kaldır, kalan argümanlar alt-servisin main()'ine kalsın
        sys.argv = [sys.argv[0]] + sys.argv[2:]

    if mode == "webapp":
        _run_webapp(root)
    elif mode == "serve":
        _run_serve(root)
    elif mode is None:
        _run_launcher(root)
    else:
        print(f"[ERR] Bilinmeyen mod: {mode}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
