# ai/gemini.py
# ------------------------------------------------------------------------------
import os
import textwrap
import json
import datetime as dt
import google.generativeai as genai
from core.models import TripRequest, Itinerary, ItineraryDay

# ──────────────────────────────────────────────────────────────────────────────
# Helper: get a configured Gemini model (flash 1.5)
# ──────────────────────────────────────────────────────────────────────────────
def _get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Environment variable GEMINI_API_KEY is missing.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")

# ──────────────────────────────────────────────────────────────────────────────
# Prompt template – create a *new* itinerary
# ──────────────────────────────────────────────────────────────────────────────
_PROMPT_TEMPLATE = textwrap.dedent(
    """\
    You are an AI travel agent. The user's request:
    - City: {city}
    - Dates: {start} → {end}
    - Total budget: {budget} €
    - Departure city: {origin}

    Weather data (by day):
    {weather_block}

    Please suggest a realistic day-by-day plan in **JSON**:
    {{
      "days": [
        {{
          "date": "YYYY-MM-DD",
          "morning": "...",
          "afternoon": "...",
          "evening": "...",
          "cost": NN
        }},
        ...
      ],
      "total_cost": NN,
      "chain_of_thought": "..."
    }}

    Constraints:
    * Stay within budget.
    * If the weather says “rain”, favour indoor activities.
    """
)

def build_prompt(req: TripRequest, weather_block: str) -> str:
    """Return the initial prompt string for Gemini."""
    return _PROMPT_TEMPLATE.format(
        city=req.city,
        start=req.start,
        end=req.end,
        budget=req.budget,
        origin=req.origin,
        weather_block=weather_block,
    )

# ──────────────────────────────────────────────────────────────────────────────
# Generate itinerary from scratch
# ──────────────────────────────────────────────────────────────────────────────
def generate_itinerary(prompt: str) -> Itinerary:
    model = _get_model()
    resp = model.generate_content(prompt)
    raw_json = resp.candidates[0].content.parts[0].text.strip("`json \n")
    data = json.loads(raw_json)

    days = [
        ItineraryDay(
            date=dt.date.fromisoformat(d["date"]),
            morning=d["morning"],
            afternoon=d["afternoon"],
            evening=d["evening"],
        )
        for d in data["days"]
    ]

    return Itinerary(
        days=days,
        total_cost=data["total_cost"],
        chain_of_thought=data["chain_of_thought"],
    )

# ──────────────────────────────────────────────────────────────────────────────
# Modify an existing itinerary
# ──────────────────────────────────────────────────────────────────────────────
def modify_itinerary(current_itin: dict, change_request: str) -> Itinerary:
    """
    Ask Gemini to update an existing itinerary (current_itin) according to
    change_request written in natural language. Returns a new Itinerary object.
    """
    model = _get_model()

    prompt = (
        "You are an AI travel agent. Current itinerary (JSON):\n"
        f"{json.dumps(current_itin, indent=2, ensure_ascii=False)}\n\n"
        "The user requests this change:\n"
        f"{change_request}\n\n"
        "Please return the **full** updated itinerary in the exact same JSON "
        'schema (keys: days, total_cost, chain_of_thought).'
    )

    resp = model.generate_content(prompt)
    raw_json = resp.candidates[0].content.parts[0].text.strip("`json \n")
    data = json.loads(raw_json)

    days = [
        ItineraryDay(
            date=dt.date.fromisoformat(d["date"]),
            morning=d["morning"],
            afternoon=d["afternoon"],
            evening=d["evening"],
        )
        for d in data["days"]
    ]
    return Itinerary(
        days=days,
        total_cost=data["total_cost"],
        chain_of_thought=data["chain_of_thought"],
    )
