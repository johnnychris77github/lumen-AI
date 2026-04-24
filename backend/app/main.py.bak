from fastapi import FastAPI
from backend.app.routers import uploads
from backend.app.db.session import engine
from backend.app.db.base import Base
from backend.app.models import user, review  # ensure models are registered
from backend.app.routers import auth as auth_router
from backend.app.routers import users as users_router
from backend.app.routers import reviews as reviews_router

app = FastAPI(title="LumenAI API")
app.include_router(uploads.router)

@app.get("/health")
def health():
    return {"ok": True}

@app.on_event("startup")
def on_startup():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print("DB init warning:", e)

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(reviews_router.router)
