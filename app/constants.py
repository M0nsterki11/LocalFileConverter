APP_NAME = "Local File Converter"
APP_VERSION = "0.1.0"

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

SUPPORTED_INPUT_EXTENSIONS = {
    *IMAGE_EXTENSIONS,
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
}

OUTPUT_FORMATS_BY_EXTENSION = {
    ".jpg": ["PNG", "WEBP"],
    ".jpeg": ["PNG", "WEBP"],
    ".png": ["JPG", "WEBP"],
    ".webp": ["JPG", "PNG"],
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