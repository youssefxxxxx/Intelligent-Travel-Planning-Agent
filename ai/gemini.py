# ai/gemini.py

import os
import textwrap
import json
import datetime
import google.generativeai as genai
from core.models import TripRequest, Itinerary, ItineraryDay, WeatherSlice

# Configuration de la clé Gemini depuis l'environnement
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_model = genai.GenerativeModel("gemini-1.5-flash")

_PROMPT_TEMPLATE = textwrap.dedent(
    """\
    Vous êtes un agent de voyage IA. Voici la demande utilisateur :
    - Ville : {city}
    - Dates : {start} → {end}
    - Budget total : {budget} €
    - Point de départ : {origin}

    Données météo (par jour) :
    {weather_block}

    Propose un programme jour / soir adapté, format JSON :
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
    - Respecte le budget.
    - Si pluie → activités intérieures.
    """
)

def build_prompt(req: TripRequest, weather_block: str) -> str:
    return _PROMPT_TEMPLATE.format(
        city=req.city,
        start=req.start,
        end=req.end,
        budget=req.budget,
        origin=req.origin,
        weather_block=weather_block,
    )

def generate_itinerary(prompt: str) -> Itinerary:
    """
    Envoie le prompt à Gemini, récupère la réponse JSON, et la mappe en Itinerary.
    """
    resp = _model.generate_content(prompt)
    # Le contenu renvoyé est du type "```json\n{ ... }\n```" ou similaire
    data = resp.candidates[0].content.parts[0].text.strip("```json \n")
    j = json.loads(data)

    days = []
    for d in j["days"]:
        day_obj = ItineraryDay(
            date=datetime.date.fromisoformat(d["date"]),
            morning=d["morning"],
            afternoon=d["afternoon"],
            evening=d["evening"],
        )
        days.append(day_obj)

    return Itinerary(
        days=days,
        total_cost=j["total_cost"],
        chain_of_thought=j["chain_of_thought"],
    )
