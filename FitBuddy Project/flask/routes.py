from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import os

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserFeedback, UserResponse, UserListResponse
from app.gemini_generator import generate_workout_gemini
from app.gemini_flash_generator import generate_nutrition_tip_with_flash
from app.updated_plan import update_workout_plan
from app.plan_parser import parse_plan_into_days

router = APIRouter()

# Configure Jinja2 templates location
templates = Jinja2Templates(directory="templates")


# ============================================================
# HOME PAGE
# ============================================================

@router.get("/", response_class=HTMLResponse, summary="FitBuddy Homepage")
async def read_home(request: Request):
    """Renders the FitBuddy landing page with features and plan generator form."""

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "goals": [
                "Weight Loss",
                "Muscle Gain",
                "General Fitness",
                "Flexibility",
                "Endurance"
            ],
            "intensities": [
                "Low",
                "Medium",
                "High"
            ]
        }
    )


# ============================================================
# GENERATE WORKOUT PLAN
# ============================================================

@router.post(
    "/generate-workout",
    response_class=HTMLResponse,
    summary="Generate Workout Plan"
)
async def generate_workout(
    request: Request,
    name: str = Form(...),
    user_id: str = Form(...),
    age: int = Form(...),
    weight: float = Form(...),
    goal: str = Form(...),
    intensity: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Receives user fitness profile, generates workout/nutrition information,
    stores it in the database, and redirects to the result page.
    """

    name = name.strip()
    user_id = user_id.strip()

    # --------------------------------------------------------
    # Validation: Name and User ID
    # --------------------------------------------------------

    if not name or not user_id:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "error_msg": "Name and User ID cannot be empty.",
                "goals": [
                    "Weight Loss",
                    "Muscle Gain",
                    "General Fitness",
                    "Flexibility",
                    "Endurance"
                ],
                "intensities": [
                    "Low",
                    "Medium",
                    "High"
                ]
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # --------------------------------------------------------
    # Validation: Age
    # --------------------------------------------------------

    if age <= 0 or age > 120:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "error_msg": "Please enter a valid age between 1 and 120.",
                "goals": [
                    "Weight Loss",
                    "Muscle Gain",
                    "General Fitness",
                    "Flexibility",
                    "Endurance"
                ],
                "intensities": [
                    "Low",
                    "Medium",
                    "High"
                ]
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # --------------------------------------------------------
    # Validation: Weight
    # --------------------------------------------------------

    if weight <= 0 or weight > 500:
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "error_msg": "Please enter a valid weight in kg.",
                "goals": [
                    "Weight Loss",
                    "Muscle Gain",
                    "General Fitness",
                    "Flexibility",
                    "Endurance"
                ],
                "intensities": [
                    "Low",
                    "Medium",
                    "High"
                ]
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # --------------------------------------------------------
    # Generate workout and nutrition information
    # --------------------------------------------------------

    try:

        # Generate workout plan
        original_plan = generate_workout_gemini(
            name=name,
            age=age,
            weight=weight,
            goal=goal,
            intensity=intensity
        )

        # Generate nutrition/recovery tip
        nutrition_tip = generate_nutrition_tip_with_flash(
            name=name,
            age=age,
            weight=weight,
            goal=goal,
            intensity=intensity
        )

        # ----------------------------------------------------
        # Check whether user already exists
        # ----------------------------------------------------

        db_user = (
            db.query(User)
            .filter(User.user_id == user_id)
            .first()
        )

        if db_user:

            # Update existing user
            db_user.name = name
            db_user.age = age
            db_user.weight = weight
            db_user.goal = goal
            db_user.intensity = intensity
            db_user.original_plan = original_plan
            db_user.updated_plan = None
            db_user.nutrition_tip = nutrition_tip
            db_user.feedback = None

        else:

            # Create new user
            db_user = User(
                user_id=user_id,
                name=name,
                age=age,
                weight=weight,
                goal=goal,
                intensity=intensity,
                original_plan=original_plan,
                nutrition_tip=nutrition_tip
            )

            db.add(db_user)

        # Save database changes
        db.commit()
        db.refresh(db_user)

        # Redirect to result page
        return RedirectResponse(
            url=f"/result/{user_id}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    except Exception as e:

        db.rollback()

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "error_msg": (
                    f"An error occurred while generating your plan: {str(e)}"
                ),
                "goals": [
                    "Weight Loss",
                    "Muscle Gain",
                    "General Fitness",
                    "Flexibility",
                    "Endurance"
                ],
                "intensities": [
                    "Low",
                    "Medium",
                    "High"
                ]
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================
# VIEW GENERATED RESULT
# ============================================================

@router.get(
    "/result/{user_id}",
    response_class=HTMLResponse,
    summary="View Generated Result"
)
async def get_result(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Displays the generated workout plan."""

    db_user = (
        db.query(User)
        .filter(User.user_id == user_id)
        .first()
    )

    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    # Select updated plan if available
    active_plan = (
        db_user.updated_plan
        if db_user.updated_plan
        else db_user.original_plan
    )

    # Parse plan into daily structure
    parsed_days = parse_plan_into_days(active_plan)

    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "user": db_user,
            "parsed_days": parsed_days,
            "has_updated_plan": bool(db_user.updated_plan)
        }
    )


