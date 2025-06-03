# run.py

import argparse
import os
import uuid
import datetime
import json
from dotenv import load_dotenv
from rich import print
from core.models import TripRequest
from services import weather as wsvc, flights as fsvc, accommodation as asvc, activities as actsvc
from ai import gemini

load_dotenv()   # Charge les variables depuis .env

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--city", required=True)
    p.add_argument("--origin", required=True)
    p.add_argument("--start", required=True)   # format YYYY-MM-DD
    p.add_argument("--end", required=True)     # format YYYY-MM-DD
    p.add_argument("--budget", type=float, required=True)
    p.add_argument("--email", required=True)
    args = p.parse_args()

    # Construction de l'objet TripRequest
    req = TripRequest(
        city=args.city,
        origin=args.origin,
        start=datetime.date.fromisoformat(args.start),
        end=datetime.date.fromisoformat(args.end),
        budget=args.budget,
        email=args.email,
    )

    print("[bold cyan]→ Récupération météo…[/]")
    meteo = wsvc.fetch_weather(req.city, req.start, req.end)
    wb = "\n".join(
        f"- {m.date}: {m.description} {m.temp_min}–{m.temp_max}°C"
        for m in meteo
    )

    # Génère le prompt et l’itinéraire avec Gemini
    prompt = gemini.build_prompt(req, wb)
    itin = gemini.generate_itinerary(prompt)

    print("[bold green]Itinéraire généré :[/]")
    for d in itin.days:
        print(f"[yellow]{d.date}[/]")
        print(f"  Matin      : {d.morning}")
        print(f"  Après-midi : {d.afternoon}")
        print(f"  Soirée     : {d.evening}\n")

    print(f"Coût total estimé : {itin.total_cost} € (budget : {req.budget} €)")
    print("\n[dim]CoT : " + itin.chain_of_thought[:120] + "...[/]")

    # Exemple de données « hôtel » factices pour envoyer l’e-mail de confirmation
    hotel_dummy = {
        "name": "Hotel Barceló Sants",
        "total": 190,
        "check_in": args.start,
        "check_out": args.end,
    }
    print(f"\nSouhaitez-vous réserver [bold]{hotel_dummy['name']}[/] pour {hotel_dummy['total']} € ? (o/n) ", end="")
    if input().lower().startswith("o"):
        trip_id = str(uuid.uuid4())[:8]
        asvc.send_confirmation_email(req.email, hotel_dummy, trip_id)
        print("[bold green]E-mail envoyé ! Vérifiez votre boîte pour confirmer.[/]")
    else:
        print("Aucune réservation effectuée.")

if __name__ == "__main__":
    main()
