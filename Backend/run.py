import argparse, datetime, uuid
from dotenv import load_dotenv

load_dotenv()

from rich import print
from core.models import TripRequest
from services import weather as wsvc, sheets as ss, accommodation as asvc
from ai import gemini

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--city", "--dest", required=True)
    p.add_argument("--origin", required=True)
    p.add_argument("--start", required=True)  # YYYY-MM-DD
    p.add_argument("--end",   required=True)
    p.add_argument("--budget", type=float, required=True)
    p.add_argument("--email",  required=True)
    args = p.parse_args()

    req = TripRequest(
        city=args.city,
        origin=args.origin,
        start=datetime.date.fromisoformat(args.start),
        end=datetime.date.fromisoformat(args.end),
        budget=args.budget,
        email=args.email,
    )

    print("[cyan]→ Météo…[/]")
    meteo = wsvc.fetch_weather(req.city, req.start, req.end)
    wb_text = "\n".join(f"- {m.date}: {m.description} {m.temp_min}–{m.temp_max}°C"
                        for m in meteo)

    print("[cyan]→ Itinéraire…[/]")
    itin = gemini.generate_itinerary(gemini.build_prompt(req, wb_text))

    for d in itin.days:
        print(f"[yellow]{d.date}[/]  {d.morning} / {d.afternoon} / {d.evening}")
    print(f"Total : {itin.total_cost} € (budget {req.budget} €)")

    hotel = {
        "name": "Hotel Barceló Sants",
        "total": round(itin.total_cost * 0.5),
        "check_in": args.start,
        "check_out": args.end,
    }
    wb_info = ss.generate_workbook(
        {
            "days": [vars(x) for x in itin.days],
            "meteo": [vars(m) for m in meteo],
            "total_cost": itin.total_cost,
        },
        hotel,
        args.email,
    )

    if input("\nEnvoyer l’e-mail de confirmation ? (o/n) ").lower().startswith("o"):
        asvc.send_confirmation_email(
            args.email, hotel, str(uuid.uuid4())[:8],
            attachment_path=wb_info["local_file"],
            gsheet_url=wb_info["gsheet_url"],
        )
        print("[green]E-mail envoyé ![/]")

if __name__ == "__main__":
    main()
