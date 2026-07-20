# MyFileConverter ONEDIR Smoke Test Checklist

Run these checks from `dist\MyFileConverter\MyFileConverter.exe`.
Copy the whole `dist\MyFileConverter\` folder when testing on another PC.

## Startup

- Starts on Windows 10/11 x64 without Python in `PATH`.
- Release build opens without a console window.
- App icon appears when `resources\app_icon.ico` exists.
- About shows the current `APP_VERSION`.
- Light, dark, and system themes work.
- Restart keeps QSettings preferences.

## Images

- JPG to PNG.
- PNG to JPG.
- Transparent PNG conversion keeps expected background behavior.
- WEBP conversions.
- Image quality slider affects JPG/WEBP output.

## PDF

- PDF to PNG.
- PDF to JPG.
- Selected page ranges.
- DPI choices.
- Folder result for multiple pages.
- ZIP result for multiple pages.
- Automatic ZIP over the 100 MB threshold.
- Image to PDF.
- Multiple images to one PDF.

## Batch

- Multiple mixed files.
- One corrupted item does not stop later items.
- Failed item can be retried with "Retry failed".
- Cancellation during a large conversion.

## Office

- DOCX to PDF prefers Microsoft Word when Word is installed and usable.
- PPTX to PDF prefers Microsoft PowerPoint when PowerPoint is installed and usable.
- XLSX to PDF prefers Microsoft Excel when Excel is installed and usable.
- Detection is per application; one missing Office app does not disable the others.
- A Microsoft Office COM failure uses LibreOffice as a fallback when available.
- LibreOffice-only conversion works without Microsoft Office.
- Manual LibreOffice `soffice.exe` path.
- Missing Office/LibreOffice gives a clear user error.
- Success, failure, and cancellation do not leave app-owned Office processes running.
- Cancellation does not close user-owned Office/LibreOffice processes.

## Safety

- Existing result is not overwritten.
- Log is created in `%LOCALAPPDATA%\LocalFileConverter\logs`.
- Output is not written into the bundle folder unless explicitly selected.
- Failed conversion does not leave a final incomplete result.
- Closing while converting asks for cancellation confirmation.
- Drag-and-drop works.
- Open output folder works.

## Second Machine

- Python not installed.
- No Microsoft Office installed.
- No LibreOffice installed.
- Only Microsoft Office installed.
- Partial Microsoft Office install, such as Word without Excel.
- Only LibreOffice installed.
- Windows scaling at 125% or 150%.

## Notes

- This build is not digitally signed yet.
- Do not attempt to bypass Windows SmartScreen or antivirus warnings.
