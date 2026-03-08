import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from routers.hello import router as hello_router
from routers.mempool import router as mempool_router
from routers.growth_stats import router as river_router
from routers.lnd import router as lnd_router
from services.graph_metrics import refresh_loop


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(refresh_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

app.include_router(hello_router)
app.include_router(mempool_router)
app.include_router(river_router)
app.include_router(lnd_router)
