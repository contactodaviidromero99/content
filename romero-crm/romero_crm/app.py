from __future__ import annotations

import argparse
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

from . import APP_NAME, APP_VERSION
from .config import Settings, data_dir
from .engine import Engine
from .server import AppServer
from .storage import Storage

ICON_PATH = Path(__file__).parent / "web" / "img" / "icon.png"


def _macos_identity() -> None:
    if sys.platform != "darwin":
        return
    try:
        from Foundation import NSBundle

        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = APP_NAME
    except Exception:
        pass
    try:
        from AppKit import NSApplication, NSImage

        if ICON_PATH.exists():
            image = NSImage.alloc().initWithContentsOfFile_(str(ICON_PATH))
            if image is not None:
                NSApplication.sharedApplication().setApplicationIconImage_(image)
    except Exception:
        pass


def open_window(url: str) -> bool:
    try:
        import webview
    except Exception:
        return False
    try:
        try:
            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        except Exception:
            pass
        _macos_identity()
        webview.create_window(
            APP_NAME,
            url + "?shell=desktop",
            width=1440,
            height=920,
            min_size=(1080, 700),
            background_color="#0d0d0d",
            text_select=True,
        )
        webview.start()
        return True
    except Exception:
        traceback.print_exc()
        return False


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="romero_crm", description=f"{APP_NAME}: radar de tendencias en España")
    parser.add_argument("--web", action="store_true", help="abrir en el navegador en vez de en una ventana propia")
    parser.add_argument("--port", type=int, default=0, help="puerto local (por defecto, uno libre)")
    parser.add_argument("--demo", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--serve-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = data_dir()
    demo_loader = None
    if args.demo:
        from .demo import DemoData

        root = root / "demo"
        root.mkdir(parents=True, exist_ok=True)
        (root / "cache").mkdir(exist_ok=True)
        demo_loader = DemoData().load

    settings = Settings(root / "settings.json")
    storage = Storage(root)
    engine = Engine(settings, storage, demo_loader)
    server = AppServer(engine, settings, storage, port=args.port or (8765 if args.web else 0))
    server.start()
    engine.start()

    print(f"\n  {APP_NAME} {APP_VERSION}")
    print(f"  Datos guardados en: {root}")
    print(f"  Dirección local:    {server.url}\n")

    stop = threading.Event()
    try:
        if args.serve_only:
            while not stop.wait(0.5):
                pass
        elif args.web or not open_window(server.url):
            if not args.web:
                print("  No se pudo abrir la ventana propia; abriendo en tu navegador.")
            webbrowser.open(server.url)
            print("  Para cerrar Romero CRM, pulsa Ctrl+C en esta ventana.\n")
            while not stop.wait(0.5):
                pass
    except KeyboardInterrupt:
        pass
    finally:
        engine.stop()
        server.stop()
