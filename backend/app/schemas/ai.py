from pydantic import BaseModel, Field

from app.infrastructure.database.models.transaction import TransactionType


class AIAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


class AIAnalysisResponse(BaseModel):
    type: TransactionType
    category: str
    amount: float | None
    confidence: float
    explanation: str


class AIInsightResponse(BaseModel):
    insight: str
    summary: str
    tips: list[str]


class AIQuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


class AIQuestionResponse(BaseModel):
    answer: str
    context_used: bool
