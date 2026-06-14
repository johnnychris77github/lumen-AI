import os
from pydantic import BaseModel

class Settings(BaseModel):
    LUMENAI_OIDC_PROVIDER: str = os.getenv("LUMENAI_OIDC_PROVIDER", "generic")
    LUMENAI_JWT_ACTOR_ID_CLAIM: str = os.getenv("LUMENAI_JWT_ACTOR_ID_CLAIM", "")
    LUMENAI_JWT_ACTOR_NAME_CLAIM: str = os.getenv("LUMENAI_JWT_ACTOR_NAME_CLAIM", "")
    LUMENAI_JWT_ACTOR_EMAIL_CLAIM: str = os.getenv("LUMENAI_JWT_ACTOR_EMAIL_CLAIM", "")
    LUMENAI_JWT_ROLE_CLAIM: str = os.getenv("LUMENAI_JWT_ROLE_CLAIM", "")
    LUMENAI_JWT_TENANT_ID_CLAIM: str = os.getenv("LUMENAI_JWT_TENANT_ID_CLAIM", "")
    LUMENAI_JWT_TENANT_NAME_CLAIM: str = os.getenv("LUMENAI_JWT_TENANT_NAME_CLAIM", "")
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "lumenai")
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

settings = Settings()
