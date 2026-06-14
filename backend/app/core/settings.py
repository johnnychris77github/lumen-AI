import os
from pydantic import BaseModel

class Settings(BaseModel):
    LUMENAI_AUTH_MODE: str = os.getenv("LUMENAI_AUTH_MODE", "dev_token")
    LUMENAI_API_TOKEN: str = os.getenv("LUMENAI_API_TOKEN", "")
    LUMENAI_JWT_ISSUER: str = os.getenv("LUMENAI_JWT_ISSUER", "")
    LUMENAI_JWT_AUDIENCE: str = os.getenv("LUMENAI_JWT_AUDIENCE", "")
    LUMENAI_JWT_ALGORITHMS: str = os.getenv("LUMENAI_JWT_ALGORITHMS", "RS256")
    LUMENAI_JWT_JWKS_URL: str = os.getenv("LUMENAI_JWT_JWKS_URL", "")
    LUMENAI_JWT_LEEWAY_SECONDS: int = int(os.getenv("LUMENAI_JWT_LEEWAY_SECONDS", "60"))
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "lumenai")
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

settings = Settings()
