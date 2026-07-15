# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


project_root = Path(SPECPATH)
build_mode = os.environ.get("LFC_BUILD_MODE", "release").strip().lower()
build_target = os.environ.get("LFC_BUILD_TARGET", "onedir").strip().lower()

is_debug = build_mode == "debug"
is_onefile = build_target == "onefile"

app_name = (
    "LocalFileConverterOnefile"
    if is_onefile
    else "LocalFileConverterDebug"
    if is_debug
    else "LocalFileConverter"
)

resources_path = project_root / "resources"
icon_path = project_root / "resources" / "app_icon.ico"
version_path = project_root / "packaging" / "windows_version_info.txt"

datas = []

if resources_path.exists():
    datas.append((str(resources_path), "resources"))

if not icon_path.exists():
    raise FileNotFoundError(f"Application icon is required: {icon_path}")

icon = str(icon_path)
version = str(version_path) if version_path.exists() else None

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tests",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

if is_onefile:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=app_name,
        debug=is_debug,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=is_debug,
        icon=icon,
        version=version,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=app_name,
        debug=is_debug,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=is_debug,
        icon=icon,
        version=version,
    )

    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=app_name,
    )
