Local File Converter
====================

Version: 0.5.0

Local File Converter is a Windows desktop application built with Python and
PySide6. File processing happens locally on the computer; documents are not
sent to an internet service.

Original files are not modified. Results are first written as temporary `.part`
files or temporary folders, and the final name is published only after a
successful conversion. If conversion fails or the user cancels it, the app
removes only its own incomplete temporary results.

Supported Conversions
---------------------

- JPG, PNG, and WEBP image conversions
- Images to PDF
- PDF pages to JPG or PNG
- All PDF pages or selected page ranges
- Multiple PDF pages as a folder or ZIP archive
- Automatic ZIP output when rendered PDF pages exceed 100 MB
- DOCX, PPTX, and XLSX to PDF through a local Office tool
- Batch conversion with per-file status and progress
- Multiple images merged into one PDF

Office Conversion
-----------------

Office conversion uses locally installed tools. The current implementation
supports LibreOffice through `soffice.exe`; the app can detect it automatically
or use a manually selected path.

Localization
------------

English is the default source and UI language. The app does not automatically
switch based on the Windows display language. Users can choose English or
Croatian in Settings, and the change is applied at runtime without restarting.

Logs and Errors
---------------

The app writes a local technical log for error diagnostics:

`%LOCALAPPDATA%\LocalFileConverter\logs\app.log`

If `%LOCALAPPDATA%` is not available, it falls back to the user's home folder:

`%USERPROFILE%\AppData\Local\LocalFileConverter\logs`

The log rotates at 2 MB and keeps up to 5 backup files. It does not contain
document contents, image contents, OCR text, or passwords. The log folder can be
opened from Settings or About.

When an error occurs, the user sees a short message and technical details are
saved to the log. One failed item in a batch conversion does not stop later
items.

Running From Source
-------------------

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Development Tests
-----------------

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Translations
------------

Compile Qt translation resources before release packaging:

```powershell
.\scripts\build_translations.ps1
```

The Croatian translation source is:

```text
translations\local_file_converter_hr.ts
```

The compiled runtime file is:

```text
translations\local_file_converter_hr.qm
```

Building the Windows Executable
-------------------------------

The primary release format is PyInstaller ONEDIR. Distribute the whole folder
from `dist`, not only the executable.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Debug ONEDIR build with a console:

```powershell
.\scripts\build_debug.ps1
```

Release ONEDIR build without a console:

```powershell
.\scripts\build_release.ps1
```

The final EXE is here:

```text
dist\LocalFileConverter\LocalFileConverter.exe
```

For another computer, copy the entire folder:

```text
dist\LocalFileConverter\
```

Do not copy only `.exe`; the ONEDIR build needs `_internal`, PySide6 DLLs, Qt
plugins, runtime resources, and translations.

Experimental ONEFILE build:

```powershell
.\scripts\build_onefile.ps1
```

ONEFILE is not the recommended release format until stability is confirmed.
Microsoft Office and LibreOffice are not embedded in the app build; the app
uses local installations when available. The build is not digitally signed yet,
so Windows SmartScreen may show a warning.

Windows Installer
-----------------

The installer is built with Inno Setup and uses the stable ONEDIR build from:

```text
dist\LocalFileConverter\
```

Install Inno Setup 6 from the official website, then run:

```powershell
.\scripts\build_installer.ps1
```

If the ONEDIR build is already fresh, the app build can be skipped:

```powershell
.\scripts\build_installer.ps1 -SkipAppBuild
```

The final Setup EXE is here:

```text
installer_output\LocalFileConverter_Setup_0.5.0_x64.exe
```

The installer is per-user and installs the app into:

```text
%LOCALAPPDATA%\Programs\LocalFileConverter
```

Microsoft Office is not included in the installer. Optional LibreOffice download
is controlled by `packaging\libreoffice_dependency.json`, which must keep the
pinned version, official URL, expected size, and SHA-256.

The current installer is not digitally signed. Windows SmartScreen may show
Unknown publisher. `installer_output/` is not committed; Setup EXE files are
published later as GitHub Release assets.

App Screenshot (not added yet)
----------

