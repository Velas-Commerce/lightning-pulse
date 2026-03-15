import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from routers.health import router as health_router
from routers.mempool import router as mempool_router
from routers.growth_stats import router as river_router
from routers.lnd import router as lnd_router
from services.graph_metrics import refresh_loop
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(refresh_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
_origins = [o.strip() for o in _raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(mempool_router)
app.include_router(river_router)
app.include_router(lnd_router)
