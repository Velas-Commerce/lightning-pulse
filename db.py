import os
import certifi
from pymongo import AsyncMongoClient, ASCENDING

_client: AsyncMongoClient | None = None

async def connect() -> None:
    global _client
    uri = os.getenv("MONGODB_URI")
    if not uri:
        print("MONGODB_URI not set - history persistence disabled")
        return
    _client = AsyncMongoClient(uri, tlsCAFile=certifi.where())
    db = _client["lightning_dashboard"]
    for collection in ("network_metrics", "graph_info", "lightning_stats"):
        await db[collection].create_index([("recorded_at", ASCENDING)])


async def disconnect() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None


def get_db():
    if _client is None:
        return None
    return _client["lightning_dashboard"]
