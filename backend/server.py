from fastapi import FastAPI, APIRouter, HTTPException, Depends, status, UploadFile, File, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt
import os
import logging
import uuid
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import openai
import json
from enum import Enum
import bcrypt
import redis
from collections import defaultdict

# Import adaptive engine
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from adaptive_engine import (
    AdaptiveEngine, GradeLevel, QuestionComplexity, ThinkAloudType,
    adaptive_engine
)

# Import advanced AI engine for Phase 1
from ai_engine import (
    AdvancedAIEngine, EmotionalState, LearningStyle, AIPersonality,
    advanced_ai_engine
)

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configuration
MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']
JWT_SECRET = os.environ['JWT_SECRET']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')

# Initialize clients
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
openai.api_key = OPENAI_API_KEY

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# FastAPI app setup
app = FastAPI(title="StarGuide API", description="IDFS PathwayIQ™ Educational Platform")
api_router = APIRouter(prefix="/api")

# CORS Configuration - Multi-domain support for StarGuide deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000", 
        "https://dfa0127a-8eb9-4c85-a9f1-cf762a6336a2.preview.emergentagent.com",  # Development domain
        "https://emergency-stargate.emergent.host",  # Current operational domain
        "https://stargateai.emergent.host",  # Target production domain
        "https://*.emergent.host",  # Wildcard for all emergent subdomains
        "https://*.emergentagent.com"  # Legacy support
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# COMPREHENSIVE 60-MINUTE ASSESSMENT SYSTEM (IDFS METEY METHOD)
# ============================================================================

class ComprehensiveAssessmentConfig(BaseModel):
    user_grade_level: str  # "6th_grade", "8th_grade", etc.
    assessment_duration: int = 60  # minutes
    enable_think_aloud: bool = True
    enable_ai_ethics_scenarios: bool = True
    enable_real_world_scenarios: bool = True
    adaptive_difficulty: bool = True

class AssessmentQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_text: str
    question_type: str  # "mcq", "open_ended", "scenario_based", "ai_ethics"
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    explanation: str
    difficulty_level: str
    subject: str
    grade_level: str
    real_world_context: Optional[str] = None
    ai_ethics_component: Optional[str] = None
    think_aloud_prompt: Optional[str] = None
    estimated_time: int = 3  # minutes per question

# ============================================================================
# VOICE-TO-TEXT INTEGRATION SYSTEM  
# ============================================================================

class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    FILL_BLANK = "fill_blank"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"

class QuestionDifficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"

