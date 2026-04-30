from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.database import get_connection
from api.config import settings
from api.routes.canvas import router as canvas_router
from api.routes.thesis import router as thesis_router
from api.routes.setup import router as setup_router
from api.routes.trade import router as trade_router
from api.routes.observation import router as observation_router
from api.routes.review import router as review_router
from api.routes.action import router as action_router
from api.routes.ritual import router as ritual_router
from api.routes.inbox import router as inbox_router
from api.routes.entities import router as entities_router
from api.routes.images import router as images_router
from db.init import init_schema
from db.migrations.runner import run_pending

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = await get_connection()
    try:
        await init_schema(conn)
        await run_pending(conn)
    finally:
        await conn.close()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(canvas_router, prefix="/canvas")
app.include_router(thesis_router, prefix="/thesis")
app.include_router(setup_router, prefix="/setup")
app.include_router(trade_router, prefix="/trade")
app.include_router(observation_router, prefix="/observation")
app.include_router(review_router, prefix="/review")
app.include_router(action_router, prefix="/action")
app.include_router(ritual_router)
app.include_router(inbox_router, prefix="/inbox")
app.include_router(entities_router)
app.include_router(images_router)

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))


@app.get("/")
async def home(request: Request):
    from api.routes.entities import _fetch_entities
    filter_type = request.query_params.get("type")
    conn = await get_connection()
    try:
        entities = await _fetch_entities(filter_type, conn)
    finally:
        await conn.close()
    return templates.TemplateResponse("home.html", {
        "request": request,
        "entities": entities,
        "filter_type": filter_type,
    })


@app.get("/health")
async def health():
    conn = await get_connection()
    try:
        await conn.execute("SELECT 1")
        return {"status": "ok", "db": "connected"}
    except Exception:
        return {"status": "ok", "db": "error"}
    finally:
        await conn.close()
