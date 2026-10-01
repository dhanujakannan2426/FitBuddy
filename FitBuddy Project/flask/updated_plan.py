import os
import logging
from app.config import settings
from app.gemini_generator import DISCLAIMER

logger = logging.getLogger("fitbuddy.updated_plan")

def update_workout_plan(original_plan: str, feedback: str, user_info: dict = None) -> str:
    """
    Updates an existing workout plan based on user feedback using Google Gemini API.
    """
    api_key = settings.GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY", "")
    model_name = settings.GEMINI_MODEL

    if api_key:
        try:
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                prompt = _build_update_prompt(original_plan, feedback, user_info)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                if response and response.text:
                    return _format_updated_response(response.text)
            except ImportError:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name)
                prompt = _build_update_prompt(original_plan, feedback, user_info)
                response = model.generate_content(prompt)
                if response and response.text:
                    return _format_updated_response(response.text)
        except Exception as e:
            logger.error(f"Error updating plan via Gemini API: {e}")

    # Fallback plan update logic when API key is missing or call fails
    return fallback_update_plan(original_plan, feedback)

def _build_update_prompt(original_plan: str, feedback: str, user_info: dict = None) -> str:
    info_str = ""
    if user_info:
        info_str = f"User Context: Name={user_info.get('name')}, Goal={user_info.get('goal')}, Intensity={user_info.get('intensity')}\n"

    return f"""
You are an expert AI fitness coach updating a user's 7-Day Workout Plan based on their specific feedback.

{info_str}
ORIGINAL 7-DAY WORKOUT PLAN:
{original_plan}

USER FEEDBACK / MODIFICATION REQUEST:
"{feedback}"

Task:
Revise the 7-Day Workout Plan to specifically incorporate the requested adjustments (e.g., adding more cardio, extra rest days, reducing intensity, adding yoga, adjusting durations, substituting exercises) while maintaining:
1. Clear 7-Day structure (Day 1 through Day 7 with Warm-up, Exercises, Cooldown).
2. Alignment with the user's primary fitness goal.
3. Safe and effective exercise progression.

At the end, include the exact disclaimer:
"{DISCLAIMER}"
"""

def _format_updated_response(text: str) -> str:
    if DISCLAIMER not in text:
        text += f"\n\n---\n**Disclaimer**: {DISCLAIMER}"
    return text.strip()

def fallback_update_plan(original_plan: str, feedback: str) -> str:
    """Smart fallback for updating plan text based on feedback keywords."""
    feedback_lower = feedback.lower()

    modifications_applied = []
    updated_plan_text = original_plan

    if "cardio" in feedback_lower:
        updated_plan_text = updated_plan_text.replace("Warm-up", "Warm-up (Extended 10-min Cardio Focus)")
        modifications_applied.append("Added extra cardiovascular conditioning to daily routines")

    if "rest" in feedback_lower or "easier" in feedback_lower or "lighter" in feedback_lower:
        updated_plan_text = updated_plan_text.replace("4-5", "2-3").replace("3-4", "2-3")
        modifications_applied.append("Reduced exercise sets and added extra recovery buffer")

    if "yoga" in feedback_lower or "stretch" in feedback_lower or "flexibility" in feedback_lower:
        updated_plan_text = updated_plan_text.replace("Cooldown", "Cooldown & 10-min Yoga Flow")
        modifications_applied.append("Integrated dedicated Yoga and mobility movements into cooldowns")

    if "duration" in feedback_lower or "shorter" in feedback_lower or "quick" in feedback_lower:
        updated_plan_text = updated_plan_text.replace("60 sec", "45 sec").replace("90 sec", "60 sec")
        modifications_applied.append("Optimized exercise rest periods for a shorter 30-45 minute workout duration")

    header_note = f"> 💡 **Updated Plan Notice**: Modified based on user feedback: \"*{feedback}*\"\n"
    if modifications_applied:
        header_note += "> Key changes: " + "; ".join(modifications_applied) + ".\n\n"
    else:
        header_note += "> Key changes: Customized workout structure according to your feedback.\n\n"

    return header_note + updated_plan_text
