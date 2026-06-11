import os
from pydantic import BaseModel


def _csv_env(name: str, default: str) -> list[str]:
    values = []
    for item in os.getenv(name, default).split(','):
        cleaned = item.strip()
        if cleaned:
            values.append(cleaned)
    return values


def _truthy_env(name: str, default: str = 'false') -> bool:
    return os.getenv(name, default).strip().lower() in {'1', 'true', 'yes', 'on'}


class Settings(BaseModel):
    MONGO_URI: str = os.getenv('MONGO_URI', '')
    DB_NAME: str = os.getenv('DB_NAME', 'lumenai')
    API_PREFIX: str = '/api'
    ENVIRONMENT: str = os.getenv('LUMENAI_ENVIRONMENT', os.getenv('ENVIRONMENT', 'development')).strip().lower()
    CORS_ORIGINS: list[str] = _csv_env('CORS_ORIGINS', 'http://localhost:3000')
    ALLOW_DEV_TOKENS: bool = _truthy_env(
        'LUMENAI_ALLOW_DEV_TOKENS',
        'false' if os.getenv('LUMENAI_ENVIRONMENT', os.getenv('ENVIRONMENT', 'development')).strip().lower() == 'production' else 'true',
    )
    DEFAULT_TENANT_ID: str = os.getenv('LUMENAI_DEFAULT_TENANT_ID', 'default-tenant').strip() or 'default-tenant'
    DEFAULT_TENANT_NAME: str = os.getenv('LUMENAI_DEFAULT_TENANT_NAME', 'Default Tenant').strip() or 'Default Tenant'


settings = Settings()
