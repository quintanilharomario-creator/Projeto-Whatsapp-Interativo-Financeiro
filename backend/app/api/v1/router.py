from fastapi import APIRouter

from app.api.v1.endpoints import (
    ai,
    audio,
    auth,
    evolution,
    reports,
    transactions,
    whatsapp,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(transactions.router)
api_router.include_router(reports.router)
api_router.include_router(audio.router)
api_router.include_router(whatsapp.router)
api_router.include_router(evolution.router)
api_router.include_router(ai.router)
