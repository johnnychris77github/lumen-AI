import os
from pydantic import BaseModel

class Settings(BaseModel):
    LUMENAI_TENANT_JIT_ENABLED: bool = os.getenv("LUMENAI_TENANT_JIT_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    LUMENAI_TENANT_JIT_ALLOWED_DOMAINS: str = os.getenv("LUMENAI_TENANT_JIT_ALLOWED_DOMAINS", "")
    LUMENAI_TENANT_JIT_DEFAULT_ROLE: str = os.getenv("LUMENAI_TENANT_JIT_DEFAULT_ROLE", "viewer")
    LUMENAI_TENANT_JIT_ALLOWED_ROLES: str = os.getenv("LUMENAI_TENANT_JIT_ALLOWED_ROLES", "viewer,reviewer,admin")
    LUMENAI_TENANT_JIT_REQUIRE_TENANT_CLAIM: bool = os.getenv(
        "LUMENAI_TENANT_JIT_REQUIRE_TENANT_CLAIM",
        "true",
    ).lower() in {"1", "true", "yes", "on"}
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "lumenai")
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

settings = Settings()
