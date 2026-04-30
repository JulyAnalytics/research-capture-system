from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from ulid import ULID

from api.config import settings
from api.database import get_db

router = APIRouter()

IMAGE_ROOT = Path(settings.image_root)
ALLOWED_ENTITIES = ("observations", "setups")


def _sanitize_filename(name: str) -> str:
    basename = Path(name).name
    if basename != name or "/" in name or "\\" in name:
        raise HTTPException(400, "Invalid filename")
    return basename


@router.post("/images/{entity}/{entity_id}")
async def upload_image(
    entity: str,
    entity_id: str,
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    if entity not in ALLOWED_ENTITIES:
        raise HTTPException(400, f"Invalid entity. Must be one of {ALLOWED_ENTITIES}")

    filename = _sanitize_filename(file.filename or "upload")

    if entity == "observations":
        parent_col = "observation_id"
        rows = await db.execute_fetchall(
            "SELECT id FROM observation WHERE id = ?", (entity_id,)
        )
    else:
        parent_col = "setup_id"
        rows = await db.execute_fetchall(
            "SELECT id FROM setup WHERE id = ?", (entity_id,)
        )

    if not rows:
        raise HTTPException(404, f"{entity.rstrip('s')} not found")

    dest_dir = IMAGE_ROOT / entity / entity_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    content = await file.read()
    dest_path.write_bytes(content)

    rel_filepath = f"{entity}/{entity_id}/{filename}"
    img_id = str(ULID())

    table = "observation_images" if entity == "observations" else "setup_images"
    await db.execute("BEGIN")
    try:
        await db.execute(
            f"INSERT INTO {table} (id, {parent_col}, filename, filepath) VALUES (?, ?, ?, ?)",
            (img_id, entity_id, filename, rel_filepath),
        )
        await db.commit()
    except Exception:
        await db.rollback()
        if dest_path.exists():
            dest_path.unlink()
        raise

    return {"id": img_id, "filename": filename, "filepath": rel_filepath}


@router.get("/images/{entity}/{entity_id}/{filename}")
async def serve_image(entity: str, entity_id: str, filename: str):
    if entity not in ALLOWED_ENTITIES:
        raise HTTPException(400, f"Invalid entity. Must be one of {ALLOWED_ENTITIES}")

    path = (IMAGE_ROOT / entity / entity_id / filename).resolve()

    if not path.is_relative_to(IMAGE_ROOT.resolve()):
        raise HTTPException(400, "Invalid path")

    if not path.exists():
        raise HTTPException(404, "Image not found")

    return FileResponse(path)
