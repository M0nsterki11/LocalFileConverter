APP_NAME = "Local File Converter"
APP_VERSION = "0.2.0"

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

PDF_EXTENSION = ".pdf"

SUPPORTED_INPUT_EXTENSIONS = {
    *IMAGE_EXTENSIONS,
    PDF_EXTENSION,
    ".docx",
    ".pptx",
    ".xlsx",
}

OUTPUT_FORMATS_BY_EXTENSION = {
    ".jpg": ["PNG", "WEBP", "PDF"],
    ".jpeg": ["PNG", "WEBP", "PDF"],
    ".png": ["JPG", "WEBP", "PDF"],
    ".webp": ["JPG", "PNG", "PDF"],
    ".pdf": ["PNG", "JPG"],
    ".docx": ["PDF"],
    ".pptx": ["PDF"],
    ".xlsx": ["PDF"],
}

DISPLAY_FORMAT_NAMES = {
    ".jpg": "JPG",
    ".jpeg": "JPG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".pptx": "PPTX",
    ".xlsx": "XLSX",
}

FILE_DIALOG_FILTER = (
    "Podržane datoteke "
    "(*.jpg *.jpeg *.png *.webp *.pdf *.docx *.pptx *.xlsx);;"
    "Slike (*.jpg *.jpeg *.png *.webp);;"
    "PDF datoteke (*.pdf);;"
    "Office dokumenti (*.docx *.pptx *.xlsx);;"
    "Sve datoteke (*.*)"
)