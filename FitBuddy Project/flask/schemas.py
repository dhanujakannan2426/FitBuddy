from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime

class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Full name of the user")
    user_id: str = Field(..., min_length=1, max_length=50, description="Unique user identifier")
    age: int = Field(..., gt=0, lt=120, description="Age in years (1-119)")
    weight: float = Field(..., gt=0, lt=500, description="Weight in kg")
    goal: str = Field(..., description="Fitness goal: Weight Loss, Muscle Gain, General Fitness, Flexibility, Endurance")
    intensity: str = Field(..., description="Workout intensity: Low, Medium, High")

    @validator('goal')
    def validate_goal(cls, v):
        valid_goals = ["Weight Loss", "Muscle Gain", "General Fitness", "Flexibility", "Endurance"]
        if v not in valid_goals:
            raise ValueError(f"Goal must be one of: {', '.join(valid_goals)}")
        return v

    @validator('intensity')
    def validate_intensity(cls, v):
        valid_intensities = ["Low", "Medium", "High"]
        if v not in valid_intensities:
            raise ValueError(f"Intensity must be one of: {', '.join(valid_intensities)}")
        return v

class UserFeedback(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=50)
    feedback: str = Field(..., min_length=1, max_length=1000, description="Feedback text for updating plan")

class UserResponse(BaseModel):
    id: int
    user_id: str
    name: str
    age: int
    weight: float
    goal: str
    intensity: str
    original_plan: Optional[str] = None
    updated_plan: Optional[str] = None
    nutrition_tip: Optional[str] = None
    feedback: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True

class UserListResponse(BaseModel):
    total: int
    users: List[UserResponse]
