import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings


client: AsyncIOMotorClient | None = None


async def connect_db() -> None:
    global client
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri, tlsCAFile=certifi.where())


async def disconnect_db() -> None:
    global client
    if client:
        client.close()
        client = None


def get_db():
    settings = get_settings()
    if client is None:
        raise RuntimeError("Database client not initialized")
    return client[settings.database_name]
