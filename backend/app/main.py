from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import settings
from app.routes.system import router as system_router
from app.routes.inspect import router as inspect_router
from app.routes.history import router as history_router
from app.routes.reports import router as reports_router
from app.db import Base, engine

app = FastAPI(title="LumenAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    # Create database tables if they don't exist
    Base.metadata.create_all(bind=engine)


# Routers (all sharing /api prefix)
app.include_router(system_router, prefix=settings.API_PREFIX)
app.include_router(inspect_router, prefix=settings.API_PREFIX)
app.include_router(history_router, prefix=settings.API_PREFIX)
app.include_router(reports_router, prefix=settings.API_PREFIX)
