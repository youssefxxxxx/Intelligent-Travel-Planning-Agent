# Backend/main.py

import os
import datetime
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
from core.models import TripRequest
from services import weather as wsvc, accommodation as asvc
from ai import gemini

# Charge les variables d'environnement (.env)
load_dotenv()  

app = FastAPI()

# Schéma pour la requête d'itinéraire
class ItineraryRequest(BaseModel):
    city: str
    origin: str
    start: datetime.date
    end: datetime.date
    budget: float
    email: EmailStr

# Schéma pour l'envoi d'e-mail
class EmailRequest(BaseModel):
    email: EmailStr
    hotel: dict  # { name, total, check_in, check_out }

@app.post("/api/itinerary", response_model=dict)
def generate_itinerary_endpoint(req: ItineraryRequest):
    try:
        # 1) Récupérer la météo
        meteo_slices = wsvc.fetch_weather(req.city, req.start, req.end)
        weather_block = "\n".join(
            f"- {m.date}: {m.description} ({m.temp_min}→{m.temp_max}°C)"
            for m in meteo_slices
        )

        # 2) Construire l'objet TripRequest et générer l'itinéraire avec Gemini
        trip_req = TripRequest(
            city=req.city,
            origin=req.origin,
            start=req.start,
            end=req.end,
            budget=req.budget,
            email=req.email,
        )
        prompt = gemini.build_prompt(trip_req, weather_block)
        itin = gemini.generate_itinerary(prompt)

        # 3) Préparer la réponse JSON
        return {
            "days": [
                {
                    "date": d.date.isoformat(),
                    "morning": d.morning,
                    "afternoon": d.afternoon,
                    "evening": d.evening,
                }
                for d in itin.days
            ],
            "total_cost": itin.total_cost,
            "chain_of_thought": itin.chain_of_thought,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send_email")
def send_email_endpoint(req: EmailRequest):
    try:
        trip_id = str(uuid.uuid4())[:8]
        asvc.send_confirmation_email(req.email, req.hotel, trip_id)
        return {"message": "Email envoyé"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
