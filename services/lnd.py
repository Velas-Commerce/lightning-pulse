import os
import httpx
from cachetools import TTLCache
from dotenv import load_dotenv
from models import GraphInfo

load_dotenv()

LND_URL = os.getenv("LND_URL") or ""
MACAROON_HEX = os.getenv("LND_READONLY_MACAROON_HEX") or ""
TLS_CERT_PATH = os.getenv("LND_TLS_CERT_PATH", "tls.cert") or "tls.cert"

HEADERS = {"Grpc-Metadata-Macaroon": MACAROON_HEX}

_graph_info_cache: TTLCache = TTLCache(maxsize=1, ttl=60)  # LND graph info — refresh every minute


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(verify=TLS_CERT_PATH, headers=HEADERS)


async def get_graph_info() -> GraphInfo:
    if "result" not in _graph_info_cache:
        async with _client() as client:
            response = await client.get(f"{LND_URL}/v1/graph/info")
            response.raise_for_status()
            _graph_info_cache["result"] = response.json()
    return _graph_info_cache["result"]
