import os
from pydantic import BaseModel

class Settings(BaseModel):
    LUMENAI_ENV: str = os.getenv("LUMENAI_ENV", "development")
    LUMENAI_API_TOKEN: str = os.getenv("LUMENAI_API_TOKEN", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", os.getenv("LUMENAI_JWT_SECRET", ""))
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    DB_NAME: str = os.getenv("DB_NAME", "lumenai")
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

settings = Settings()
