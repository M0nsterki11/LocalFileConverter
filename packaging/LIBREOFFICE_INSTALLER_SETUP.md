# LibreOffice Installer Setup

LibreOffice download/install is enabled as an optional online step in phase 11B.
The Local File Converter setup remains a small online installer and does not
embed the LibreOffice MSI.

The configuration file is:

```text
packaging/libreoffice_dependency.json
```

Pinned LibreOffice package:

- Version: `26.2.4`
- Architecture: Windows x86-64
- Filename: `LibreOffice_26.2.4_Win_x86-64.msi`
- URL: `https://download.documentfoundation.org/libreoffice/stable/26.2.4/win/x86_64/LibreOffice_26.2.4_Win_x86-64.msi`
- Expected size: `372539392` bytes
- SHA-256: `202f26cda071c5aa4996a5a28412fddceb3891dceb0366982c62650456c0730f`

Required config shape:

```json
{
  "ENABLED": true,
  "VERSION": "26.2.4",
  "ARCHITECTURE": "x64",
  "FILENAME": "LibreOffice_26.2.4_Win_x86-64.msi",
  "DOWNLOAD_URL": "https://download.documentfoundation.org/libreoffice/stable/26.2.4/win/x86_64/LibreOffice_26.2.4_Win_x86-64.msi",
  "SHA256": "202f26cda071c5aa4996a5a28412fddceb3891dceb0366982c62650456c0730f",
  "EXPECTED_FILE_SIZE": 372539392,
  "EXPECTED_SOFFICE_PATH": "C:\\Program Files\\LibreOffice\\program\\soffice.exe"
}
```

Installer behavior:

1. Detect whether LibreOffice is already installed.
2. If it exists, do not offer installation.
3. If it does not exist, show an unchecked optional download checkbox.
4. The user may decline and still finish LocalFileConverter installation.
5. Download only from the official pinned URL.
6. Verify SHA-256 before running anything.
7. If the hash is wrong, do not run the downloaded file.
8. Internet failure must not break LocalFileConverter installation.
9. Do not modify Microsoft Office.
10. After installation, detect `soffice.exe` again.
11. If detection fails, explain that the path can be selected manually in the app.

Never use a "latest" URL. Full/offline installer remains a separate future task.