# ============================================================
# SUBMIT FEEDBACK
# ============================================================

@router.post(
    "/submit-feedback",
    response_class=HTMLResponse,
    summary="Submit Plan Feedback"
)
async def submit_feedback(
    request: Request,
    user_id: str = Form(...),
    feedback: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Accepts user feedback, generates an updated workout plan,
    saves it, and displays the comparison page.
    """

    user_id = user_id.strip()
    feedback = feedback.strip()

    # --------------------------------------------------------
    # Empty feedback validation
    # --------------------------------------------------------

    if not feedback:

        db_user = (
            db.query(User)
            .filter(User.user_id == user_id)
            .first()
        )

        if not db_user:
            raise HTTPException(
                status_code=404,
                detail="User not found."
            )

        parsed_days = parse_plan_into_days(
            db_user.original_plan
        )

        return templates.TemplateResponse(
            request,
            "result.html",
            {
                "user": db_user,
                "parsed_days": parsed_days,
                "error_msg": (
                    "Feedback cannot be empty. "
                    "Please specify what changes you would like."
                )
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # --------------------------------------------------------
    # Find user
    # --------------------------------------------------------

    db_user = (
        db.query(User)
        .filter(User.user_id == user_id)
        .first()
    )

    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User profile not found."
        )

    # --------------------------------------------------------
    # Generate updated plan
    # --------------------------------------------------------

    try:

        user_info = {
            "name": db_user.name,
            "goal": db_user.goal,
            "intensity": db_user.intensity
        }

        updated_plan_text = update_workout_plan(
            original_plan=db_user.original_plan,
            feedback=feedback,
            user_info=user_info
        )

        # Save feedback and updated plan
        db_user.feedback = feedback
        db_user.updated_plan = updated_plan_text

        db.commit()
        db.refresh(db_user)

        # Parse both plans
        parsed_original = parse_plan_into_days(
            db_user.original_plan
        )

        parsed_updated = parse_plan_into_days(
            db_user.updated_plan
        )

        return templates.TemplateResponse(
            request,
            "feedback.html",
            {
                "user": db_user,
                "feedback": feedback,
                "parsed_original": parsed_original,
                "parsed_updated": parsed_updated
            }
        )

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workout plan: {str(e)}"
        )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@router.get(
    "/view-all-users",
    response_class=HTMLResponse,
    summary="Admin Dashboard"
)
async def view_all_users(
    request: Request,
    db: Session = Depends(get_db)
):
    """Admin dashboard rendering all registered users."""

    users = (
        db.query(User)
        .order_by(User.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        request,
        "all_users.html",
        {
            "users": users,
            "total_users": len(users)
        }
    )


# ============================================================
# API: LIST ALL USERS
# ============================================================

@router.get(
    "/api/users",
    response_model=UserListResponse,
    summary="API: List All Users"
)
async def api_get_users(
    db: Session = Depends(get_db)
):
    """Returns all registered users as JSON."""

    users = db.query(User).all()

    return {
        "total": len(users),
        "users": users
    }


# ============================================================
# API: GET USER BY ID
# ============================================================

@router.get(
    "/api/users/{user_id}",
    response_model=UserResponse,
    summary="API: Get User Detail"
)
async def api_get_user_by_id(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Returns a specific user and workout plan."""

    db_user = (
        db.query(User)
        .filter(User.user_id == user_id)
        .first()
    )

    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found."
        )

    return db_user
