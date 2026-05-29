from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID, uuid4
import os
import shutil
from pathlib import Path

from app.database import get_db
from app.dependencies.auth import get_current_seller
from app.models.seller import Seller
from app.models.product import Product
from app.models.sku import SKU
from app.schemas.common import ImageUploadResponse

router = APIRouter()

# Директория для загрузки изображений (в MVP — локальное хранилище)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

# Допустимые MIME-типы и их magic bytes
ALLOWED_TYPES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


def verify_magic_bytes(content: bytes, mime_type: str) -> bool:
    """Проверка magic bytes файла"""
    signatures = ALLOWED_TYPES.get(mime_type, [])
    for sig in signatures:
        if content.startswith(sig):
            return True
    return False


def check_entity_ownership(entity_id: Optional[str], entity_type: str, current_seller_id: UUID, db: Session):
    """Проверяет, что текущий продавец владеет entity"""
    if not entity_id:
        return True
    
    try:
        entity_uuid = UUID(entity_id)
    except ValueError:
        error_response("INVALID_REQUEST", f"Invalid {entity_type}_id format", 400)
    
    if entity_type == "PRODUCT":
        product = db.query(Product).filter(Product.id == entity_uuid).first()
        if not product or product.seller_id != current_seller_id:
            error_response("FORBIDDEN", "You don't own this product", 403)
    elif entity_type == "SKU":
        sku = db.query(SKU).join(Product).filter(SKU.id == entity_uuid).first()
        if not sku or sku.product.seller_id != current_seller_id:
            error_response("FORBIDDEN", "You don't own this SKU", 403)
    
    return True


@router.post("/", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_image(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: Optional[str] = Form(None),
    ordering: int = Form(0),
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """
    Загрузить файл изображения (multipart). Возвращает url + id.
    
    Соответствует спецификации:
    - URL: POST /api/v1/images
    - Авторизация: Bearer JWT
    - Проверка: размер ≤ 5 МБ, формат JPEG/PNG/WEBP, magic bytes
    """
    # Проверка типа entity_type
    if entity_type not in ("PRODUCT", "SKU"):
        error_response("INVALID_REQUEST", "entity_type must be PRODUCT or SKU", 400)
    
    # Проверка прав на entity (если передан)
    check_entity_ownership(entity_id, entity_type, current_seller.id, db)
    
    # Читаем содержимое файла
    content = file.file.read()
    file_size = len(content)
    
    # Проверка размера
    if file_size > MAX_FILE_SIZE:
        error_response("FILE_TOO_LARGE", "File size exceeds 5 MB limit", 413)
    
    # Проверка MIME-типа по magic bytes
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_TYPES:
        error_response("UNSUPPORTED_MEDIA_TYPE", f"Unsupported file type: {mime_type}", 415)
    
    if not verify_magic_bytes(content, mime_type):
        error_response("UNSUPPORTED_MEDIA_TYPE", "File content does not match declared type", 415)
    
    # Генерируем уникальное имя файла
    file_ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime_type, ".bin")
    
    image_id = uuid4()
    filename = f"{image_id}{file_ext}"
    file_path = UPLOAD_DIR / filename
    
    # Сохраняем файл
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Формируем URL (в MVP — относительный путь)
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    url = f"{base_url}/uploads/{filename}"
    
    # Возвращаем по спецификации
    return ImageUploadResponse(
        id=image_id,
        url=url,
        ordering=ordering,
        entity_type=entity_type,
        entity_id=UUID(entity_id) if entity_id else None
    )