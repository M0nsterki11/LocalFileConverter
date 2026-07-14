# Future LibreOffice Installer Setup

LibreOffice download/install is disabled in phase 11A.

The configuration file is:

```text
packaging/libreoffice_dependency.json
```

Before enabling it, Borna must provide and test:

- exact LibreOffice version
- official x64 download URL for that exact version
- SHA-256 hash of the installer
- expected `soffice.exe` path

Required config shape:

```json
{
  "ENABLED": true,
  "VERSION": "exact-version",
  "ARCHITECTURE": "x64",
  "DOWNLOAD_URL": "official-version-pinned-url",
  "SHA256": "expected-sha256",
  "EXPECTED_SOFFICE_PATH": "C:\\Program Files\\LibreOffice\\program\\soffice.exe"
}
```

Future behavior:

1. Detect whether LibreOffice is already installed.
2. If it exists, do not offer installation.
3. If it does not exist, ask whether to download and install the tested version.
4. The user may decline and still finish LocalFileConverter installation.
5. Download only from the official pinned URL.
6. Verify SHA-256 before running anything.
7. If the hash is wrong, do not run the downloaded file.
8. Internet failure must not break LocalFileConverter installation.
9. Do not modify Microsoft Office.
10. After installation, detect `soffice.exe` again.
11. If detection fails, explain that the path can be selected manually in the app.

Never use a "latest" URL. Full/offline installer remains a separate future task.
