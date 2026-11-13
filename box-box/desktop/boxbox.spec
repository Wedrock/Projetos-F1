# PyInstaller spec do Box Box para PC.
# Rode a partir de box-box/desktop depois de compilar o frontend
# (frontend/out). Veja build-windows.ps1.
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent          # box-box/
BACKEND = ROOT / "backend"
STATIC = ROOT / "frontend" / "out"

if not (STATIC / "index.html").is_file():
    raise SystemExit("Compile o frontend antes: cd frontend && npm ci && npm run build")

datas = [
    (str(STATIC), "static"),
    (str(BACKEND / "data"), "backend/data"),   # calendários e pit loss iniciais
]
binaries = []

def backend_modules(pkg):
    # Os módulos do backend, listados pelos arquivos (sem importar nada aqui).
    return [pkg] + [f"{pkg}.{f.stem}" for f in (BACKEND / pkg).glob("*.py") if f.stem != "__init__"]


hiddenimports = (
    backend_modules("routers")
    + backend_modules("services")
    + backend_modules("models")
    + collect_submodules("uvicorn")
    + ["main", "app_config", "auth", "websockets.legacy", "websockets.asyncio"]
)

# Pacotes com dados, DLLs ou imports dinâmicos
for pkg in ("fastf1", "faster_whisper", "ctranslate2", "av", "pillow_heif",
            "webview", "clr_loader", "pythonnet", "pystray", "pywebpush", "py_vapid",
            "tokenizers", "onnxruntime"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(Path(SPECPATH) / "launcher.py")],
    pathex=[str(BACKEND)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "boto3", "botocore", "s3transfer"],
    noarchive=False,
)
pyz = PYZ(a.pure)

icon = str(Path(SPECPATH) / "boxbox.ico")
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="BoxBox",
    console=False,            # sem janela de terminal
    icon=icon if Path(icon).is_file() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="BoxBox", upx=False)
