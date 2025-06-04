# Backend/app.py

import os
import datetime
import uuid
from dotenv import load_dotenv

load_dotenv()  # ← DOIT précéder tout import dépendant de .env

import streamlit as st
import pandas as pd
import pydeck as pdk

from core.models import TripRequest
from services import weather as wsvc, sheets as ss, geocode as gc
from services import accommodation as asvc
from ai import gemini

# ──────────────────────────────────────────────────────────────────────────────
# 0. Configuration Streamlit
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Agent de Voyage IA", layout="wide")

# ──────────────────────────────────────────────────────────────────────────────
# 1. Initialisation du session_state (valeurs par défaut)
# ──────────────────────────────────────────────────────────────────────────────
defaults = {
    "itinerary": None,       # {"days":…, "total_cost":…, "chain_of_thought":…, "meteo":…}
    "hotel_dummy": None,     # {"name":…, "total":…, "check_in":…, "check_out":…}
    "workbook": None,        # {"local_file":…, "gsheet_url":…}
    "show_itinerary": False,
    "error_message": "",
    "city_coords": None,     # tuple(lat, lon) de la ville de destination
    "origin_coords": None,   # tuple(lat, lon) de la ville de départ
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ──────────────────────────────────────────────────────────────────────────────
# 2. Formulaire de saisie
# ──────────────────────────────────────────────────────────────────────────────
with st.form("travel_form"):
    st.markdown("## 🛫 Agent de Voyage Intelligent")
    city_input   = st.text_input("Ville de destination",  "Barcelone", key="city")
    origin_input = st.text_input("Ville de départ",       "Paris",     key="origin")
    start_input  = st.date_input("Date de début", datetime.date(2025, 6, 2), key="start")
    end_input    = st.date_input("Date de fin",  datetime.date(2025, 6, 5),  key="end")
    budget_input = st.number_input(
        "Budget total (€)", 
        min_value=0.0, 
        value=300.0,
        step=10.0, 
        key="budget"
    )
    email_input  = st.text_input("Adresse e-mail", "example@example.com", key="email")
    submitted = st.form_submit_button("Générer l’itinéraire")

# ──────────────────────────────────────────────────────────────────────────────
# 3. À la soumission du formulaire
# ──────────────────────────────────────────────────────────────────────────────
if submitted:
    # 3.1. Validation “dates” & champs obligatoires
    if end_input < start_input:
        st.session_state.error_message = "🛑 La date de fin doit être après la date de début."
    elif not (city_input and origin_input and email_input):
        st.session_state.error_message = "🛑 Merci de remplir tous les champs obligatoires."
    else:
        st.session_state.error_message = ""
        try:
            # 3.2. Géocodage des villes
            st.info("⏳ Géocodage des villes…")
            origin_latlon = gc.city_to_coords(origin_input)
            dest_latlon   = gc.city_to_coords(city_input)
            st.session_state.origin_coords = origin_latlon
            st.session_state.city_coords   = dest_latlon
            st.success("✅ Géocodage OK.")

            # 3.3. Appel météo
            st.info("📡 Récupération des données météo…")
            meteo_slices = wsvc.fetch_weather(city_input, start_input, end_input)
            wb_text = "\n".join(
                f"- {m.date}: {m.description} ({m.temp_min}→{m.temp_max}°C)"
                for m in meteo_slices
            )
            st.success("✅ Météo récupérée.")

            # 3.4. Construire TripRequest
            trip_req = TripRequest(
                city=city_input,
                origin=origin_input,
                start=start_input,
                end=end_input,
                budget=budget_input,
                email=email_input,
            )

            # 3.5. Génération d’itinéraire initial
            st.info("🤖 Génération de l’itinéraire avec Gemini…")
            itin_obj = gemini.generate_itinerary(gemini.build_prompt(trip_req, wb_text))
            st.success("✅ Itinéraire généré.")

            # 3.6. Stockage en session (convertir dates → chaînes pour JSON)
            st.session_state.itinerary = {
                "days": [
                    {
                        "date": d.date.isoformat(),
                        "morning": d.morning,
                        "afternoon": d.afternoon,
                        "evening": d.evening,
                    }
                    for d in itin_obj.days
                ],
                "total_cost": itin_obj.total_cost,
                "chain_of_thought": itin_obj.chain_of_thought,
                "meteo": [
                    {
                        "date": m.date.isoformat(),
                        "description": m.description,
                        "temp_min": m.temp_min,
                        "temp_max": m.temp_max,
                    }
                    for m in meteo_slices
                ],
            }

            # 3.7. Hôtel factice (50 % du coût total)
            st.session_state.hotel_dummy = {
                "name": "Hotel Barceló Sants",
                "total": round(itin_obj.total_cost * 0.5),
                "check_in": start_input.isoformat(),
                "check_out": end_input.isoformat(),
            }

            # 3.8. Génération du classeur (XLSX + Sheets)
            st.info("📑 Préparation du classeur Excel / Sheets…")
            wb_info = ss.generate_workbook(
                st.session_state.itinerary,
                st.session_state.hotel_dummy,
                email_input,
            )
            st.session_state.workbook = wb_info
            st.success("✅ Classeur prêt.")

            st.session_state.show_itinerary = True

        except Exception as e:
            st.session_state.error_message = f"⚠️ Erreur : {e}"
            st.session_state.show_itinerary = False

# ──────────────────────────────────────────────────────────────────────────────
# 4. Affiche le message d’erreur si besoin
# ──────────────────────────────────────────────────────────────────────────────
if st.session_state.error_message:
    st.error(st.session_state.error_message)

# ──────────────────────────────────────────────────────────────────────────────
# 5. Si l’itinéraire existe, on l’affiche + carte + calendrier + chat
# ──────────────────────────────────────────────────────────────────────────────
if st.session_state.show_itinerary and st.session_state.itinerary:
    data = st.session_state.itinerary

    # 5.1. Barre latérale pour choisir la vue
    st.sidebar.markdown("## 🗺️ Options")
    view_choice = st.sidebar.radio("Afficher :", ["Itinéraire", "Carte interactive"])
    st.sidebar.markdown("---")

    # ──────────────────────────────────────────────────────────────────────────
    # 5.A Itinéraire textuel + Boutons Agenda + Chat de modification
    # ──────────────────────────────────────────────────────────────────────────
    if view_choice == "Itinéraire":
        st.subheader("🗓️ Itinéraire proposé")
        for d in data["days"]:
            meteo_desc = next(
                (m["description"] for m in data["meteo"] if m["date"] == d["date"]),
                "N/A",
            )
            with st.expander(f"{d['date']} — Météo : {meteo_desc}"):
                st.markdown(f"**Matin :** {d['morning']}")
                # Bouton Google Calendar “Matin”
                gc_url_matin = (
                    "https://calendar.google.com/calendar/render?action=TEMPLATE"
                    f"&text=Matin+le+{d['date']}+à+{city_input}"
                    f"&dates={d['date'].replace('-','')}T090000Z/{d['date'].replace('-','')}T120000Z"
                    f"&details={d['morning']}"
                    f"&location={city_input.replace(' ', '+')}"
                )
                st.markdown(f"[➕ Ajouter Matin au Google Calendar]({gc_url_matin})")

                st.markdown("---")
                st.markdown(f"**Après-midi :** {d['afternoon']}")
                # Bouton Google Calendar “Après-midi”
                gc_url_pm = (
                    "https://calendar.google.com/calendar/render?action=TEMPLATE"
                    f"&text=Après-midi+le+{d['date']}+à+{city_input}"
                    f"&dates={d['date'].replace('-','')}T130000Z/{d['date'].replace('-','')}T170000Z"
                    f"&details={d['afternoon']}"
                    f"&location={city_input.replace(' ', '+')}"
                )
                st.markdown(f"[➕ Ajouter PM au Google Calendar]({gc_url_pm})")

                st.markdown("---")
                st.markdown(f"**Soir :** {d['evening']}")
                # Bouton Google Calendar “Soir”
                gc_url_soir = (
                    "https://calendar.google.com/calendar/render?action=TEMPLATE"
                    f"&text=Soir+le+{d['date']}+à+{city_input}"
                    f"&dates={d['date'].replace('-','')}T180000Z/{d['date'].replace('-','')}T210000Z"
                    f"&details={d['evening']}"
                    f"&location={city_input.replace(' ', '+')}"
                )
                st.markdown(f"[➕ Ajouter Soir au Google Calendar]({gc_url_soir})")

                st.markdown("---")

        st.write(f"**Coût total estimé :** {data['total_cost']} €  (Budget : {budget_input} €)")

        with st.expander("🧠 Voir la Logique interne (CoT)"):
            st.text(data["chain_of_thought"])

        # ──────────────────────────────────────────────────────────────────────
        # 5.A.1. Section “Itinéraire au format tableur”
        # ──────────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("📑 Itinéraire au format tableur")
        wb = st.session_state.workbook
        if wb:
            loc = wb["local_file"]
            with open(loc, "rb") as f:
                st.download_button(
                    "📥 Télécharger l’itinéraire (XLSX)",
                    f,
                    file_name=os.path.basename(loc),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            if wb["gsheet_url"]:
                st.markdown(f"[📄 Ouvrir dans Google Sheets]({wb['gsheet_url']})")

        # ──────────────────────────────────────────────────────────────────────
        # 5.A.2. Section “Hôtel factice + envoi e-mail”
        # ──────────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("🏨 Réservation d’hôtel factice")
        hd = st.session_state.hotel_dummy
        st.write(f"**Nom :** {hd['name']}")
        st.write(f"**Prix total estimé :** {hd['total']} €")
        st.write(f"**Dates :** {hd['check_in']} → {hd['check_out']}")

        if st.button("📨 Envoyer l’e-mail de confirmation"):
            try:
                asvc.send_confirmation_email(
                    email_input,
                    hd,
                    str(uuid.uuid4())[:8],
                    attachment_path=wb["local_file"],
                    gsheet_url=wb["gsheet_url"],
                )
                st.success("✉️ E-mail envoyé ! Consultez votre boîte.")
            except Exception as e:
                st.error(f"❌ Échec de l’envoi : {e}")

        # ──────────────────────────────────────────────────────────────────────
        # 5.A.3. Chatbot pour modifications interactives
        # ──────────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("💬 Modifier l’itinéraire")
        with st.form("modify_form"):
            mod_request = st.text_area(
                "Exemple : « Ajoute une visite de la cathédrale le 2 juin en fin d’après-midi. »",
                key="mod_text",
                height=100
            )
            apply_mod = st.form_submit_button("Appliquer la modification")
        if apply_mod and mod_request:
            try:
                st.info("🔄 Application de votre demande…")
                new_itin_obj = gemini.modify_itinerary(data, mod_request)

                # Met à jour directement session_state.itinerary
                st.session_state.itinerary = {
                    "days": [
                        {
                            "date": d.date.isoformat(),
                            "morning": d.morning,
                            "afternoon": d.afternoon,
                            "evening": d.evening,
                        }
                        for d in new_itin_obj.days
                    ],
                    "total_cost": new_itin_obj.total_cost,
                    "chain_of_thought": new_itin_obj.chain_of_thought,
                    # On conserve l’ancienne météo
                    "meteo": data["meteo"],
                }
                st.session_state.show_itinerary = True
                st.success("✅ Itinéraire mis à jour.")
                # Le simple fait de modifier session_state relance le script

            except Exception as e:
                st.error(f"❌ Impossible d’appliquer la modification : {e}")

    # ─────────────────────────────────────────────────────────────────────────────────
    # 5.B Carte interactive (tous les lieux)
    # ─────────────────────────────────────────────────────────────────────────────────
        # ─────────────────────────────────────────────────────────────────────────────────
    # 5.B Carte interactive (tous les lieux précis, sans couvrir toute la ville)
    # ─────────────────────────────────────────────────────────────────────────────────
    else:
        st.subheader("🗺️ Carte interactive de l’itinéraire")

        # 1) On récupère origin & destination (uniquement pour centrer la carte)
        oc = st.session_state.origin_coords
        dc = st.session_state.city_coords

        # 2) Géocoder chaque activité et construire une liste de points
        activities_points = []
        idx = 1  # compteur pour “J1”, “J2”, etc.

        for day_info in st.session_state.itinerary["days"]:
            for moment in ["morning", "afternoon", "evening"]:
                text_activity = day_info[moment].strip()
                if not text_activity:
                    continue

                # 2.A. Extraire la partie “lieu” de la phrase d’activité
                place = text_activity
                for prefix in ["Visite de ", "Visite du ", "Découverte de ", "Découverte du ",
                               "Exploration de ", "Exploration du ", "Aller à ", "Aller au "]:
                    if place.startswith(prefix):
                        place = place[len(prefix):]
                        break

                # 2.B. Géocoder “lieu + ville” pour obtenir lat/lon
                query = f"{place}, {city_input}"
                try:
                    lat, lon = gc.city_to_coords(query)
                    activities_points.append({
                        "lat": lat,
                        "lon": lon,
                        "label": f"J{idx} {moment.capitalize()}"
                    })
                except Exception:
                    # Si Nominatim ne trouve pas, on n’ajoute pas ce point
                    pass
            idx += 1

        # 3) Construire le DataFrame pour PyDeck
        #    – On inclut ORIGINE (pour le point de départ) mais PAS la “Destination”,
        #      afin de ne pas masquer tous les POI
        df_points = pd.DataFrame(
            [{"lat": oc[0], "lon": oc[1], "label": "Origine"}] + activities_points
        )

        # 4) Créer la carte PyDeck
        deck = pdk.Deck(
            map_style="mapbox://styles/mapbox/streets-v11",
            initial_view_state=pdk.ViewState(
                latitude=(oc[0] + dc[0]) / 2,
                longitude=(oc[1] + dc[1]) / 2,
                zoom=10,    # on zoome davantage pour voir les POI de plus près
                pitch=0,
            ),
            layers=[
                # Cercle pour chaque point (Origine + POI)
                pdk.Layer(
                    "ScatterplotLayer",
                    data=df_points,
                    get_position=["lon", "lat"],
                    get_color=[200, 30, 0, 200],
                    get_radius=800,  # rayon en mètres : ~800 m pour un petit point
                    pickable=True,
                ),
                # Texte (étiquette) pour chaque point
                pdk.Layer(
                    "TextLayer",
                    data=df_points,
                    get_position=["lon", "lat"],
                    get_text="label",
                    get_color=[0, 0, 0, 200],
                    get_size=14,
                    get_alignment_baseline="'bottom'",
                ),
            ],
        )
        st.pydeck_chart(deck)
        st.markdown(
            "*🔍 Vous pouvez zoomer, déplacer la carte et cliquer sur un marqueur pour lire l’étiquette.*"
        )

