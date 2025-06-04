"""
services/flights.py
-------------------
Recherche des vols via l’API aviationstack (plan Free ou supérieur).
- Conversion ville → IATA avec /airports
- Recherche des vols avec /flights
- Gestion centralisée des erreurs 401/403/quota
"""

from __future__ import annotations
import os
import datetime as dt
from typing import List, Dict

import requests
from core.models import TripRequest

_BASE = "https://api.aviationstack.com/v1"        # ← HTTPS obligatoire


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internes
# ──────────────────────────────────────────────────────────────────────────────
def _key() -> str:
    k = os.getenv("AVIATIONSTACK_API_KEY")
    if not k:
        raise RuntimeError("AVIATIONSTACK_API_KEY manquante ou vide.")
    return k


def _req(endpoint: str, **params) -> dict:
    """
    Appel générique.
    - Ajoute la clé `access_key`
    - Lève une RuntimeError avec le message JSON de l’API en cas de 4xx/5xx
    """
    params["access_key"] = _key()
    r = requests.get(f"{_BASE}/{endpoint}", params=params, timeout=10)

    # aviationstack renvoie souvent un JSON {"error": {...}} même si le code ↗︎
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            msg = r.text
        raise RuntimeError(f"aviationstack {r.status_code}: {msg}")

    return r.json()


def _city_to_iata(city: str) -> str:
    """
    Premier aéroport (code IATA) correspondant à la ville.
    """
    data = _req("airports", search=city).get("data", [])
    for a in data:
        if a.get("iata_code"):
            return a["iata_code"]
    raise RuntimeError(f"Aucun code IATA trouvé pour « {city} ».")


# ──────────────────────────────────────────────────────────────────────────────
# Fonction publique
# ──────────────────────────────────────────────────────────────────────────────
def fetch_flights(req: TripRequest) -> List[Dict]:
    """
    Retourne une liste de vols pour la date de départ.
    Chaque dict contient : carrier, flight_no, depart, arrive, price(None).
    """
    dep_iata = _city_to_iata(req.origin)
    arr_iata = _city_to_iata(req.city)

    data = _req(
        "flights",
        dep_iata=dep_iata,
        arr_iata=arr_iata,
        flight_date=req.start.isoformat(),
        limit=10,
    ).get("data", [])

    flights: List[Dict] = [
        {
            "carrier": f["airline"]["name"],
            "flight_no": f["flight"]["iata"] or f["flight"]["icao"],
            "price": None,                               # non dispo en plan Free
            "depart": f["departure"]["scheduled"],
            "arrive": f["arrival"]["scheduled"],
        }
        for f in data
    ]

    if not flights:
        flights.append(
            {
                "carrier": "Aucun vol trouvé",
                "flight_no": "",
                "price": None,
                "depart": "",
                "arrive": "",
            }
        )
    return flights
