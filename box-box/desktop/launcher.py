"""Box Box para PC: abre o app numa janela própria, sem Docker.

Sobe o backend (FastAPI) num thread em 127.0.0.1 e mostra o frontend numa
janela nativa (WebView2 no Windows, via pywebview). Se a janela não puder ser
criada, abre o navegador padrão.

Pastas usadas (no Windows):
  %LOCALAPPDATA%\\BoxBox\\data   sessões baixadas, conta F1 TV, modelos Whisper
  %LOCALAPPDATA%\\BoxBox\\.env   configurações opcionais (mesmas chaves do .env.example)
  %LOCALAPPDATA%\\BoxBox\\boxbox.log

Opções:
  --browser   abre no navegador em vez da janela do app
  --port N    porta local (padrão 8765; se estiver ocupada, usa outra livre)
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "Box Box"
DEFAULT_PORT = 8765
HOST = "127.0.0.1"


def bundle_dir() -> Path:
    """Where the backend code, seed data and static frontend live."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # Running from source: box-box/desktop/launcher.py
    return Path(__file__).resolve().parent.parent


def static_dir() -> Path:
    """The compiled frontend (frontend/out when running from source)."""
    if getattr(sys, "frozen", False):
        return bundle_dir() / "static"
    return bundle_dir() / "frontend" / "out"


def app_home() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "BoxBox"


def setup_logging(home: Path) -> None:
    # A windowed .exe has no console: stdout/stderr are None and uvicorn's
    # logging would crash, so everything goes to a log file instead.
    if sys.stdout is None or sys.stderr is None:
        log = open(home / "boxbox.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log


def seed_data(src: Path, dest: Path) -> None:
    """Copy the bundled data files (calendars, pit loss) without overwriting."""
    if not src.is_dir():
        return
    for path in src.rglob("*"):
        if path.is_file():
            target = dest / path.relative_to(src)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)


def configure_env(home: Path, bundle: Path) -> None:
    data = home / "data"
    (data / "fastf1-cache").mkdir(parents=True, exist_ok=True)

    env_file = home / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False)

    os.environ.setdefault("DATA_DIR", str(data))
    os.environ.setdefault("FASTF1_CACHE_DIR", str(data / "fastf1-cache"))
    os.environ.setdefault("STORAGE_MODE", "local")
    os.environ["STATIC_DIR"] = str(static_dir())
    # Only this computer may reach the server.
    os.environ["ALLOWED_HOSTS"] = "localhost,127.0.0.1"

    seed_data(bundle / "backend" / "data", Path(os.environ["DATA_DIR"]))


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=1) as r:
            return r.status == 200 and b"ok" in r.read()
    except Exception:
        return False


def pick_port(preferred: int) -> int:
    if port_free(preferred):
        return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def start_server(port: int):
    import uvicorn

    backend = bundle_dir() / "backend"
    if backend.is_dir() and str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    os.chdir(os.environ["DATA_DIR"])

    from main import app  # noqa: E402  (needs the env set above)

    config = uvicorn.Config(app, host=HOST, port=port, log_level="info", ws="websockets")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="boxbox-server", daemon=True)
    thread.start()
    return server, thread


def wait_until_up(port: int, thread: threading.Thread, timeout: float = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not thread.is_alive():
            return False
        if already_running(port):
            return True
        time.sleep(0.25)
    return False


def show_error(message: str) -> None:
    print(message, file=sys.stderr)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
        except Exception:
            pass


def open_window(url: str) -> bool:
    """Show the app in a native window. Returns False if that isn't possible."""
    try:
        import webview
    except Exception:
        print("Janela do app indisponível (pywebview não carregou):", file=sys.stderr)
        traceback.print_exc()
        return False
    selftest = os.environ.get("BOXBOX_SELFTEST") == "1"
    try:
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        webview.settings["ALLOW_DOWNLOADS"] = True
        window = webview.create_window(APP_NAME, url, width=1440, height=900, min_size=(1024, 640))

        def on_loaded():
            print("Janela do app carregada.", flush=True)
            if selftest:
                threading.Timer(3, window.destroy).start()

        window.events.loaded += on_loaded
        icon = static_dir() / "icon-512.png"
        webview.start(private_mode=False, storage_path=str(app_home() / "webview"),
                      icon=str(icon) if icon.is_file() else None)
        return True
    except Exception:  # no WebView2 / GTK / Qt available
        print("Janela do app indisponível; abrindo no navegador:", file=sys.stderr)
        traceback.print_exc()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Box Box para PC")
    parser.add_argument("--browser", action="store_true", help="abrir no navegador")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-ui", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    setup_logging(home)

    # A second double-click just brings up the one that's already running.
    if already_running(args.port):
        url = f"http://localhost:{args.port}"
        if args.browser or not open_window(url):
            webbrowser.open(url)
        return 0

    print(f"--- Box Box iniciando {time.strftime('%Y-%m-%d %H:%M:%S')} "
          f"(Python {sys.version.split()[0]}, {sys.platform})", flush=True)
    configure_env(home, bundle_dir())
    port = pick_port(args.port)
    url = f"http://localhost:{port}"

    try:
        server, thread = start_server(port)
    except Exception as exc:
        show_error(f"Não foi possível iniciar o Box Box:\n{exc}\n\nVeja {home / 'boxbox.log'}")
        return 1

    if not wait_until_up(port, thread):
        show_error(f"O Box Box não iniciou.\nVeja os detalhes em {home / 'boxbox.log'}")
        return 1
    print(f"Box Box rodando em {url}")

    if args.no_ui:
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
    elif args.browser or not open_window(url):
        webbrowser.open(url)
        print("Feche esta janela (ou Ctrl+C) para encerrar o Box Box.")
        try:
            while thread.is_alive():
                thread.join(1)
        except KeyboardInterrupt:
            pass

    server.should_exit = True
    thread.join(10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
