from motor.motor_asyncio import AsyncIOMotorClient
from app.core.settings import settings

_client = None

def get_client():
    global _client
    if _client is None:
        if not settings.MONGO_URI:
            raise RuntimeError("MONGO_URI is not set")
        _client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=8000)
    return _client

def get_db():
    return get_client()[settings.DB_NAME]

def inspections():
    return get_db()["inspections"]

async def ensure_indexes():
    await inspections().create_index([("timestamp", -1)])
    await inspections().create_index("instrument_name")
