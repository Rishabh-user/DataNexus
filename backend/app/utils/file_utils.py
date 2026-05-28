import hashlib
import re
import uuid
from pathlib import Path

from app.core.config import settings

ALLOWED_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".pptx",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif",
}

MIME_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
}


def sanitize_filename(filename: str) -> str:
    name = re.sub(r'[^\w\s\-.]', '', filename)
    name = re.sub(r'\s+', '_', name)
    return name[:255]


def get_file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def is_allowed_file(filename: str) -> bool:
    return get_file_extension(filename) in ALLOWED_EXTENSIONS


def get_mime_type(filename: str) -> str:
    ext = get_file_extension(filename)
    return MIME_TYPE_MAP.get(ext, "application/octet-stream")


def compute_file_hash(file_path: str | Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def generate_storage_path(user_id: int, filename: str) -> Path:
    safe_name = sanitize_filename(filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    user_dir = settings.upload_path / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / unique_name


def get_file_type(filename: str) -> str:
    ext = get_file_extension(filename)
    type_map = {
        ".pdf": "pdf",
        ".xlsx": "excel", ".xls": "excel",
        ".csv": "csv",
        ".docx": "docx",
        ".pptx": "pptx",
        ".png": "image", ".jpg": "image", ".jpeg": "image",
        ".tiff": "image", ".bmp": "image", ".gif": "image",
    }
    return type_map.get(ext, "unknown")