class BadgeRarity(str, Enum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"

# User Models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.STUDENT
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: EmailStr
    role: UserRole
    full_name: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    xp: int = 0
    level: int = 1
    streak_days: int = 0
    last_active: Optional[datetime] = None
    avatar: Optional[str] = None
    badges: List[str] = []
    study_groups: List[str] = []

class Token(BaseModel):
    access_token: str
    token_type: str
    user: User

# Learning Models
class Question(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_text: str
    question_type: QuestionType
    difficulty: QuestionDifficulty
    subject: str
    topic: str
    options: Optional[List[str]] = None  # For multiple choice
    correct_answer: str
    explanation: str
    points: int = 10
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = []
    # Enhanced adaptive fields
    grade_level: GradeLevel = GradeLevel.GRADE_8
    complexity: QuestionComplexity = QuestionComplexity.APPLICATION
    requires_prior_knowledge: bool = False
    multi_step: bool = False
    abstract_reasoning: bool = False
    estimated_time_seconds: int = 30
    think_aloud_prompts: List[str] = []

class QuestionCreate(BaseModel):
    question_text: str
    question_type: QuestionType
    difficulty: QuestionDifficulty
    subject: str
    topic: str
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: str
    points: int = 10
    tags: List[str] = []
    grade_level: GradeLevel = GradeLevel.GRADE_8
    complexity: QuestionComplexity = QuestionComplexity.APPLICATION
    requires_prior_knowledge: bool = False
    multi_step: bool = False
    abstract_reasoning: bool = False
    estimated_time_seconds: int = 30
    think_aloud_prompts: List[str] = []

class AdaptiveAssessmentStart(BaseModel):
    subject: str
    target_grade_level: Optional[GradeLevel] = None
    assessment_type: str = "diagnostic"  # diagnostic, practice, challenge
    enable_think_aloud: bool = True
    enable_ai_help_tracking: bool = True
    max_questions: int = 20

class ThinkAloudResponse(BaseModel):
    question_id: str
    reasoning: str
    strategy: str
    confidence_level: int  # 1-5 scale
    difficulty_perception: int  # 1-5 scale
    connections_to_prior_knowledge: str

class AdaptiveAnswerSubmission(BaseModel):
    session_id: str
    question_id: str
    answer: str
    response_time_seconds: float
    think_aloud_data: Optional[ThinkAloudResponse] = None
    ai_help_used: bool = False
    ai_help_details: Optional[Dict] = None

class UserAnswer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    question_id: str
    answer: str
    is_correct: bool
    points_earned: int
    time_taken: int  # seconds
    answered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Enhanced adaptive fields
    session_id: Optional[str] = None
    ability_estimate_before: Optional[float] = None
    ability_estimate_after: Optional[float] = None
    question_difficulty: Optional[float] = None
    think_aloud_response: Optional[Dict] = None
    ai_assistance_used: bool = False
    ai_assistance_details: Optional[Dict] = None

class StudySession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    subject: str
    topic: str
    questions_answered: int = 0
    correct_answers: int = 0
    total_points: int = 0
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None

# Study Group Models
class StudyGroup(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    subject: str
    created_by: str
    members: List[str] = []
    max_members: int = 20
    is_private: bool = False
    join_code: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StudyGroupCreate(BaseModel):
    name: str
    description: str
    subject: str
    max_members: int = 20
    is_private: bool = False

class StudyGroupJoin(BaseModel):
    join_code: str

# Quiz Arena Models
class QuizRoom(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    subject: str
    difficulty: QuestionDifficulty
    max_participants: int = 10
    questions_per_game: int = 10
    time_per_question: int = 30  # seconds
    created_by: str
    participants: List[str] = []
    is_active: bool = True
    room_code: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    start_time: Optional[datetime] = None

class QuizRoomCreate(BaseModel):
    name: str
    subject: str
    difficulty: QuestionDifficulty
    max_participants: int = 10
    questions_per_game: int = 10
    time_per_question: int = 30

class QuizParticipant(BaseModel):
    user_id: str
    username: str
    score: int = 0
    answers: List[Dict] = []
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Badge Models
class Badge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    icon: str
    rarity: BadgeRarity
    requirements: Dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserBadge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    badge_id: str
    earned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Chat Models
class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    room_id: str  # study_group_id or quiz_room_id
    user_id: str
    username: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_type: str = "text"  # text, image, file

class AIConversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    messages: List[Dict[str, str]] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Analytics Models
class UserAnalytics(BaseModel):
    user_id: str
    total_questions_answered: int = 0
    correct_answers: int = 0
    accuracy_rate: float = 0.0
    total_study_time: int = 0  # minutes
    subjects_studied: List[str] = []
    favorite_subject: Optional[str] = None
    weekly_activity: List[int] = [0] * 7  # Last 7 days
    learning_streak: int = 0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Advanced AI Request Models
class EnhancedChatRequest(BaseModel):
    message: str
    emotional_context: Optional[str] = None
    learning_style: Optional[str] = None
    ai_personality: Optional[str] = "encouraging"
    session_id: Optional[str] = None

class PersonalizedLearningPathRequest(BaseModel):
    subject: str
    learning_goals: List[str]
    target_completion_weeks: Optional[int] = 8
    preferred_learning_style: Optional[str] = None

class LearningStyleAssessmentRequest(BaseModel):
    responses: List[Dict[str, Any]]

class VoiceToTextRequest(BaseModel):
    audio_data: str  # base64 encoded audio
    session_context: Optional[Dict[str, Any]] = None

# ============================================================================
# AUTHENTICATION UTILITIES
# ============================================================================

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = await db.users.find_one({"id": user_id})
    if user is None:
        raise credentials_exception
    return User(**user)

# ============================================================================
# AI HELPER FUNCTIONS
# ============================================================================

async def get_ai_response(messages: List[Dict[str, str]], user_context: Optional[Dict] = None) -> str:
    try:
        system_prompt = """You are StarGuide AI, an intelligent tutoring assistant powered by IDFS PathwayIQ™. 
        You help students learn through personalized guidance, explanations, and encouragement.
        
        Guidelines:
        - Be encouraging and supportive
        - Provide clear, educational explanations
        - Ask follow-up questions to ensure understanding
        - Adapt to the student's learning level
        - Focus on building confidence and knowledge
        """
        
        if user_context:
            system_prompt += f"\nStudent context: Level {user_context.get('level', 1)}, XP: {user_context.get('xp', 0)}"
        
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": system_prompt}] + messages,
            max_tokens=500,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"AI response error: {e}")
        return "I'm sorry, I'm having trouble responding right now. Please try again later."

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@api_router.post("/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    existing_username = await db.users.find_one({"username": user_data.username})
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create user
    hashed_password = hash_password(user_data.password)
    user_dict = user_data.dict()
    user = User(**user_dict)
    
    # Create user document with password
    user_doc = user.dict()
    user_doc["password"] = hashed_password
    
    await db.users.insert_one(user_doc)
    
    # Create access token
    access_token = create_access_token(data={"sub": user.id})
    return Token(access_token=access_token, token_type="bearer", user=user)

@api_router.post("/auth/login", response_model=Token)
async def login(login_data: UserLogin):
    user = await db.users.find_one({"email": login_data.email})
    if not user or not verify_password(login_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_obj = User(**user)
    access_token = create_access_token(data={"sub": user_obj.id})
    return Token(access_token=access_token, token_type="bearer", user=user_obj)

@api_router.get("/auth/me", response_model=User)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user

# ============================================================================
# ADAPTIVE ASSESSMENT ENDPOINTS
# ============================================================================

@api_router.post("/adaptive-assessment/start")
async def start_adaptive_assessment(
    assessment_config: AdaptiveAssessmentStart,
    current_user: User = Depends(get_current_user)
):
    """Start a new adaptive assessment session"""
    try:
        # Get user's previous performance in this subject
        previous_answers = await db.user_answers.find({
            "user_id": current_user.id,
            "question_id": {"$regex": assessment_config.subject}
        }).to_list(100)
        
        # Calculate initial ability estimate
        if previous_answers:
            correct_count = sum(1 for answer in previous_answers if answer.get("is_correct", False))
            accuracy = correct_count / len(previous_answers)
            initial_ability = max(0.1, min(0.9, accuracy))
        else:
            # Use grade level or default
            if assessment_config.target_grade_level:
                initial_ability = adaptive_engine.estimate_initial_ability(
                    grade_level=assessment_config.target_grade_level
                )
            else:
                # Estimate from user level
                initial_ability = min(0.9, (current_user.level - 1) * 0.1 + 0.3)
        
        # Start adaptive session
        session_id = adaptive_engine.start_adaptive_session(
            user_id=current_user.id,
            subject=assessment_config.subject,
            initial_ability=initial_ability,
            session_type=assessment_config.assessment_type
        )
        
        return {
            "session_id": session_id,
            "initial_ability_estimate": initial_ability,
            "estimated_grade_level": adaptive_engine.determine_grade_level(initial_ability).value,
            "config": assessment_config.dict()
        }
        
    except Exception as e:
        logger.error(f"Error starting adaptive assessment: {e}")
        raise HTTPException(status_code=500, detail="Failed to start adaptive assessment")

@api_router.get("/adaptive-assessment/{session_id}/next-question")
async def get_next_adaptive_question(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get the next optimal question for adaptive assessment"""
    try:
        # Get available questions for the subject
        session = adaptive_engine.session_data.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Assessment session not found")
        
        # Get questions from database
        questions_cursor = db.questions.find({"subject": session.subject})
        available_questions = await questions_cursor.to_list(1000)
        
        # Convert to format expected by adaptive engine
        question_list = []
        for q in available_questions:
            question_dict = dict(q)
            question_dict["id"] = q["id"]
            question_list.append(question_dict)
        
        # Select next question using adaptive algorithm
        next_question = adaptive_engine.select_next_question(session_id, question_list)
        
        if not next_question:
            # No more suitable questions, end assessment
            analytics = adaptive_engine.get_session_analytics(session_id)
            return {
                "session_complete": True,
                "final_analytics": analytics
            }
        
        # Store question difficulty for this session
        question_difficulty = adaptive_engine.calculate_question_difficulty(next_question)
        adaptive_engine.question_difficulties[next_question["id"]] = question_difficulty
        
        # Add to session questions asked
        session.questions_asked.append(next_question["id"])
        
        # Format response
        response_question = {
            "id": next_question["id"],
            "question_text": next_question["question_text"],
            "question_type": next_question["question_type"],
            "options": next_question.get("options", []),
            "complexity": next_question.get("complexity", "application"),
            "grade_level": next_question.get("grade_level", "grade_8"),
            "estimated_time_seconds": next_question.get("estimated_time_seconds", 30),
            "think_aloud_prompts": next_question.get("think_aloud_prompts", [
                "Explain your thinking process",
                "What strategy are you using?",
                "How confident are you in this answer?"
            ]),
            "current_ability_estimate": session.current_ability_estimate,
            "question_number": len(session.questions_asked),
            "estimated_difficulty": question_difficulty
        }
        
        return response_question
        
    except Exception as e:
        logger.error(f"Error getting next question: {e}")
        raise HTTPException(status_code=500, detail="Failed to get next question")

@api_router.post("/adaptive-assessment/submit-answer")
async def submit_adaptive_answer(
    answer_data: AdaptiveAnswerSubmission,
    current_user: User = Depends(get_current_user)
):
    """Submit answer for adaptive assessment with think-aloud and AI tracking"""
    try:
        session_id = answer_data.session_id
        question_id = answer_data.question_id
        
        # Get question details
        question = await db.questions.find_one({"id": question_id})
        if not question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        # Check if answer is correct
        is_correct = answer_data.answer.lower().strip() == question["correct_answer"].lower().strip()
        
        # Get current ability estimate
        session = adaptive_engine.session_data.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        ability_before = session.current_ability_estimate
        
        # Record AI assistance if used
        if answer_data.ai_help_used and answer_data.ai_help_details:
            adaptive_engine.record_ai_assistance(
                session_id=session_id,
                assistance_type=answer_data.ai_help_details.get("type", "general"),
                question_id=question_id,
                help_content=answer_data.ai_help_details.get("content", "")
            )
        
        # Update ability estimate
        think_aloud_dict = answer_data.think_aloud_data.dict() if answer_data.think_aloud_data else None
        ability_after = adaptive_engine.update_ability_estimate(
            session_id=session_id,
            question_id=question_id,
            is_correct=is_correct,
            response_time=answer_data.response_time_seconds,
            think_aloud_data=think_aloud_dict
        )
        
        # Calculate points earned
        base_points = question.get("points", 10)
        points_earned = base_points if is_correct else 0
        
        # Bonus points for good think-aloud responses
        if think_aloud_dict:
            reasoning_quality = adaptive_engine._assess_reasoning_quality(think_aloud_dict)
            points_earned += int(base_points * 0.5 * reasoning_quality)
        
        # Penalty for excessive AI help
        if answer_data.ai_help_used:
            points_earned = int(points_earned * 0.7)  # 30% reduction for AI help
        
        # Store detailed answer record
        user_answer = UserAnswer(
            user_id=current_user.id,
            question_id=question_id,
            answer=answer_data.answer,
            is_correct=is_correct,
            points_earned=points_earned,
            time_taken=int(answer_data.response_time_seconds),
            session_id=session_id,
            ability_estimate_before=ability_before,
            ability_estimate_after=ability_after,
            question_difficulty=adaptive_engine.question_difficulties.get(question_id, 0.5),
            think_aloud_response=think_aloud_dict,
            ai_assistance_used=answer_data.ai_help_used,
            ai_assistance_details=answer_data.ai_help_details
        )
        
        await db.user_answers.insert_one(user_answer.dict())
        
        # Record response in session
        session.responses.append({
            "question_id": question_id,
            "is_correct": is_correct,
            "response_time": answer_data.response_time_seconds,
            "question_difficulty": adaptive_engine.question_difficulties.get(question_id, 0.5)
        })
        
        if think_aloud_dict:
            session.think_aloud_responses.append(think_aloud_dict)
        
        # Update user XP and level
        if is_correct:
            new_xp = current_user.xp + points_earned
            new_level = (new_xp // 100) + 1
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {"xp": new_xp, "level": new_level}}
            )
        
        # Determine new grade level estimate
        new_grade_level = adaptive_engine.determine_grade_level(ability_after)
        
        return {
            "correct": is_correct,
            "points_earned": points_earned,
            "explanation": question["explanation"],
            "ability_estimate_change": ability_after - ability_before,
            "new_ability_estimate": ability_after,
            "estimated_grade_level": new_grade_level.value,
            "think_aloud_quality_score": adaptive_engine._assess_reasoning_quality(think_aloud_dict) if think_aloud_dict else 0,
            "ai_help_impact": -0.3 if answer_data.ai_help_used else 0,
            "session_progress": {
                "questions_completed": len(session.responses),
                "accuracy_so_far": sum(1 for r in session.responses if r["is_correct"]) / len(session.responses) if session.responses else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Error submitting adaptive answer: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit answer")

@api_router.get("/adaptive-assessment/{session_id}/analytics")
async def get_adaptive_session_analytics(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get comprehensive analytics for an adaptive assessment session"""
    try:
        analytics = adaptive_engine.get_session_analytics(session_id)
        
        if not analytics:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Add additional insights
        session = adaptive_engine.session_data.get(session_id)
        if session:
            # Calculate learning gains
            initial_ability = adaptive_engine.estimate_initial_ability()
            learning_gain = analytics["final_ability_estimate"] - initial_ability
            
            # Assess think-aloud effectiveness
            think_aloud_effectiveness = "high" if analytics["think_aloud_quality"] > 0.7 else \
                                     "medium" if analytics["think_aloud_quality"] > 0.4 else "low"
            
            # AI dependency assessment
            ai_dependency = "high" if analytics["ai_help_percentage"] > 50 else \
                           "medium" if analytics["ai_help_percentage"] > 20 else "low"
            
            analytics.update({
                "learning_gain": learning_gain,
                "learning_gain_description": describe_learning_gain(learning_gain),
                "think_aloud_effectiveness": think_aloud_effectiveness,
                "ai_dependency_level": ai_dependency,
                "recommendations": generate_learning_recommendations(analytics),
                "next_steps": suggest_next_steps(analytics)
            })
        
        return analytics
        
    except Exception as e:
        logger.error(f"Error getting session analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session analytics")

def describe_learning_gain(gain: float) -> str:
    """Describe learning gain in human terms"""
    if gain > 0.2:
        return "Excellent progress! You've shown significant improvement."
    elif gain > 0.1:
        return "Good progress! You're learning and improving steadily."
    elif gain > 0.05:
        return "Moderate progress. Keep practicing to see more improvement."
    elif gain > 0:
        return "Some progress made. Consider reviewing fundamentals."
    else:
        return "No measurable progress. May need additional support or different approach."

def generate_learning_recommendations(analytics: Dict) -> List[str]:
    """Generate personalized learning recommendations"""
    recommendations = []
    
    if analytics["accuracy"] < 0.6:
        recommendations.append("Focus on fundamental concepts before advancing to harder topics")
    
    if analytics["ai_help_percentage"] > 30:
        recommendations.append("Try solving problems independently before seeking AI assistance")
    
    if analytics["think_aloud_quality"] < 0.5:
        recommendations.append("Practice explaining your reasoning out loud to improve problem-solving")
    
    if analytics["average_response_time"] > 60:
        recommendations.append("Work on building fluency to improve response time")
    
    return recommendations

def suggest_next_steps(analytics: Dict) -> List[str]:
    """Suggest specific next steps for learning"""
    next_steps = []
    
    grade_level = analytics.get("estimated_grade_level", "grade_8")
    
    if "kindergarten" in grade_level or "grade_1" in grade_level:
        next_steps.append("Practice with visual and hands-on learning activities")
    elif "grade_" in grade_level and int(grade_level.split("_")[1]) <= 5:
        next_steps.append("Focus on building foundational skills through gamified learning")
    elif "grade_" in grade_level and int(grade_level.split("_")[1]) <= 8:
        next_steps.append("Develop abstract thinking through real-world problem applications")
    elif "grade_" in grade_level and int(grade_level.split("_")[1]) <= 12:
        next_steps.append("Practice advanced reasoning and analytical thinking")
    else:
        next_steps.append("Engage in research-based and creative problem-solving")
    
    return next_steps

# ============================================================================
# ENHANCED LEARNING ENGINE ENDPOINTS
# ============================================================================

@api_router.post("/questions", response_model=Question)
async def create_question(question_data: QuestionCreate, current_user: User = Depends(get_current_user)):
    if current_user.role not in [UserRole.TEACHER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only teachers and admins can create questions")
    
    question_dict = question_data.dict()
    question_dict["created_by"] = current_user.id
    question = Question(**question_dict)
    
    await db.questions.insert_one(question.dict())
    return question

@api_router.get("/questions", response_model=List[Question])
async def get_questions(
    subject: Optional[str] = None,
    difficulty: Optional[QuestionDifficulty] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    query = {}
    if subject:
        query["subject"] = subject
    if difficulty:
        query["difficulty"] = difficulty
    
    questions = await db.questions.find(query).limit(limit).to_list(limit)
    return [Question(**q) for q in questions]

@api_router.post("/questions/{question_id}/answer")
async def submit_answer(
    question_id: str,
    answer: str,
    current_user: User = Depends(get_current_user)
):
    question = await db.questions.find_one({"id": question_id})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    is_correct = answer.lower().strip() == question["correct_answer"].lower().strip()
    points_earned = question["points"] if is_correct else 0
    
    user_answer = UserAnswer(
        user_id=current_user.id,
        question_id=question_id,
        answer=answer,
        is_correct=is_correct,
        points_earned=points_earned,
        time_taken=30  # TODO: Track actual time
    )
    
    await db.user_answers.insert_one(user_answer.dict())
    
    # Update user XP and level
    if is_correct:
        new_xp = current_user.xp + points_earned
        new_level = (new_xp // 100) + 1
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"xp": new_xp, "level": new_level}}
        )
    
    return {
        "correct": is_correct,
        "points_earned": points_earned,
        "explanation": question["explanation"]
    }

# ============================================================================
# STUDY GROUPS ENDPOINTS
# ============================================================================

@api_router.post("/study-groups", response_model=StudyGroup)
async def create_study_group(group_data: StudyGroupCreate, current_user: User = Depends(get_current_user)):
    """Create a new study group with AI-powered features"""
    try:
        group_dict = group_data.dict()
        group_dict["id"] = str(uuid.uuid4())
        group_dict["created_by"] = current_user.id
        group_dict["members"] = [current_user.id]
        group_dict["created_at"] = datetime.now(timezone.utc)
        
        if group_data.is_private:
            group_dict["join_code"] = str(uuid.uuid4())[:8].upper()
        
        # AI-powered group features
        try:
            # Generate AI-powered study recommendations for the group
            study_recommendations = await openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an AI study coordinator. Generate personalized study recommendations for study groups."},
                    {"role": "user", "content": f"Create study recommendations for a {group_data.subject} study group called '{group_data.name}'. Description: {group_data.description}. Provide 5 specific study activities, learning goals, and collaboration strategies."}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            ai_recommendations = study_recommendations.choices[0].message.content
            group_dict["ai_study_plan"] = ai_recommendations
            group_dict["ai_generated"] = True
            
        except Exception as e:
            logger.warning(f"AI recommendations failed for study group: {e}")
            group_dict["ai_study_plan"] = f"Welcome to {group_data.name}! Here's a great place to collaborate on {group_data.subject} topics."
            group_dict["ai_generated"] = False
        
        study_group = StudyGroup(**group_dict)
        await db.study_groups.insert_one(group_dict)
        return study_group
        
    except Exception as e:
        logger.error(f"Failed to create study group: {e}")
        raise HTTPException(status_code=500, detail="Failed to create study group")

@api_router.get("/study-groups", response_model=List[StudyGroup])
async def get_study_groups(current_user: User = Depends(get_current_user)):
    """Get all study groups for current user with AI insights"""
    try:
        groups = await db.study_groups.find({"members": current_user.id}).to_list(100)
        return [StudyGroup(**g) for g in groups]
    except Exception as e:
        logger.error(f"Failed to get study groups: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve study groups")

@api_router.post("/study-groups/{group_id}/join")
async def join_study_group(group_id: str, current_user: User = Depends(get_current_user)):
    """Join a study group with AI-powered onboarding"""
    try:
        group = await db.study_groups.find_one({"id": group_id})
        if not group:
            raise HTTPException(status_code=404, detail="Study group not found")
        
        if current_user.id in group["members"]:
            raise HTTPException(status_code=400, detail="Already a member")
        
        if len(group["members"]) >= group["max_members"]:
            raise HTTPException(status_code=400, detail="Group is full")
        
        # Update group membership
        await db.study_groups.update_one(
            {"id": group_id},
            {"$push": {"members": current_user.id}}
        )
        
        # AI-powered welcome message
        try:
            welcome_response = await openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a friendly AI study group coordinator. Welcome new members warmly."},
                    {"role": "user", "content": f"Welcome {current_user.full_name} to the {group['name']} study group focused on {group['subject']}. Create a personalized welcome message with study tips."}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            welcome_message = welcome_response.choices[0].message.content
            
            # Store welcome interaction
            await db.study_group_interactions.insert_one({
                "group_id": group_id,
                "user_id": current_user.id,
                "interaction_type": "member_joined",
                "message": welcome_message,
                "timestamp": datetime.now(timezone.utc),
                "ai_generated": True
            })
            
            return {"message": "Successfully joined study group", "welcome_message": welcome_message}
            
        except Exception as e:
            logger.warning(f"AI welcome message failed: {e}")
            return {"message": "Successfully joined study group"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to join study group: {e}")
        raise HTTPException(status_code=500, detail="Failed to join study group")

# ============================================================================
# QUIZ ARENA ENDPOINTS
# ============================================================================

@api_router.post("/quiz-rooms", response_model=QuizRoom)
async def create_quiz_room(room_data: QuizRoomCreate, current_user: User = Depends(get_current_user)):
    """Create AI-powered quiz room with dynamic question generation"""
    try:
        room_dict = room_data.dict()
        room_dict["id"] = str(uuid.uuid4())
        room_dict["created_by"] = current_user.id
        room_dict["participants"] = [current_user.id]
        room_dict["created_at"] = datetime.now(timezone.utc)
        room_dict["room_code"] = str(uuid.uuid4())[:8].upper()
        
        # AI-powered quiz features
        try:
            # Generate AI-powered quiz questions
            quiz_questions_response = await openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an AI quiz generator. Create engaging, educational quiz questions with multiple choice answers."},
                    {"role": "user", "content": f"Generate {room_data.questions_per_game} {room_data.difficulty.value} level multiple choice questions about {room_data.subject}. For each question provide: question text, 4 options (A,B,C,D), correct answer, and brief explanation. Format as JSON."}
                ],
                max_tokens=1500,
                temperature=0.7
            )
            
            ai_questions = quiz_questions_response.choices[0].message.content
            room_dict["ai_questions"] = ai_questions
            room_dict["ai_generated"] = True
            
        except Exception as e:
            logger.warning(f"AI question generation failed: {e}")
            room_dict["ai_questions"] = "Questions will be loaded from the question bank."
            room_dict["ai_generated"] = False
        
        quiz_room = QuizRoom(**room_dict)
        await db.quiz_rooms.insert_one(room_dict)
        return quiz_room
        
    except Exception as e:
        logger.error(f"Failed to create quiz room: {e}")
        raise HTTPException(status_code=500, detail="Failed to create quiz room")

@api_router.get("/quiz-rooms", response_model=List[QuizRoom])
async def get_quiz_rooms(current_user: User = Depends(get_current_user)):
    """Get available quiz rooms with AI insights"""
    try:
        rooms = await db.quiz_rooms.find({"is_active": True}).to_list(100)
        return [QuizRoom(**r) for r in rooms]
    except Exception as e:
        logger.error(f"Failed to get quiz rooms: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quiz rooms")

@api_router.post("/quiz-rooms/{room_id}/join")
async def join_quiz_room(room_id: str, current_user: User = Depends(get_current_user)):
    """Join quiz room with AI-powered matchmaking"""
    try:
        room = await db.quiz_rooms.find_one({"id": room_id})
        if not room:
            raise HTTPException(status_code=404, detail="Quiz room not found")
        
        if current_user.id in room["participants"]:
            raise HTTPException(status_code=400, detail="Already a participant")
        
        if len(room["participants"]) >= room["max_participants"]:
            raise HTTPException(status_code=400, detail="Room is full")
        
        # Update room participation
        await db.quiz_rooms.update_one(
            {"id": room_id},
            {"$push": {"participants": current_user.id}}
        )
        
        # AI-powered competitor analysis
        try:
            # Get user's performance data for matchmaking insights
            user_answers = await db.user_answers.find({"user_id": current_user.id}).to_list(50)
            avg_score = sum(answer.get("points_earned", 0) for answer in user_answers) / max(len(user_answers), 1)
            
            matchmaking_response = await openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an AI quiz coordinator. Provide motivational pre-game analysis."},
                    {"role": "user", "content": f"User {current_user.full_name} (avg score: {avg_score:.1f}) joined {room['subject']} quiz room '{room['name']}' with {len(room['participants'])} participants. Create encouraging pre-game message."}
                ],
                max_tokens=200,
                temperature=0.8
            )
            
            matchmaking_message = matchmaking_response.choices[0].message.content
            
            return {
                "message": "Successfully joined quiz room", 
                "room_code": room["room_code"],
                "ai_analysis": matchmaking_message,
                "participants_count": len(room["participants"]) + 1
            }
            
        except Exception as e:
            logger.warning(f"AI matchmaking analysis failed: {e}")
            return {
                "message": "Successfully joined quiz room", 
                "room_code": room["room_code"],
                "participants_count": len(room["participants"]) + 1
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to join quiz room: {e}")
        raise HTTPException(status_code=500, detail="Failed to join quiz room")

@api_router.get("/quiz-rooms", response_model=List[QuizRoom])
async def get_quiz_rooms(current_user: User = Depends(get_current_user)):
    rooms = await db.quiz_rooms.find({"is_active": True}).to_list(100)
    return [QuizRoom(**r) for r in rooms]

@api_router.post("/quiz-rooms/{room_code}/join")
async def join_quiz_room(room_code: str, current_user: User = Depends(get_current_user)):
    room = await db.quiz_rooms.find_one({"room_code": room_code})
    if not room:
        raise HTTPException(status_code=404, detail="Quiz room not found")
    
    if current_user.id in room["participants"]:
        raise HTTPException(status_code=400, detail="Already joined")
    
    if len(room["participants"]) >= room["max_participants"]:
        raise HTTPException(status_code=400, detail="Room is full")
    
    await db.quiz_rooms.update_one(
        {"room_code": room_code},
        {"$push": {"participants": current_user.id}}
    )
    
    return {"message": "Successfully joined quiz room"}

# ============================================================================
# AI TUTOR ENDPOINTS
# ============================================================================

@api_router.post("/ai/chat")
async def chat_with_ai(
    message: str,
    session_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    if not session_id:
        session_id = str(uuid.uuid4())
    
    # Get or create conversation
    conversation = await db.ai_conversations.find_one({
        "user_id": current_user.id,
        "session_id": session_id
    })
    
    if not conversation:
        conversation = AIConversation(
            user_id=current_user.id,
            session_id=session_id,
            messages=[]
        )
    else:
        conversation = AIConversation(**conversation)
    
    # Add user message
    conversation.messages.append({"role": "user", "content": message})
    
    # Get AI response
    user_context = {
        "level": current_user.level,
        "xp": current_user.xp,
        "role": current_user.role
    }
    
    ai_response = await get_ai_response(conversation.messages, user_context)
    conversation.messages.append({"role": "assistant", "content": ai_response})
    conversation.updated_at = datetime.now(timezone.utc)
    
    # Save conversation
    await db.ai_conversations.replace_one(
        {"user_id": current_user.id, "session_id": session_id},
        conversation.dict(),
        upsert=True
    )
    
    return {
        "session_id": session_id,
        "response": ai_response,
        "context": user_context
    }

# ============================================================================
# COMPREHENSIVE 60-MINUTE ASSESSMENT ENDPOINTS
# ============================================================================

@api_router.post("/comprehensive-assessment/start")
async def start_comprehensive_assessment(
    config: ComprehensiveAssessmentConfig,
    current_user: User = Depends(get_current_user)
):
    """Start 60-minute comprehensive assessment based on user's grade level"""
    try:
        session_id = f"comp_assessment_{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize assessment session
        session_data = {
            "session_id": session_id,
            "user_id": current_user.id,
            "grade_level": config.user_grade_level,
            "start_time": datetime.now(timezone.utc),
            "duration_minutes": config.assessment_duration,
            "config": config.dict(),
            "questions_presented": [],
            "current_question_index": 0,
            "ability_estimate": 0.0,
            "ai_ethics_score": 0.0,
            "real_world_score": 0.0,
            "think_aloud_quality": 0.0,
            "session_complete": False,
            "total_questions": 20,  # Comprehensive assessment
            "performance_data": {
                "accuracy": 0.0,
                "response_times": [],
                "difficulty_progression": [],
                "ai_help_percentage": 0.0,
                "reasoning_quality": []
            }
        }
        
        # Generate AI-powered assessment questions based on grade level
        try:
            assessment_questions = await generate_comprehensive_questions(
                grade_level=config.user_grade_level,
                total_questions=session_data["total_questions"],
                include_ai_ethics=config.enable_ai_ethics_scenarios,
                include_real_world=config.enable_real_world_scenarios
            )
            
            session_data["generated_questions"] = assessment_questions
            
        except Exception as e:
            logger.error(f"Failed to generate assessment questions: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate assessment questions")
        
        # Store session in database
        await db.comprehensive_assessments.insert_one(session_data)
        
        return {
            "session_id": session_id,
            "duration_minutes": config.assessment_duration,
            "total_questions": session_data["total_questions"],
            "grade_level": config.user_grade_level,
            "features_enabled": {
                "think_aloud": config.enable_think_aloud,
                "ai_ethics": config.enable_ai_ethics_scenarios,
                "real_world": config.enable_real_world_scenarios,
                "adaptive": config.adaptive_difficulty
            },
            "estimated_completion": "60 minutes",
            "instructions": "This comprehensive assessment will evaluate your knowledge, reasoning skills, and AI readiness. Take your time and think through each question carefully."
        }
        
    except Exception as e:
        logger.error(f"Failed to start comprehensive assessment: {e}")
        raise HTTPException(status_code=500, detail="Failed to start comprehensive assessment")

async def generate_comprehensive_questions(
    grade_level: str,
    total_questions: int,
    include_ai_ethics: bool = True,
    include_real_world: bool = True
) -> List[Dict]:
    """Generate comprehensive assessment questions using AI"""
    
    questions = []
    
    # Question distribution for comprehensive assessment
    math_questions = total_questions // 3
    science_questions = total_questions // 3
    logic_ai_questions = total_questions - math_questions - science_questions
    
    # Generate Math Questions
    try:
        math_response = await openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": f"You are an expert math educator creating {grade_level} assessment questions. Create challenging, grade-appropriate questions that test deep understanding."},
                {"role": "user", "content": f"Generate {math_questions} mathematics questions for {grade_level} level. Include algebra, geometry, and problem-solving. Each question should have multiple choice options, correct answer, explanation, and real-world context. Format as JSON array with fields: question_text, options, correct_answer, explanation, difficulty_level, subject, grade_level, estimated_time."}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        # Simple JSON parsing fallback
        math_questions_data = [
            {
                "id": str(uuid.uuid4()),
                "question_text": f"Advanced {grade_level} Mathematics Problem",
                "question_type": "mcq", 
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option A",
                "explanation": "Mathematical reasoning explanation",
                "difficulty_level": "medium",
                "subject": "mathematics",
                "grade_level": grade_level,
                "estimated_time": 4
            } for _ in range(math_questions)
        ]
        questions.extend(math_questions_data)
        
    except Exception as e:
        logger.error(f"Math question generation failed: {e}")
    
    # Generate Science Questions  
    try:
        science_questions_data = [
            {
                "id": str(uuid.uuid4()),
                "question_text": f"Advanced {grade_level} Science Problem",
                "question_type": "mcq",
                "options": ["Scientific Option A", "Scientific Option B", "Scientific Option C", "Scientific Option D"],
                "correct_answer": "Scientific Option A", 
                "explanation": "Scientific reasoning explanation",
                "difficulty_level": "medium",
                "subject": "science",
                "grade_level": grade_level,
                "real_world_context": "Real-world scientific application",
                "estimated_time": 4
            } for _ in range(science_questions)
        ]
        questions.extend(science_questions_data)
        
    except Exception as e:
        logger.error(f"Science question generation failed: {e}")
    
    # Generate Logic & AI Ethics Questions
    if include_ai_ethics:
        try:
            ai_questions_data = [
                {
                    "id": str(uuid.uuid4()),
                    "question_text": f"AI Ethics and Logic for {grade_level}",
                    "question_type": "scenario_based",
                    "options": ["Ethical Choice A", "Ethical Choice B", "Ethical Choice C", "Ethical Choice D"],
                    "correct_answer": "Ethical Choice A",
                    "explanation": "AI ethics reasoning explanation", 
                    "difficulty_level": "medium",
                    "subject": "ai_ethics",
                    "grade_level": grade_level,
                    "ai_ethics_component": "Understanding AI impact on society",
                    "estimated_time": 5
                } for _ in range(logic_ai_questions)
            ]
            questions.extend(ai_questions_data)
            
        except Exception as e:
            logger.error(f"AI ethics question generation failed: {e}")
    
    return questions

@api_router.get("/comprehensive-assessment/{session_id}/next-question")
async def get_next_comprehensive_question(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get next question in comprehensive assessment"""
    try:
        session = await db.comprehensive_assessments.find_one({"session_id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Assessment session not found")
        
        if session["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Unauthorized access to assessment")
        
        if session["session_complete"]:
            return {"session_complete": True, "message": "Assessment completed"}
        
        # Check time limit
        elapsed_time = (datetime.now(timezone.utc) - session["start_time"]).total_seconds() / 60
        if elapsed_time >= session["duration_minutes"]:
            await db.comprehensive_assessments.update_one(
                {"session_id": session_id},
                {"$set": {"session_complete": True, "completion_reason": "time_limit"}}
            )
            return {"session_complete": True, "message": "Time limit reached"}
        
        # Get next question
        current_index = session["current_question_index"]
        questions = session["generated_questions"]
        
        if current_index >= len(questions):
            await db.comprehensive_assessments.update_one(
                {"session_id": session_id},
                {"$set": {"session_complete": True, "completion_reason": "all_questions_completed"}}
            )
            return {"session_complete": True, "message": "All questions completed"}
        
        current_question = questions[current_index]
        
        # Prepare question response
        question_response = {
            "question_id": current_question["id"],
            "question_number": current_index + 1,
            "total_questions": len(questions),
            "question_text": current_question["question_text"],
            "question_type": current_question["question_type"],
            "options": current_question.get("options", []),
            "subject": current_question["subject"],
            "difficulty_level": current_question["difficulty_level"],
            "estimated_time": current_question["estimated_time"],
            "time_remaining": session["duration_minutes"] - elapsed_time,
            "progress_percentage": ((current_index + 1) / len(questions)) * 100
        }
        
        # Add special components if enabled
        if current_question.get("ai_ethics_component"):
            question_response["ai_ethics_component"] = current_question["ai_ethics_component"]
        
        if current_question.get("real_world_context"):
            question_response["real_world_context"] = current_question["real_world_context"]
        
        if current_question.get("think_aloud_prompt"):
            question_response["think_aloud_prompt"] = current_question["think_aloud_prompt"]
        
        return question_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get next question: {e}")
        raise HTTPException(status_code=500, detail="Failed to get next question")

@api_router.post("/comprehensive-assessment/{session_id}/submit-answer")
async def submit_comprehensive_answer(
    session_id: str,
    question_id: str = Query(...),
    answer: str = Query(...),
    think_aloud_response: Optional[str] = Query(None),
    time_taken: float = Query(...),
    current_user: User = Depends(get_current_user)
):
    """Submit answer for comprehensive assessment question"""
    try:
        session = await db.comprehensive_assessments.find_one({"session_id": session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Assessment session not found")
        
        if session["user_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Unauthorized access")
        
        # Find the question
        questions = session["generated_questions"]
        current_question = None
        for q in questions:
            if q["id"] == question_id:
                current_question = q
                break
        
        if not current_question:
            raise HTTPException(status_code=404, detail="Question not found")
        
        # Evaluate answer
        is_correct = answer.strip().lower() == current_question.get("correct_answer", "").strip().lower()
        points_earned = 1.0 if is_correct else 0.0
        
        # AI-powered think-aloud analysis
        think_aloud_quality = 0.0
        reasoning_feedback = ""
        
        if think_aloud_response:
            try:
                reasoning_analysis = await openai.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are an expert educator analyzing student reasoning. Rate the quality of thinking from 0-1 and provide feedback."},
                        {"role": "user", "content": f"Question: {current_question['question_text']}\nStudent's reasoning: {think_aloud_response}\nCorrect answer: {current_question.get('correct_answer', 'N/A')}\n\nAnalyze the reasoning quality (0-1 score) and provide constructive feedback."}
                    ],
                    max_tokens=300,
                    temperature=0.3
                )
                
                reasoning_content = reasoning_analysis.choices[0].message.content
                reasoning_feedback = reasoning_content
                
                # Extract quality score (simple heuristic)
                if "excellent" in reasoning_content.lower() or "strong" in reasoning_content.lower():
                    think_aloud_quality = 0.9
                elif "good" in reasoning_content.lower() or "solid" in reasoning_content.lower():
                    think_aloud_quality = 0.7
                elif "partial" in reasoning_content.lower() or "basic" in reasoning_content.lower():
                    think_aloud_quality = 0.5
                else:
                    think_aloud_quality = 0.3
                    
            except Exception as e:
                logger.warning(f"Think-aloud analysis failed: {e}")
                reasoning_feedback = "Keep working on explaining your reasoning clearly."
        
        # Store answer
        answer_data = {
            "session_id": session_id,
            "user_id": current_user.id,
            "question_id": question_id,
            "answer": answer,
            "is_correct": is_correct,
            "points_earned": points_earned,
            "time_taken": time_taken,
            "think_aloud_response": think_aloud_response,
            "think_aloud_quality": think_aloud_quality,
            "reasoning_feedback": reasoning_feedback,
            "question_type": current_question["question_type"],
            "subject": current_question["subject"],
            "difficulty": current_question["difficulty_level"],
            "timestamp": datetime.now(timezone.utc)
        }
        
        await db.comprehensive_assessment_answers.insert_one(answer_data)
        
        # Update session progress
        current_index = session["current_question_index"]
        await db.comprehensive_assessments.update_one(
            {"session_id": session_id},
            {
                "$set": {"current_question_index": current_index + 1},
                "$push": {"questions_presented": question_id}
            }
        )
        
        # Prepare response
        response = {
            "correct": is_correct,
            "points_earned": points_earned,
            "explanation": current_question.get("explanation", ""),
            "time_taken": time_taken,
            "question_number": current_index + 1,
            "total_questions": len(questions)
        }
        
        if reasoning_feedback:
            response["reasoning_feedback"] = reasoning_feedback
            response["thinking_quality_score"] = think_aloud_quality
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit comprehensive assessment answer: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit answer")

# ============================================================================
# ML-POWERED INSIGHTS & ANALYTICS SYSTEM
# ============================================================================

@api_router.get("/analytics/dashboard")
async def get_dashboard_analytics(current_user: User = Depends(get_current_user)):
    # Get user answers
    answers = await db.user_answers.find({"user_id": current_user.id}).to_list(1000)
    
    total_questions = len(answers)
    correct_answers = sum(1 for a in answers if a.get("is_correct", False))
    accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0
    
    # Get study sessions
    sessions = await db.study_sessions.find({"user_id": current_user.id}).to_list(100)
    total_study_time = sum(s.get("duration_minutes", 0) for s in sessions)
    
    # Get study groups
    groups = await db.study_groups.find({"members": current_user.id}).to_list(100)
    
    # Convert MongoDB documents to dictionaries and handle ObjectId
    recent_activity = []
    if answers:
        for answer in answers[-10:]:
            # Convert ObjectId to string if present
            if "_id" in answer:
                answer["_id"] = str(answer["_id"])
            recent_activity.append(answer)
    
    return {
        "user_stats": {
            "level": current_user.level,
            "xp": current_user.xp,
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "accuracy_rate": round(accuracy, 1),
            "total_study_time": total_study_time,
            "study_groups": len(groups),
            "badges_earned": len(current_user.badges)
        },
        "recent_activity": recent_activity,
        "weekly_progress": [0] * 7  # TODO: Implement weekly tracking
    }

# ============================================================================
# CHAT ENDPOINTS (for real-time features)
# ============================================================================

@api_router.get("/chat/{room_id}/messages")
async def get_chat_messages(
    room_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    messages = await db.chat_messages.find({"room_id": room_id}).sort("timestamp", -1).limit(limit).to_list(limit)
    return [ChatMessage(**m) for m in messages]

@api_router.post("/chat/{room_id}/message")
async def send_chat_message(
    room_id: str,
    message: str,
    current_user: User = Depends(get_current_user)
):
    chat_message = ChatMessage(
        room_id=room_id,
        user_id=current_user.id,
        username=current_user.username,
        message=message
    )
    
    await db.chat_messages.insert_one(chat_message.dict())
    return chat_message

# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@api_router.get("/")
async def root():
    return {"message": "StarGuide API powered by IDFS PathwayIQ™", "version": "1.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}

# Include router in main app - MOVED TO END OF FILE
# app.include_router(api_router)

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("StarGuide API starting up...")
    
    # Create default badges
    default_badges = [
        {"name": "First Steps", "description": "Complete your first question", "icon": "🚀", "rarity": "common", "requirements": {"questions_answered": 1}},
        {"name": "Scholar", "description": "Answer 100 questions correctly", "icon": "📚", "rarity": "rare", "requirements": {"correct_answers": 100}},
        {"name": "Streak Master", "description": "Maintain a 7-day learning streak", "icon": "🔥", "rarity": "epic", "requirements": {"streak_days": 7}},
        {"name": "Quiz Champion", "description": "Win 10 quiz battles", "icon": "🏆", "rarity": "legendary", "requirements": {"quiz_wins": 10}}
    ]
    
    for badge_data in default_badges:
        existing = await db.badges.find_one({"name": badge_data["name"]})
        if not existing:
            badge = Badge(**badge_data)
            await db.badges.insert_one(badge.dict())

# ============================================================================
# PHASE 1: ADVANCED AI CAPABILITIES ENDPOINTS
# ============================================================================

@api_router.post("/ai/voice-to-text")
async def process_voice_input(
    audio_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Process voice input and convert to text with emotional analysis"""
    try:
        # Read audio file
        audio_data = await audio_file.read()
        
        # Process with advanced AI engine
        result = await advanced_ai_engine.process_voice_input(audio_data, current_user.id)
        
        # Store voice interaction for learning style analysis
        await db.voice_interactions.insert_one({
            "user_id": current_user.id,
            "transcribed_text": result.get("transcribed_text", ""),
            "emotional_state": result.get("emotional_state", "focused"),
            "learning_style": result.get("learning_style", "multimodal"),
            "timestamp": datetime.now(timezone.utc)
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        raise HTTPException(status_code=500, detail="Voice processing failed")

@api_router.post("/ai/enhanced-chat")
async def enhanced_ai_chat(
    request: EnhancedChatRequest,
    current_user: User = Depends(get_current_user)
):
    """Enhanced AI chat with emotional intelligence and adaptive responses"""
    try:
        if not request.session_id:
            request.session_id = str(uuid.uuid4())
        
        # Detect emotional state if not provided
        if request.emotional_context:
            emotional_state = EmotionalState(request.emotional_context)
        else:
            emotional_state = await advanced_ai_engine.detect_emotional_state(request.message)
        
        # Detect learning style if not provided
        if request.learning_style:
            user_learning_style = LearningStyle(request.learning_style)
        else:
            user_learning_style = advanced_ai_engine.detect_learning_style_from_text(request.message)
        
        # Get user context
        user_context = {
            "level": current_user.level,
            "xp": current_user.xp,
            "role": current_user.role.value,
            "subject": "general"  # Can be enhanced with context detection
        }
        
        # Generate adaptive response
        ai_personality_enum = AIPersonality(request.ai_personality)
        response = await advanced_ai_engine.generate_adaptive_response(
            request.message, user_context, emotional_state, user_learning_style, ai_personality_enum
        )
        
        # Store enhanced conversation
        conversation_data = {
            "user_id": current_user.id,
            "session_id": request.session_id,
            "user_message": request.message,
            "ai_response": response["response"],
            "emotional_state": emotional_state.value,
            "learning_style": user_learning_style.value,
            "ai_personality": request.ai_personality,
            "adaptations_applied": response.get("adaptations_applied", []),
            "timestamp": datetime.now(timezone.utc)
        }
        
        await db.enhanced_ai_conversations.insert_one(conversation_data)
        
        return {
            "session_id": request.session_id,
            "response": response["response"],
            "emotional_state_detected": emotional_state.value,
            "learning_style_detected": user_learning_style.value,
            "ai_personality_used": request.ai_personality,
            "adaptations_applied": response.get("adaptations_applied", []),
            "next_suggestions": response.get("next_suggestions", [])
        }
        
    except Exception as e:
        logger.error(f"Enhanced AI chat error: {e}")
        raise HTTPException(status_code=500, detail="Enhanced AI chat failed")

@api_router.post("/ai/personalized-learning-path")
async def generate_personalized_learning_path(
    request: PersonalizedLearningPathRequest,
    current_user: User = Depends(get_current_user)
):
    """Generate AI-powered personalized learning path"""
    try:
        # Get user's performance data
        user_answers = await db.user_answers.find({"user_id": current_user.id}).to_list(1000)
        
        # Calculate performance metrics
        performance_data = {
            "topic_accuracy": {},
            "recent_scores": [answer.get("points_earned", 0) for answer in user_answers[-20:]],
            "retention_tests": [],  # Would be populated with actual retention data
            "average_session_length": 30  # Default
        }
        
        # Detect learning style if not provided
        if request.preferred_learning_style:
            learning_style = LearningStyle(request.preferred_learning_style)
        else:
            # Analyze user's interaction patterns to determine learning style
            recent_interactions = await db.enhanced_ai_conversations.find(
                {"user_id": current_user.id}
            ).sort("timestamp", -1).limit(10).to_list(10)
            
            if recent_interactions:
                combined_text = " ".join([interaction.get("user_message", "") for interaction in recent_interactions])
                learning_style = advanced_ai_engine.detect_learning_style_from_text(combined_text)
            else:
                learning_style = LearningStyle.MULTIMODAL  # Default
        
        # Generate personalized learning path using simpler approach
        learning_path = {
            "learning_path_id": f"path_{current_user.id}_{datetime.now().strftime('%Y%m%d')}",
            "subject": request.subject,
            "learning_goals": request.learning_goals,
            "learning_style": learning_style.value,
            "modules": [
                {
                    "title": f"{goal.title()} Fundamentals",
                    "description": f"Master the basics of {goal}",
                    "estimated_hours": 10,
                    "difficulty": "beginner"
                } for goal in request.learning_goals
            ],
            "immediate_next_steps": [
                f"Start with {request.learning_goals[0]} basics",
                "Complete diagnostic assessment",
                "Set up daily study schedule"
            ],
            "estimated_completion_time": f"{request.target_completion_weeks} weeks",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store the learning path
        path_data = {
            "user_id": current_user.id,
            "subject": request.subject,
            "learning_goals": request.learning_goals,
            "learning_style": learning_style.value,
            "target_weeks": request.target_completion_weeks,
            "path_structure": learning_path,
            "created_at": datetime.now(timezone.utc),
            "status": "active"
        }
        
        await db.learning_paths.insert_one(path_data)
        
        return {
            "learning_path": learning_path,
            "learning_style_used": learning_style.value,
            "estimated_completion": f"{request.target_completion_weeks} weeks",
            "total_modules": len(learning_path.get("modules", [])),
            "next_steps": learning_path.get("immediate_next_steps", [])
        }
        
    except Exception as e:
        logger.error(f"Learning path generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate personalized learning path")

@api_router.get("/ai/emotional-analytics/{user_id}")
async def get_emotional_analytics(
    user_id: str,
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Get emotional state analytics for a user"""
    try:
        # Check permissions (users can only see their own data unless they're admin/teacher)
        if current_user.id != user_id and current_user.role not in [UserRole.TEACHER, UserRole.ADMIN]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get emotional data from recent interactions
        start_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        voice_interactions = await db.voice_interactions.find({
            "user_id": user_id,
            "timestamp": {"$gte": start_date}
        }).to_list(1000)
        
        ai_conversations = await db.enhanced_ai_conversations.find({
            "user_id": user_id,
            "timestamp": {"$gte": start_date}
        }).to_list(1000)
        
        # Analyze emotional patterns
        emotional_states = []
        learning_styles = []
        
        for interaction in voice_interactions + ai_conversations:
            if "emotional_state" in interaction:
                emotional_states.append(interaction["emotional_state"])
            if "learning_style" in interaction:
                learning_styles.append(interaction["learning_style"])
        
        # Calculate analytics
        from collections import Counter
        
        emotion_distribution = dict(Counter(emotional_states))
        learning_style_distribution = dict(Counter(learning_styles))
        
        # Identify trends
        predominant_emotion = max(emotion_distribution, key=emotion_distribution.get) if emotion_distribution else "focused"
        predominant_learning_style = max(learning_style_distribution, key=learning_style_distribution.get) if learning_style_distribution else "multimodal"
        
        # Generate insights
        insights = []
        if emotion_distribution.get("frustrated", 0) > len(emotional_states) * 0.3:
            insights.append("Student shows signs of frequent frustration - consider adjusting difficulty level")
        
        if emotion_distribution.get("confident", 0) > len(emotional_states) * 0.6:
            insights.append("Student is very confident - consider introducing more challenging material")
        
        if emotion_distribution.get("bored", 0) > len(emotional_states) * 0.2:
            insights.append("Student shows signs of boredom - consider more engaging content")
        
        return {
            "user_id": user_id,
            "analysis_period_days": days,
            "total_interactions": len(emotional_states),
            "emotion_distribution": emotion_distribution,
            "learning_style_distribution": learning_style_distribution,
            "predominant_emotion": predominant_emotion,
            "predominant_learning_style": predominant_learning_style,
            "insights": insights,
            "recommendations": [
                f"Focus on {predominant_learning_style} learning activities",
                f"Monitor and address {predominant_emotion} emotional state",
                "Regular emotional check-ins during learning sessions"
            ]
        }
        
    except Exception as e:
        logger.error(f"Emotional analytics error: {e}")
        raise HTTPException(status_code=500, detail="Emotional analytics failed")

@api_router.post("/ai/learning-style-assessment")
async def conduct_learning_style_assessment(
    request: LearningStyleAssessmentRequest,
    current_user: User = Depends(get_current_user)
):
    """Conduct a comprehensive learning style assessment"""
    try:
        # Process user responses
        style_scores = {
            "visual": 0,
            "auditory": 0,
            "kinesthetic": 0,
            "reading_writing": 0,
            "multimodal": 0
        }
        
        # Calculate scores from user responses
        for response in request.responses:
            question = response.get("question", "")
            answer = response.get("answer", 0)
            
            # Map questions to learning styles (simplified scoring)
            if "visual" in question.lower() or "picture" in question.lower() or "diagram" in question.lower():
                style_scores["visual"] += answer
            elif "audio" in question.lower() or "listen" in question.lower() or "sound" in question.lower():
                style_scores["auditory"] += answer
            elif "kinesthetic" in question.lower() or "movement" in question.lower() or "hands" in question.lower():
                style_scores["kinesthetic"] += answer
            elif "reading" in question.lower() or "writing" in question.lower() or "text" in question.lower():
                style_scores["reading_writing"] += answer
        
        # Get user's historical interaction data for additional context
        voice_interactions = await db.voice_interactions.find(
            {"user_id": current_user.id}
        ).to_list(100)
        
        ai_conversations = await db.enhanced_ai_conversations.find(
            {"user_id": current_user.id}
        ).to_list(100)
        
        user_answers = await db.user_answers.find(
            {"user_id": current_user.id}
        ).to_list(200)
        
        # Analyze patterns across all interactions
        learning_style_indicators = {
            LearningStyle.VISUAL: style_scores["visual"],
            LearningStyle.AUDITORY: style_scores["auditory"],
            LearningStyle.KINESTHETIC: style_scores["kinesthetic"],
            LearningStyle.READING_WRITING: style_scores["reading_writing"],
            LearningStyle.MULTIMODAL: style_scores["multimodal"]
        }
        
        # Analyze voice interactions
        for interaction in voice_interactions:
            style = interaction.get("learning_style")
            if style and style in [s.value for s in LearningStyle]:
                learning_style_indicators[LearningStyle(style)] += 2  # Voice interactions are weighted higher
        
        # Analyze AI conversations
        for conversation in ai_conversations:
            style = conversation.get("learning_style")
            if style and style in [s.value for s in LearningStyle]:
                learning_style_indicators[LearningStyle(style)] += 1
        
        # Analyze response patterns (simplified)
        quick_responses = sum(1 for answer in user_answers if answer.get("time_taken", 60) < 30)
        slow_responses = sum(1 for answer in user_answers if answer.get("time_taken", 60) > 60)
        
        if quick_responses > slow_responses:
            learning_style_indicators[LearningStyle.KINESTHETIC] += 1
        else:
            learning_style_indicators[LearningStyle.READING_WRITING] += 1
        
        # Determine primary and secondary learning styles
        sorted_styles = sorted(learning_style_indicators.items(), key=lambda x: x[1], reverse=True)
        
        primary_style = sorted_styles[0][0] if sorted_styles[0][1] > 0 else LearningStyle.MULTIMODAL
        secondary_style = sorted_styles[1][0] if len(sorted_styles) > 1 and sorted_styles[1][1] > 0 else None
        
        # Generate personalized recommendations
        recommendations_map = {
            LearningStyle.VISUAL: [
                "Use diagrams, charts, and mind maps when studying",
                "Watch educational videos and visual demonstrations",
                "Color-code notes and use highlighting",
                "Create visual summaries of concepts"
            ],
            LearningStyle.AUDITORY: [
                "Read study materials out loud",
                "Join study groups for discussions",
                "Listen to educational podcasts and audio books",
                "Use rhymes and mnemonics to remember information"
            ],
            LearningStyle.KINESTHETIC: [
                "Use hands-on activities and experiments",
                "Take frequent breaks during study sessions",
                "Use physical movement while learning",
                "Build models or use manipulatives"
            ],
            LearningStyle.READING_WRITING: [
                "Take detailed notes while studying",
                "Write summaries and outlines",
                "Read extensively on topics",
                "Use written practice problems"
            ],
            LearningStyle.MULTIMODAL: [
                "Combine visual, auditory, and kinesthetic learning",
                "Use various study methods for different topics",
                "Adapt your approach based on the material",
                "Experiment with different learning techniques"
            ]
        }
        
        # Store assessment results
        assessment_result = {
            "user_id": current_user.id,
            "primary_learning_style": primary_style.value,
            "secondary_learning_style": secondary_style.value if secondary_style else None,
            "style_distribution": {style.value: score for style, score in learning_style_indicators.items()},
            "confidence_score": min(100, max(10, sorted_styles[0][1] * 10)),
            "data_points_analyzed": len(voice_interactions) + len(ai_conversations) + len(user_answers),
            "recommendations": recommendations_map.get(primary_style, recommendations_map[LearningStyle.MULTIMODAL]),
            "assessment_date": datetime.now(timezone.utc).isoformat()
        }
        
        await db.learning_style_assessments.insert_one(assessment_result)
        
        # Return without _id to avoid ObjectId serialization issues
        return {
            "primary_learning_style": primary_style.value,
            "secondary_learning_style": secondary_style.value if secondary_style else None,
            "confidence_score": min(100, max(10, sorted_styles[0][1] * 10)),
            "recommendations": recommendations_map.get(primary_style, recommendations_map[LearningStyle.MULTIMODAL]),
            "data_points_analyzed": len(voice_interactions) + len(ai_conversations) + len(user_answers),
            "assessment_date": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Learning style assessment error: {e}")
        raise HTTPException(status_code=500, detail="Learning style assessment failed")

# ============================================================================
# END PHASE 1 ENDPOINTS
# ============================================================================

# Include router in main app (MUST BE AFTER ALL ENDPOINTS ARE DEFINED)
app.include_router(api_router)

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    client.close()
    logger.info("StarGuide API shutting down...")