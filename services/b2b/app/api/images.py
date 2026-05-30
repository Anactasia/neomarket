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

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/webp": [b"RIFF"],
}

MAX_FILE_SIZE = 5 * 1024 * 1024


def error_response(code: str, message: str, status_code: int = 400):
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message}
    )


def verify_magic_bytes(content: bytes, mime_type: str) -> bool:
    signatures = ALLOWED_TYPES.get(mime_type, [])
    for sig in signatures:
        if content.startswith(sig):
            return True
    return False


def check_entity_ownership(
    entity_id: UUID,
    entity_type: str,
    current_seller_id: UUID,
    db: Session
):
    """Проверяет, что текущий продавец владеет entity"""
    if entity_type == "PRODUCT":
        product = db.query(Product).filter(Product.id == entity_id).first()
        if not product or product.seller_id != current_seller_id:
            error_response("FORBIDDEN", "You don't own this product", 403)
    elif entity_type == "SKU":
        sku = db.query(SKU).join(Product).filter(SKU.id == entity_id).first()
        if not sku or sku.product.seller_id != current_seller_id:
            error_response("FORBIDDEN", "You don't own this SKU", 403)
    else:
        error_response("INVALID_REQUEST", "entity_type must be PRODUCT or SKU", 400)


@router.post("/", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_image(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: Optional[UUID] = Form(None),
    ordering: int = Form(0),
    db: Session = Depends(get_db),
    current_seller: Seller = Depends(get_current_seller)
):
    """POST /api/v1/images - загрузка изображения"""
    
    if entity_type not in ("PRODUCT", "SKU"):
        error_response("INVALID_REQUEST", "entity_type must be PRODUCT or SKU", 400)
    
    if entity_id:
        check_entity_ownership(entity_id, entity_type, current_seller.id, db)
    
    content = file.file.read()
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE:
        error_response("FILE_TOO_LARGE", "File size exceeds 5 MB limit", 413)
    
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in ALLOWED_TYPES:
        error_response("UNSUPPORTED_MEDIA_TYPE", f"Unsupported file type: {mime_type}", 415)
    
    if not verify_magic_bytes(content, mime_type):
        error_response("UNSUPPORTED_MEDIA_TYPE", "File content does not match declared type", 415)
    
    file_ext = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(mime_type, ".bin")
    
    image_id = uuid4()
    filename = f"{image_id}{file_ext}"
    file_path = UPLOAD_DIR / filename
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    base_url = os.getenv("BASE_URL", "http://localhost:8000")
    url = f"{base_url}/uploads/{filename}"
    
    return ImageUploadResponse(
        id=image_id,
        url=url,
        ordering=ordering,
        entity_type=entity_type,
        entity_id=entity_id
    )