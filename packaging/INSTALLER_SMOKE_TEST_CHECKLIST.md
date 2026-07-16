# LocalFileConverter Installer Smoke Test Checklist

## Installation

- Installer starts.
- No console window appears.
- Version shown by installer is correct.
- Custom install location works.
- Start Menu shortcut exists.
- Desktop shortcut works when selected.
- App can be launched from the final installer page.

## Application

- Image to image conversion.
- PDF to image conversion.
- Image to PDF conversion.
- Batch conversion.
- Multiple images to one PDF.
- Light, dark, and system themes.
- Settings persist after restart.
- Logging writes to `%LOCALAPPDATA%\LocalFileConverter\logs`.
- Drag-and-drop works.
- Office conversions show clear behavior based on installed local tools.

## Optional LibreOffice Download

### A. LibreOffice is already installed

- Installer does not show an unnecessary LibreOffice download offer.
- Installer does not download `LibreOffice_26.2.4_Win_x86-64.msi`.
- Existing LibreOffice installation is not changed or upgraded automatically.
- DOCX, PPTX and XLSX to PDF conversions work after install.

### B. LibreOffice is not installed and the user accepts

- Installer shows an optional checkbox:
  `Download and install LibreOffice 26.2.4 (approximately 355 MB)`.
- Installer explains that LibreOffice is only required for DOCX, PPTX and XLSX to PDF conversion.
- MSI downloads from the pinned HTTPS Document Foundation URL.
- Download progress is visible and can be cancelled.
- SHA-256 is verified before `msiexec` starts the MSI.
- LibreOffice MSI opens interactively.
- Installer waits for the LibreOffice MSI to finish.
- Downloaded MSI is removed from the temporary folder.
- After installation, `soffice.exe` is found automatically.

### C. LibreOffice is not installed and the user declines or cancels

- Local File Converter installs normally.
- No LibreOffice MSI is run without explicit user consent.
- Image and PDF conversions still work.
- Office conversions show a clear message that LibreOffice is required.
- User can install LibreOffice later or choose `soffice.exe` manually in app settings.

## Upgrade

- Install the same version over an existing installation.
- Later, install a newer version over an older version.
- AppId stays fixed.
- User settings remain.
- User output files remain.

## Uninstall

- Application files are removed.
- Start Menu shortcuts are removed.
- Desktop shortcut is removed if installer created it.
- Source/output documents remain.
- Microsoft Office remains.
- LibreOffice remains.
- Arbitrary user folders are not deleted.
- QSettings and runtime logs remain for now.

## Safety

- Installer is currently unsigned.
- Windows SmartScreen may show Unknown Publisher.
- Do not disable antivirus.
- Do not use any bypass techniques.

## Second Machine

- Windows 10/11 x64.
- Python not installed.
- Install and launch app.
- Test on a machine without Office tools.
- Test on a machine with only Microsoft Office, if that engine exists.
- Test on a machine with only LibreOffice.
- Test Windows scaling 125% and 150%.
