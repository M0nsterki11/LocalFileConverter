Local File Converter
====================

Verzija: 0.5.0

Local File Converter je Windows desktop aplikacija napravljena u Pythonu
i PySide6. Obrada datoteka odvija se lokalno na racunalu; dokumenti se
ne salju na internetski servis.

Originalne datoteke se ne mijenjaju. Rezultati se najprije spremaju
kao privremeni `.part` zapis ili privremena mapa, a zavrsni naziv se
objavljuje tek nakon uspjesnog dovrsetka konverzije. Ako konverzija
ne uspije ili je korisnik prekine, aplikacija brise samo svoje
privremene nepotpune rezultate.

Podrzane konverzije
-------------------

- JPG, PNG i WEBP konverzije slika
- Slike u PDF
- PDF stranice u JPG ili PNG
- Sve PDF stranice ili odabrani rasponi stranica
- Vise PDF stranica kao mapa ili ZIP arhiva
- Automatski ZIP kada renderirane PDF stranice predu 100 MB
- DOCX, PPTX i XLSX u PDF kroz lokalni Office alat
- Grupna konverzija sa statusom i napretkom po datoteci
- Vise slika spojeno u jedan PDF

Office konverzija
-----------------

Office konverzija koristi lokalno instalirane alate. Trenutna
implementacija podrzava LibreOffice kroz `soffice.exe`; aplikacija ga
moze pronaci automatski ili koristiti rucno odabranu putanju.

Logovi i greske
---------------

Aplikacija sprema lokalni tehnicki log za dijagnostiku gresaka:

`%LOCALAPPDATA%\LocalFileConverter\logs\app.log`

Ako `%LOCALAPPDATA%` nije dostupan, koristi se fallback u korisnickom
home direktoriju:

`%USERPROFILE%\AppData\Local\LocalFileConverter\logs`

Log se rotira na 2 MB i cuva do 5 backup datoteka. Log ne sadrzi
sadrzaj dokumenata, slika, OCR tekst ni lozinke. Mapu s logovima mozes
otvoriti iz Settings ili About dijaloga.

Kod greske korisnik vidi kratku poruku na hrvatskom, a tehnicki detalji
i traceback spremaju se u log. Jedna neuspjela stavka u batch konverziji
ne zaustavlja ostale stavke.

Pokretanje iz sourcea
---------------------

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Development testovi
-------------------

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Building the Windows executable
-------------------------------

Primary release format je PyInstaller ONEDIR. Installer ce doci u
sljedecoj fazi; za sada se distribuira cijeli folder iz `dist`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Debug ONEDIR build s konzolom:

```powershell
.\scripts\build_debug.ps1
```

Release ONEDIR build bez konzole:

```powershell
.\scripts\build_release.ps1
```

Zavrsni EXE nalazi se ovdje:

```text
dist\LocalFileConverter\LocalFileConverter.exe
```

Za pokretanje na drugom racunalu kopiraj cijeli folder:

```text
dist\LocalFileConverter\
```

Nemoj kopirati samo `.exe`, jer ONEDIR build treba `_internal`,
PySide6 DLL-ove, Qt plugine i runtime resurse.

Eksperimentalni ONEFILE build:

```powershell
.\scripts\build_onefile.ps1
```

ONEFILE nije preporuceni release format dok se ne potvrdi stabilnost.
Microsoft Office i LibreOffice se ne ugraduju u build; aplikacija koristi
lokalne instalacije ako postoje. Build trenutno nije digitalno potpisan,
pa Windows SmartScreen moze prikazati upozorenje.

Screenshot
----------

Screenshot placeholder: ovdje dodati screenshot aplikacije kada bude
snimljen za repozitorij.
