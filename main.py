import asyncio
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # whatever port your React dev server uses
    allow_methods=["GET"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(mempool_router)
app.include_router(river_router)
app.include_router(lnd_router)
