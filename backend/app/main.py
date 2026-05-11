from fastapi import FastAPI

from app.api.v1.chat import router as chat_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.forms import router as forms_router


def create_app() -> FastAPI:
    app = FastAPI(title="AskMeInsurance API", version="0.1.0")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(conversations_router, prefix="/api/v1")
    app.include_router(forms_router, prefix="/api/v1")
    return app


app = create_app()
