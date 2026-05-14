import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import AIServiceError, AuthorizationError
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db
from app.schemas.ai import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    AIInsightResponse,
    AIQuestionRequest,
    AIQuestionResponse,
)
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze", response_model=AIAnalysisResponse)
async def analyze_transaction(
    body: AIAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AIService()
    suggestion = await svc.analyze_transaction(body.text, user_id=str(current_user.id))
    return AIAnalysisResponse(
        type=suggestion.type,
        category=suggestion.category,
        amount=float(suggestion.amount) if suggestion.amount is not None else None,
        confidence=suggestion.confidence,
        explanation=suggestion.explanation,
    )


@router.get("/insight/{user_id}", response_model=AIInsightResponse)
async def get_monthly_insight(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.id != user_id:
        raise AuthorizationError()
    svc = AIService()
    result = await svc.generate_monthly_report(str(user_id), db)
    return AIInsightResponse(
        insight=result.get("insight", ""),
        summary=result.get("summary", ""),
        tips=result.get("tips", []),
    )


@router.post("/question", response_model=AIQuestionResponse)
async def answer_question(
    body: AIQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AIService()
    answer = await svc.answer_question(body.question, str(current_user.id), db)
    return AIQuestionResponse(answer=answer, context_used=True)
