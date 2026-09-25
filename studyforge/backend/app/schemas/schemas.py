from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Documents ---
class DocumentOut(BaseModel):
    id: int
    filename: str
    page_count: int
    ocr_pages: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# --- Q&A ---
class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    document_id: Optional[int] = None  # None = search across all of the user's documents


class SourceCitation(BaseModel):
    chunk_id: int
    document_filename: str
    page_number: Optional[int]
    excerpt: str
    similarity: float


class AskResponse(BaseModel):
    answer: str
    citations: list[SourceCitation]
    generation_method: str  # "llm" or "extractive_fallback"


# --- Quiz ---
class QuizQuestionOut(BaseModel):
    id: int
    topic_name: str
    question_text: str
    options: list[str]
    difficulty: str
    generation_method: str


class QuizAnswerRequest(BaseModel):
    question_id: int
    selected_option_index: int


class QuizAnswerResponse(BaseModel):
    is_correct: bool
    correct_option_index: int
    explanation: str
    updated_mastery: float
    next_recommended_topic: Optional[str]


# --- Dashboard ---
class TopicMastery(BaseModel):
    topic_id: int
    topic_name: str
    mastery_score: float
    attempts_count: int
    last_reviewed_at: Optional[datetime]


class DashboardResponse(BaseModel):
    topics: list[TopicMastery]
    overall_mastery: float
    weakest_topic: Optional[str]
