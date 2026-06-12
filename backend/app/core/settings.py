import os
from pydantic import BaseModel

class Settings(BaseModel):
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "lumenai")
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    LUMENAI_AUDIT_ANCHOR_SCHEDULING_ENABLED: bool = os.getenv(
        "LUMENAI_AUDIT_ANCHOR_SCHEDULING_ENABLED",
        "false",
    ).lower() in {"1", "true", "yes", "on"}
    LUMENAI_AUDIT_ANCHOR_INTERVAL_HOURS: int = int(os.getenv("LUMENAI_AUDIT_ANCHOR_INTERVAL_HOURS", "24"))
    LUMENAI_AUDIT_ANCHOR_PROVIDER: str = os.getenv("LUMENAI_AUDIT_ANCHOR_PROVIDER", "internal")

settings = Settings()
