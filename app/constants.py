APP_NAME = "MyFile Converter"
APP_VERSION = "0.5.0"
APP_ORGANIZATION = "LocalFileConverter"
APP_SETTINGS_APPLICATION_NAME = "Local File Converter"
GITHUB_REPOSITORY_URL = (
    "https://github.com/M0nsterki11/LocalFileConverter"
)

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

OFFICE_EXTENSIONS = {
    ".docx",
    ".pptx",
    ".xlsx",
}

PDF_EXTENSION = ".pdf"

SUPPORTED_INPUT_EXTENSIONS = {
    *IMAGE_EXTENSIONS,
    *OFFICE_EXTENSIONS,
    PDF_EXTENSION,
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
    "Supported files "
    "(*.jpg *.jpeg *.png *.webp *.pdf *.docx *.pptx *.xlsx);;"
    "Images (*.jpg *.jpeg *.png *.webp);;"
    "PDF files (*.pdf);;"
    "Office documents (*.docx *.pptx *.xlsx);;"
    "All files (*.*)"
)
