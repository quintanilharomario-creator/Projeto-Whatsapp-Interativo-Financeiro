from fastapi import APIRouter

from app.api.v1.endpoints import ai, auth, transactions, whatsapp

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(transactions.router)
api_router.include_router(whatsapp.router)
api_router.include_router(ai.router)
