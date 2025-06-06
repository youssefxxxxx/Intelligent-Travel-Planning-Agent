# Backend/app.py

import os
import datetime
import uuid
from dotenv import load_dotenv

load_dotenv()  # ← Must precede any import depending on .env

import streamlit as st
import pandas as pd
import pydeck as pdk

from core.models import TripRequest
from services import weather as wsvc, sheets as ss, geocode as gc
from services import accommodation as asvc
from ai import gemini

# ──────────────────────────────────────────────────────────────────────────────
# 0. Streamlit configuration
# ──────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AI Travel Agent", layout="wide")

# ──────────────────────────────────────────────────────────────────────────────
# 1. session_state initialisation (default values)
# ──────────────────────────────────────────────────────────────────────────────
defaults = {
    "itinerary": None,       # {"days":…, "total_cost":…, "chain_of_thought":…, "meteo":…}
    "hotel_dummy": None,     # {"name":…, "total":…, "check_in":…, "check_out":…}
    "workbook": None,        # {"local_file":…, "gsheet_url":…}
    "show_itinerary": False,
    "error_message": "",
    "city_coords": None,     # tuple(lat, lon) of destination city
    "origin_coords": None,   # tuple(lat, lon) of origin city
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ──────────────────────────────────────────────────────────────────────────────
# 2. Input form
# ──────────────────────────────────────────────────────────────────────────────
with st.form("travel_form"):
    st.markdown("## 🛫 Intelligent Travel Agent")
    city_input   = st.text_input("Destination city",  "Barcelona", key="city")
    origin_input = st.text_input("Origin city",       "Paris",     key="origin")
    start_input  = st.date_input("Start date", datetime.date(2025, 6, 2), key="start")
    end_input    = st.date_input("End date",  datetime.date(2025, 6, 5),  key="end")
    budget_input = st.number_input(
        "Total budget (€)",
        min_value=0.0,
        value=300.0,
        step=10.0,
        key="budget"
    )
    email_input  = st.text_input("Email address", "example@example.com", key="email")
    submitted = st.form_submit_button("Generate itinerary")

# ──────────────────────────────────────────────────────────────────────────────
# 3. On form submission
# ──────────────────────────────────────────────────────────────────────────────
if submitted:
    # 3.1. Date validation & required fields
    if end_input < start_input:
        st.session_state.error_message = "🛑 End date must be after start date."
    elif not (city_input and origin_input and email_input):
        st.session_state.error_message = "🛑 Please fill in all required fields."
    else:
        st.session_state.error_message = ""
        try:
            # 3.2. Geocode cities
            st.info("⏳ Geocoding cities…")
            origin_latlon = gc.city_to_coords(origin_input)
            dest_latlon   = gc.city_to_coords(city_input)
            st.session_state.origin_coords = origin_latlon
            st.session_state.city_coords   = dest_latlon
            st.success("✅ Geocoding complete.")

            # 3.3. Weather call
            st.info("📡 Fetching weather data…")
            meteo_slices = wsvc.fetch_weather(city_input, start_input, end_input)
            wb_text = "\n".join(
                f"- {m.date}: {m.description} ({m.temp_min}→{m.temp_max}°C)"
                for m in meteo_slices
            )
            st.success("✅ Weather data retrieved.")

            # 3.4. Build TripRequest
            trip_req = TripRequest(
                city=city_input,
                origin=origin_input,
                start=start_input,
                end=end_input,
                budget=budget_input,
                email=email_input,
            )

            # 3.5. Generate initial itinerary
            st.info("🤖 Generating itinerary with Gemini…")
            itin_obj = gemini.generate_itinerary(gemini.build_prompt(trip_req, wb_text))
            st.success("✅ Itinerary generated.")

            # 3.6. Store in session (convert dates → strings for JSON)
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

            # 3.7. Dummy hotel (50 % of total cost)
            st.session_state.hotel_dummy = {
                "name": "Hotel Barceló Sants",
                "total": round(itin_obj.total_cost * 0.5),
                "check_in": start_input.isoformat(),
                "check_out": end_input.isoformat(),
            }

            # 3.8. Workbook generation (XLSX + Sheets)
            st.info("📑 Preparing Excel workbook / Sheets…")
            wb_info = ss.generate_workbook(
                st.session_state.itinerary,
                st.session_state.hotel_dummy,
                email_input,
            )
            st.session_state.workbook = wb_info
            st.success("✅ Workbook ready.")

            st.session_state.show_itinerary = True

        except Exception as e:
            st.session_state.error_message = f"⚠️ Error: {e}"
            st.session_state.show_itinerary = False

# ──────────────────────────────────────────────────────────────────────────────
# 4. Display error message if needed
# ──────────────────────────────────────────────────────────────────────────────
if st.session_state.error_message:
    st.error(st.session_state.error_message)

# ──────────────────────────────────────────────────────────────────────────────
# 5. If itinerary exists, display it + map + calendar + chat
# ──────────────────────────────────────────────────────────────────────────────
if st.session_state.show_itinerary and st.session_state.itinerary:
    data = st.session_state.itinerary

    # 5.1. Sidebar view selector
    st.sidebar.markdown("## 🗺️ Options")
    view_choice = st.sidebar.radio("Display:", ["Itinerary", "Interactive map"])
    st.sidebar.markdown("---")

    # ──────────────────────────────────────────────────────────────────────────
    # 5.A Textual itinerary + Agenda buttons + modification chat
    # ──────────────────────────────────────────────────────────────────────────
    if view_choice == "Itinerary":
        st.subheader("🗓️ Proposed itinerary")
        for d in data["days"]:
            meteo_desc = next(
                (m["description"] for m in data["meteo"] if m["date"] == d["date"]),
                "N/A",
            )
            with st.expander(f"{d['date']} — Weather: {meteo_desc}"):
                st.markdown(f"**Morning:** {d['morning']}")
                # Google Calendar button "Morning"
                gc_url_morning = (
                    "https://calendar.google.com/calendar/render?action=TEMPLATE"
                    f"&text=Morning+on+{d['date']}+in+{city_input}"
                    f"&dates={d['date'].replace('-','')}T090000Z/{d['date'].replace('-','')}T120000Z"
                    f"&details={d['morning']}"
                    f"&location={city_input.replace(' ', '+')}"
                )
                st.markdown(f"[➕ Add Morning to Google Calendar]({gc_url_morning})")

                st.markdown("---")
                st.markdown(f"**Afternoon:** {d['afternoon']}")
                # Google Calendar button "Afternoon"
                gc_url_pm = (
                    "https://calendar.google.com/calendar/render?action=TEMPLATE"
                    f"&text=Afternoon+on+{d['date']}+in+{city_input}"
                    f"&dates={d['date'].replace('-','')}T130000Z/{d['date'].replace('-','')}T170000Z"
                    f"&details={d['afternoon']}"
                    f"&location={city_input.replace(' ', '+')}"
                )
                st.markdown(f"[➕ Add Afternoon to Google Calendar]({gc_url_pm})")

                st.markdown("---")
                st.markdown(f"**Evening:** {d['evening']}")
                # Google Calendar button "Evening"
                gc_url_evening = (
                    "https://calendar.google.com/calendar/render?action=TEMPLATE"
                    f"&text=Evening+on+{d['date']}+in+{city_input}"
                    f"&dates={d['date'].replace('-','')}T180000Z/{d['date'].replace('-','')}T210000Z"
                    f"&details={d['evening']}"
                    f"&location={city_input.replace(' ', '+')}"
                )
                st.markdown(f"[➕ Add Evening to Google Calendar]({gc_url_evening})")

                st.markdown("---")

        st.write(f"**Estimated total cost:** {data['total_cost']} €  (Budget: {budget_input} €)")

        with st.expander("🧠 View internal logic (CoT)"):
            st.text(data["chain_of_thought"])

        # ──────────────────────────────────────────────────────────────────────
        # 5.A.1. “Itinerary as spreadsheet” section
        # ──────────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("📑 Itinerary as spreadsheet")
        wb = st.session_state.workbook
        if wb:
            loc = wb["local_file"]
            with open(loc, "rb") as f:
                st.download_button(
                    "📥 Download itinerary (XLSX)",
                    f,
                    file_name=os.path.basename(loc),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            if wb["gsheet_url"]:
                st.markdown(f"[📄 Open in Google Sheets]({wb['gsheet_url']})")

        # ──────────────────────────────────────────────────────────────────────
        # 5.A.2. “Dummy hotel + email” section
        # ──────────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("🏨 Dummy hotel booking")
        hd = st.session_state.hotel_dummy
        st.write(f"**Name:** {hd['name']}")
        st.write(f"**Estimated total price:** {hd['total']} €")
        st.write(f"**Dates:** {hd['check_in']} → {hd['check_out']}")

        if st.button("📨 Send confirmation email"):
            try:
                asvc.send_confirmation_email(
                    email_input,
                    hd,
                    str(uuid.uuid4())[:8],
                    attachment_path=wb["local_file"],
                    gsheet_url=wb["gsheet_url"],
                )
                st.success("✉️ Email sent! Check your inbox.")
            except Exception as e:
                st.error(f"❌ Failed to send: {e}")

        # ──────────────────────────────────────────────────────────────────────
        # 5.A.3. Chatbot for interactive modifications
        # ──────────────────────────────────────────────────────────────────────
        st.markdown("---")
        st.subheader("💬 Modify itinerary")
        with st.form("modify_form"):
            mod_request = st.text_area(
                'Example: "Add a visit to the cathedral on June 2 in late afternoon."',
                key="mod_text",
                height=100
            )
            apply_mod = st.form_submit_button("Apply modification")
        if apply_mod and mod_request:
            try:
                st.info("🔄 Applying your request…")
                new_itin_obj = gemini.modify_itinerary(data, mod_request)

                # Update session_state.itinerary directly
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
                    # Keep existing weather
                    "meteo": data["meteo"],
                }
                st.session_state.show_itinerary = True
                st.success("✅ Itinerary updated.")
                # Modifying session_state automatically reruns the script

            except Exception as e:
                st.error(f"❌ Unable to apply modification: {e}")

    # ─────────────────────────────────────────────────────────────────────────────────
    # 5.B Interactive map (all locations)
    # ─────────────────────────────────────────────────────────────────────────────────
    else:
        st.subheader("🗺️ Interactive map")

        oc = st.session_state.origin_coords
        dc = st.session_state.city_coords

        df_points = pd.DataFrame(
            [
                {"lat": oc[0], "lon": oc[1], "label": "Origin",      "color": [ 30,144,255]}, # blue
                {"lat": dc[0], "lon": dc[1], "label": "Destination", "color": [200, 30,  0]}, # red
            ]
        )

        layers = [
            pdk.Layer(
                "ScatterplotLayer",
                data=df_points,
                get_position=["lon", "lat"],
                get_color="color",
                get_radius=900,
                pickable=True,
            ),
            pdk.Layer(
                "TextLayer",
                data=df_points,
                get_position=["lon", "lat"],
                get_text="label",
                get_color=[0, 0, 0, 200],
                get_size=16,
                get_alignment_baseline="'bottom'",
            ),
        ]

        deck = pdk.Deck(
            map_style="mapbox://styles/mapbox/streets-v11",
            initial_view_state=pdk.ViewState(
                latitude=(oc[0] + dc[0]) / 2,
                longitude=(oc[1] + dc[1]) / 2,
                zoom=5,
            ),
            layers=layers,
        )
        st.pydeck_chart(deck)
        st.markdown("*🔍 Zoom and pan the map, click a marker to read its label.*")
