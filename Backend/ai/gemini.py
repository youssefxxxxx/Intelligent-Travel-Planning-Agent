# ai/gemini.py

import os
import textwrap
import json
import datetime as dt
import google.generativeai as genai
from core.models import TripRequest, Itinerary, ItineraryDay

# ──────────────────────────────────────────────────────────────────────────────
# On ne configure pas la clé à l’import, on la lit à la demande dans _get_model()
# ──────────────────────────────────────────────────────────────────────────────
def _get_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY manquante ou vide.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


# ──────────────────────────────────────────────────────────────────────────────
# Prompt template pour génération d’itinéraire neuf
# ──────────────────────────────────────────────────────────────────────────────
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
    """
    Construit le prompt initial pour demander un itinéraire.
    """
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
    Envoie le prompt à Gemini, récupère le JSON en output, et le mappe sur un objet Itinerary.
    """
    model = _get_model()
    resp = model.generate_content(prompt)
    raw = resp.candidates[0].content.parts[0].text.strip("`json \n")
    data = json.loads(raw)

    days = []
    for d in data["days"]:
        day_obj = ItineraryDay(
            date=dt.date.fromisoformat(d["date"]),
            morning=d["morning"],
            afternoon=d["afternoon"],
            evening=d["evening"],
        )
        days.append(day_obj)

    return Itinerary(
        days=days,
        total_cost=data["total_cost"],
        chain_of_thought=data["chain_of_thought"],
    )


def modify_itinerary(current_itin: dict, change_request: str) -> Itinerary:
    """
    Demande à Gemini de modifier un itinéraire existant (JSON), selon une consigne en langage naturel.
    - current_itin : le dict JSON de l’itinéraire actuel (avec "days", "total_cost", "chain_of_thought", "meteo").
    - change_request : texte libre expliquant la modification souhaitée.
    Renvoie un nouvel Itinerary.
    """
    model = _get_model()
    # Construire le prompt pour la modification
    base = (
        "Vous êtes un agent de voyage IA. Voici l’itinéraire actuel (format JSON) :\n"
        f"{json.dumps(current_itin, indent=2, ensure_ascii=False)}\n\n"
        "L’utilisateur demande la modification suivante :\n"
        f"{change_request}\n\n"
        "Merci de renvoyer l’itinéraire COMPLET mis à jour au format JSON exactement identique "
        "au même schéma (avec keys : days, total_cost, chain_of_thought)."
    )
    resp = model.generate_content(base)
    raw = resp.candidates[0].content.parts[0].text.strip("`json \n")
    data = json.loads(raw)

    # Convertir en Itinerary
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
