import os
from pydantic import BaseModel

class Settings(BaseModel):
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "lumenai")
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    SECURITY_HEADERS_HSTS_ENABLED: bool = os.getenv("SECURITY_HEADERS_HSTS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}

settings = Settings()
