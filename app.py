
import os
import math
from urllib.parse import urlencode

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from openai import OpenAI

try:
    from streamlit_mic_recorder import mic_recorder
except ImportError:
    mic_recorder = None


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

st.set_page_config(
    page_title="VoltPilot | AI Mobility Assistant",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

HEADERS = {
    "User-Agent": "VoltPilotEVAssistant/1.0 (educational project)"
}

# Create clients only when an API key is configured.
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(145deg, #08111f 0%, #101d30 55%, #07131c 100%);
        color: #f2f7ff;
    }

    [data-testid="stSidebar"] {
        background: #0a1422;
        border-right: 1px solid #20364c;
    }

    .hero {
        padding: 28px 30px;
        border-radius: 22px;
        background: linear-gradient(120deg, #102a43, #103b45, #102235);
        border: 1px solid #24596a;
        margin-bottom: 24px;
    }

    .hero h1 {
        font-size: 44px;
        font-weight: 800;
        margin: 0;
        color: #e8fbff;
    }

    .hero p {
        color: #b6dce7;
        font-size: 17px;
        margin-top: 8px;
        margin-bottom: 0;
    }

    .section-card {
        padding: 18px;
        border-radius: 16px;
        background: #101e2e;
        border: 1px solid #243b50;
        margin-bottom: 12px;
    }

    .small-note {
        color: #9bb3c9;
        font-size: 13px;
    }

    div[data-testid="stMetric"] {
        background: #102033;
        border: 1px solid #243b50;
        padding: 14px;
        border-radius: 14px;
    }

    .stButton button {
        border-radius: 10px;
        font-weight: 600;
    }

    a {
        color: #69e4ed !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "chat_history": [],
    "station_results": None,
    "station_search_label": "",
    "last_transcript": "",
    "last_ai_reply": "",
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def valid_number(value, minimum=0):
    """Check whether a value is a valid non-negative number."""
    try:
        return math.isfinite(float(value)) and float(value) >= minimum
    except (ValueError, TypeError):
        return False


def geocode_location(place):
    """Convert a place name or address to latitude/longitude."""
    if not place or not place.strip():
        return None

    url = "https://nominatim.openstreetmap.org/search"

    try:
        response = requests.get(
            url,
            params={
                "q": place.strip(),
                "format": "jsonv2",
                "limit": 1,
            },
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        results = response.json()

        if not results:
            return None

        item = results[0]

        return {
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "display_name": item.get("display_name", place),
        }

    except requests.RequestException as exc:
        st.warning(f"Location lookup failed: {exc}")
        return None
    except (ValueError, KeyError, TypeError):
        return None


def search_osm_stations(lat, lon, radius_m=10000, station_type="EV chargers"):
    """
    Search OpenStreetMap through Overpass API.

    Results show mapped locations, not guaranteed live availability.
    """
    radius_m = int(max(100, min(radius_m, 50000)))

    if station_type == "EV chargers":
        selector = (
            'node["amenity"="charging_station"](around:{r},{lat},{lon});'
            'way["amenity"="charging_station"](around:{r},{lat},{lon});'
            'relation["amenity"="charging_station"](around:{r},{lat},{lon});'
        )
    elif station_type == "Petrol pumps":
        selector = (
            'node["amenity"="fuel"](around:{r},{lat},{lon});'
            'way["amenity"="fuel"](around:{r},{lat},{lon});'
            'relation["amenity"="fuel"](around:{r},{lat},{lon});'
        )
    else:
        selector = (
            'node["amenity"="charging_station"](around:{r},{lat},{lon});'
            'way["amenity"="charging_station"](around:{r},{lat},{lon});'
            'relation["amenity"="charging_station"](around:{r},{lat},{lon});'
            'node["amenity"="fuel"](around:{r},{lat},{lon});'
            'way["amenity"="fuel"](around:{r},{lat},{lon});'
            'relation["amenity"="fuel"](around:{r},{lat},{lon});'
        )

    query = f"""
    [out:json][timeout:25];
    (
        {selector.format(r=radius_m, lat=lat, lon=lon)}
    );
    out center tags;
    """

    endpoints = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]

    last_error = None

    for endpoint in endpoints:
        try:
            response = requests.post(
                endpoint,
                data={"data": query},
                headers=HEADERS,
                timeout=35,
            )
            response.raise_for_status()
            payload = response.json()

            stations = []

            for element in payload.get("elements", []):
                tags = element.get("tags", {})

                element_lat = element.get("lat")
                element_lon = element.get("lon")

                # Ways and relations may have a center rather than coordinates.
                if element_lat is None or element_lon is None:
                    center = element.get("center", {})
                    element_lat = center.get("lat")
                    element_lon = center.get("lon")

                if element_lat is None or element_lon is None:
                    continue

                name = tags.get("name") or tags.get("brand") or "Unnamed location"

                if tags.get("amenity") == "fuel":
                    category = "Petrol pump"
                else:
                    category = "EV charging station"

                stations.append(
                    {
                        "Name": name,
                        "Type": category,
                        "Latitude": float(element_lat),
                        "Longitude": float(element_lon),
                        "Operator": tags.get("operator", "Not listed"),
                        "Sockets": tags.get("socket:type2:output")
                        or tags.get("socket:ccs:output")
                        or tags.get("socket:chademo:output")
                        or "Not listed",
                        "Access": tags.get("access", "Not listed"),
                        "Address": " ".join(
                            str(tags.get(k, ""))
                            for k in [
                                "addr:street",
                                "addr:city",
                                "addr:postcode",
                            ]
                            if tags.get(k)
                        ) or "Not listed",
                        "Map": (
                            "https://www.openstreetmap.org/?"
                            + urlencode(
                                {
                                    "mlat": element_lat,
                                    "mlon": element_lon,
                                    "zoom": 17,
                                }
                            )
                        ),
                    }
                )

            return stations

        except (requests.RequestException, ValueError) as exc:
            last_error = exc

    raise RuntimeError(
        "OpenStreetMap search is temporarily unavailable. "
        f"Please retry later. Details: {last_error}"
    )


def google_maps_directions(origin, destination, travel_mode="driving"):
    """Build a Google Maps directions URL."""
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination,
        "travelmode": travel_mode,
    }
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def calculate_ev_trip(
    battery_kwh,
    soc_percent,
    consumption,
    distance_km,
    reserve_percent,
    target_soc_percent,
    charging_power_kw,
    charger_efficiency,
    electricity_price,
    trip_buffer_percent,
):
    """Estimate range, trip energy, charging requirement and cost."""

    usable_battery_kwh = battery_kwh * max(
        0, soc_percent - reserve_percent
    ) / 100

    estimated_range_km = (
        usable_battery_kwh / consumption * 100
        if consumption > 0
        else 0
    )

    buffered_distance = distance_km * (1 + trip_buffer_percent / 100)

    trip_energy_kwh = buffered_distance * consumption / 100

    available_energy_kwh = battery_kwh * soc_percent / 100

    energy_needed_kwh = max(
        0, trip_energy_kwh - available_energy_kwh
    )

    target_energy_kwh = max(
        0, battery_kwh * (target_soc_percent - soc_percent) / 100
    )

    energy_to_charge_kwh = max(energy_needed_kwh, target_energy_kwh)

    charging_input_kwh = (
        energy_to_charge_kwh / charger_efficiency
        if charger_efficiency > 0
        else 0
    )

    charging_hours = (
        charging_input_kwh / charging_power_kw
        if charging_power_kw > 0
        else 0
    )

    charging_cost = charging_input_kwh * electricity_price

    return {
        "usable_energy": usable_battery_kwh,
        "range": estimated_range_km,
        "buffered_distance": buffered_distance,
        "trip_energy": trip_energy_kwh,
        "energy_needed": energy_needed_kwh,
        "energy_to_charge": energy_to_charge_kwh,
        "charging_hours": charging_hours,
        "charging_cost": charging_cost,
        "range_sufficient": estimated_range_km >= buffered_distance,
    }


def ask_ai(messages):
    """Get a response from the configured LangChain chat model."""
    if not OPENAI_API_KEY:
        return (
            "Add OPENAI_API_KEY to your .env file to enable AI responses. "
            "Your EV calculations and map features can work without it."
        )

    try:
        llm = ChatOpenAI(
            model=OPENAI_MODEL,
            temperature=0.3,
            api_key=OPENAI_API_KEY,
        )

        response = llm.invoke(messages)
        return response.content

    except Exception as exc:
        return (
            "I couldn't get an AI response. Check your API key, model access, "
            f"internet connection, and package versions.\n\nDetails: {exc}"
        )


def transcribe_audio(audio_bytes):
    """Transcribe uploaded or recorded audio using OpenAI."""
    if not openai_client:
        return "Add OPENAI_API_KEY to your .env file first."

    try:
        from io import BytesIO

        audio_file = BytesIO(audio_bytes)
        audio_file.name = "voice_input.wav"

        result = openai_client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=audio_file,
        )

        return result.text

    except Exception as exc:
        return f"Transcription failed: {exc}"


def generate_speech(text):
    """Generate spoken output from an AI response."""
    if not openai_client:
        return None

    try:
        response = openai_client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text[:4000],
        )

        return response.read()

    except Exception as exc:
        st.warning(f"Voice generation failed: {exc}")
        return None


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.title("⚡ VoltPilot")
    st.caption("Predict range. Find chargers. Drive smarter.")

    st.divider()

    st.markdown("### Navigation")
    st.markdown(
        """
        - 🔋 EV Range & Trip Planner
        - 🗺️ Nearby Stations
        - 🤖 AI Mobility Assistant
        - 🎙️ Voice Assistant
        """
    )

    st.divider()

    st.markdown("### System status")

    if OPENAI_API_KEY:
        st.success("OpenAI key detected")
    else:
        st.warning("OpenAI key not configured")

    st.caption(f"AI model: {OPENAI_MODEL}")
    st.caption("Map data: OpenStreetMap")
    st.caption("Directions: Google Maps")


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>⚡ VoltPilot</h1>
        <p>Predict range. Find chargers. Drive smarter.</p>
        <p>Your AI-powered electric mobility companion.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write(
    "Plan your EV journey, estimate battery requirements, discover mapped "
    "charging stations, and ask the AI assistant questions about electric mobility."
)


# ============================================================
# MAIN TABS
# ============================================================

tab_planner, tab_stations, tab_ai, tab_voice = st.tabs(
    [
        "🔋 EV Trip Planner",
        "🗺️ Nearby Stations",
        "🤖 AI Assistant",
        "🎙️ Voice Assistant",
    ]
)


# ============================================================
# TAB 1: EV TRIP PLANNER
# ============================================================

with tab_planner:
    st.subheader("EV range and charging planner")
    st.write("Enter your vehicle and journey details to estimate energy needs.")

    with st.form("ev_planner_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            battery_kwh = st.number_input(
                "Battery capacity (kWh)",
                min_value=1.0,
                max_value=300.0,
                value=60.0,
                step=1.0,
            )

            soc_percent = st.slider(
                "Current battery (%)",
                min_value=0,
                max_value=100,
                value=80,
            )

            reserve_percent = st.slider(
                "Minimum reserve (%)",
                min_value=0,
                max_value=50,
                value=15,
            )

        with col2:
            consumption = st.number_input(
                "Consumption (kWh/100 km)",
                min_value=1.0,
                max_value=60.0,
                value=16.0,
                step=0.5,
            )

            distance_km = st.number_input(
                "Trip distance (km)",
                min_value=0.0,
                max_value=5000.0,
                value=150.0,
                step=5.0,
            )

            trip_buffer_percent = st.slider(
                "Extra trip energy buffer (%)",
                min_value=0,
                max_value=40,
                value=15,
            )

        with col3:
            target_soc_percent = st.slider(
                "Desired charging target (%)",
                min_value=0,
                max_value=100,
                value=90,
            )

            charging_power_kw = st.number_input(
                "Charger power (kW)",
                min_value=0.5,
                max_value=500.0,
                value=50.0,
                step=5.0,
            )

            charger_efficiency = st.slider(
                "Charging efficiency (%)",
                min_value=50,
                max_value=100,
                value=90,
            ) / 100

            electricity_price = st.number_input(
                "Electricity price (₹/kWh)",
                min_value=0.0,
                max_value=500.0,
                value=12.0,
                step=0.5,
            )

        submitted = st.form_submit_button(
            "⚡ Calculate EV trip",
            use_container_width=True,
        )

    if submitted:
        if reserve_percent > soc_percent:
            st.error(
                "Your minimum reserve is higher than your current battery. "
                "Adjust the battery or reserve setting."
            )
        elif target_soc_percent < soc_percent:
            st.warning(
                "Your target charge is below the current battery percentage. "
                "Charging time will be zero if no additional energy is needed."
            )
            result = calculate_ev_trip(
                battery_kwh,
                soc_percent,
                consumption,
                distance_km,
                reserve_percent,
                target_soc_percent,
                charging_power_kw,
                charger_efficiency,
                electricity_price,
                trip_buffer_percent,
            )
            st.session_state["ev_result"] = result
        else:
            result = calculate_ev_trip(
                battery_kwh,
                soc_percent,
                consumption,
                distance_km,
                reserve_percent,
                target_soc_percent,
                charging_power_kw,
                charger_efficiency,
                electricity_price,
                trip_buffer_percent,
            )
            st.session_state["ev_result"] = result

    result = st.session_state.get("ev_result")

    if result:
        st.divider()
        st.subheader("Your EV trip analysis")

        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "Estimated usable range",
            f"{result['range']:.0f} km",
        )

        m2.metric(
            "Trip energy estimate",
            f"{result['trip_energy']:.1f} kWh",
        )

        m3.metric(
            "Energy to add",
            f"{result['energy_to_charge']:.1f} kWh",
        )

        m4.metric(
            "Estimated charging cost",
            f"₹{result['charging_cost']:.0f}",
        )

        if result["range_sufficient"]:
            st.success(
                "Your estimated usable range covers the buffered trip distance. "
                "Actual range may vary with traffic, speed, weather, terrain, "
                "load, and battery condition."
            )
        else:
            st.warning(
                "Your estimated usable range may not cover the buffered trip. "
                "Consider charging before departure or identifying a charging stop."
            )

        st.markdown("### Charging estimate")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Buffered trip distance",
            f"{result['buffered_distance']:.0f} km",
        )

        c2.metric(
            "Approximate charging time",
            f"{result['charging_hours'] * 60:.0f} min",
        )

        c3.metric(
            "Usable energy above reserve",
            f"{result['usable_energy']:.1f} kWh",
        )

        st.caption(
            "These are simplified estimates. Real charging slows at higher "
            "battery levels, and charger output may be below its rated power. "
            "This calculator does not guarantee arrival or account for "
            "battery degradation and elevation."
        )

        with st.expander("View calculation details"):
            st.write(
                {
                    "Battery capacity (kWh)": battery_kwh,
                    "Current state of charge (%)": soc_percent,
                    "Consumption (kWh/100 km)": consumption,
                    "Trip distance (km)": distance_km,
                    "Trip buffer (%)": trip_buffer_percent,
                    "Charging efficiency (%)": charger_efficiency * 100,
                    "Charging power (kW)": charging_power_kw,
                    "Estimated energy to add (kWh)": round(
                        result["energy_to_charge"], 2
                    ),
                    "Estimated charging time (hours)": round(
                        result["charging_hours"], 2
                    ),
                }
            )

        st.markdown("### Plan your route")

        route_col1, route_col2 = st.columns(2)

        with route_col1:
            route_origin = st.text_input(
                "Starting location",
                placeholder="e.g. Thane, Maharashtra",
                key="route_origin",
            )

        with route_col2:
            route_destination = st.text_input(
                "Destination",
                placeholder="e.g. Pune, Maharashtra",
                key="route_destination",
            )

        if st.button("🗺️ Open route in Google Maps", key="planner_route"):
            if route_origin.strip() and route_destination.strip():
                url = google_maps_directions(
                    route_origin.strip(),
                    route_destination.strip(),
                )
                st.link_button(
                    "Open Google Maps directions",
                    url,
                    use_container_width=True,
                )
            else:
                st.error("Enter both the starting location and destination.")


# ============================================================
# TAB 2: NEARBY STATIONS
# ============================================================

with tab_stations:
    st.subheader("Discover nearby stations")
    st.write(
        "Search mapped charging stations or petrol pumps using OpenStreetMap."
    )

    with st.form("station_search_form"):
        location_text = st.text_input(
            "Enter your location",
            placeholder="e.g. Thane West, Maharashtra",
        )

        station_type = st.selectbox(
            "What are you looking for?",
            [
                "EV chargers",
                "Petrol pumps",
                "Both",
            ],
        )

        radius_km = st.slider(
            "Search radius (km)",
            min_value=1,
            max_value=50,
            value=10,
        )

        station_submit = st.form_submit_button(
            "🔎 Find stations",
            use_container_width=True,
        )

    if station_submit:
        if not location_text.strip():
            st.error("Please enter a location.")
        else:
            with st.spinner("Finding the location and searching OpenStreetMap..."):
                coordinates = geocode_location(location_text)

                if coordinates:
                    st.session_state["station_search_label"] = (
                        coordinates["display_name"]
                    )

                    try:
                        station_results = search_osm_stations(
                            coordinates["lat"],
                            coordinates["lon"],
                            radius_m=radius_km * 1000,
                            station_type=station_type,
                        )

                        st.session_state["station_results"] = station_results
                        st.session_state["station_center"] = {
                            "lat": coordinates["lat"],
                            "lon": coordinates["lon"],
                        }

                    except RuntimeError as exc:
                        st.session_state["station_results"] = None
                        st.error(str(exc))
                else:
                    st.error(
                        "Location not found. Try a more specific address, "
                        "area, or city."
                    )

    stations = st.session_state.get("station_results")

    if stations is not None:
        st.divider()

        st.markdown(
            f"**Search area:** {st.session_state.get('station_search_label', '')}"
        )

        if not stations:
            st.info(
                "No matching stations were returned for this search. "
                "Try a larger radius or another location."
            )
        else:
            df = pd.DataFrame(stations)

            st.success(f"Found {len(df)} mapped location(s).")

            display_df = df[
                [
                    "Name",
                    "Type",
                    "Operator",
                    "Sockets",
                    "Access",
                    "Address",
                ]
            ]

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
            )

            center = st.session_state.get("station_center")

            if center:
                map_data = pd.DataFrame(
                    [
                        {
                            "lat": center["lat"],
                            "lon": center["lon"],
                        }
                    ]
                    + [
                        {
                            "lat": row["Latitude"],
                            "lon": row["Longitude"],
                        }
                        for row in stations
                    ]
                )

                st.markdown("### Map view")
                st.map(map_data, latitude="lat", longitude="lon")

            st.markdown("### Open a station")

            for index, station in enumerate(stations):
                with st.expander(
                    f"{station['Name']} — {station['Type']}"
                ):
                    st.write(f"**Operator:** {station['Operator']}")
                    st.write(f"**Connector information:** {station['Sockets']}")
                    st.write(f"**Access:** {station['Access']}")
                    st.write(f"**Address:** {station['Address']}")

                    st.markdown(
                        f"[Open location in OpenStreetMap]({station['Map']})"
                    )

                    destination = (
                        f"{station['Latitude']},{station['Longitude']}"
                    )

                    directions_url = google_maps_directions(
                        st.session_state.get("station_search_label", ""),
                        destination,
                    )

                    st.link_button(
                        "Get directions",
                        directions_url,
                        key=f"station_directions_{index}",
                    )

            st.caption(
                "OpenStreetMap data may be incomplete or outdated. "
                "Connector type, operating hours, pricing, live occupancy, "
                "and charger functionality are not guaranteed by this search."
            )


# ============================================================
# TAB 3: AI MOBILITY ASSISTANT
# ============================================================

with tab_ai:
    st.subheader("Ask VoltPilot")
    st.write(
        "Ask about EV range, battery usage, charging, route preparation, "
        "electric mobility, or your trip calculations."
    )

    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_question = st.chat_input(
        "Ask your EV mobility question...",
        key="mobility_chat_input",
    )

    if user_question:
        st.session_state["chat_history"].append(
            {
                "role": "user",
                "content": user_question,
            }
        )

        with st.chat_message("user"):
            st.markdown(user_question)

        system_prompt = """
        You are VoltPilot, a helpful AI-powered electric mobility assistant.

        Help users understand EV range, charging calculations, battery
        efficiency, trip preparation, connector compatibility, charging
        etiquette, and sustainable mobility.

        Be practical and transparent. Do not invent real-time charger
        availability, live traffic, station pricing, or vehicle specifications.
        Explain that range and charging estimates are approximate.

        If asked about safety-critical vehicle faults, recommend checking the
        vehicle manual and consulting a qualified service professional.
        """

        conversation = [
            ("system", system_prompt),
        ]

        # Keep a limited amount of recent history for context.
        for item in st.session_state["chat_history"][-12:]:
            conversation.append(
                (item["role"], item["content"])
            )

        with st.chat_message("assistant"):
            with st.spinner("VoltPilot is thinking..."):
                ai_reply = ask_ai(conversation)

            st.markdown(ai_reply)

        st.session_state["chat_history"].append(
            {
                "role": "assistant",
                "content": ai_reply,
            }
        )

        st.session_state["last_ai_reply"] = ai_reply

    col_clear, col_voice = st.columns(2)

    with col_clear:
        if st.button("🗑️ Clear conversation", use_container_width=True):
            st.session_state["chat_history"] = []
            st.session_state["last_ai_reply"] = ""
            st.rerun()

    with col_voice:
        if st.button(
            "🔊 Generate speech for latest reply",
            use_container_width=True,
        ):
            latest_reply = st.session_state.get("last_ai_reply", "")

            if latest_reply:
                with st.spinner("Generating voice response..."):
                    audio_output = generate_speech(latest_reply)

                if audio_output:
                    st.audio(audio_output, format="audio/mpeg")
            else:
                st.info("Ask a question first.")


# ============================================================
# TAB 4: VOICE ASSISTANT
# ============================================================

with tab_voice:
    st.subheader("Talk to VoltPilot")
    st.write(
        "Record a question, transcribe it, and send the transcript to the AI assistant."
    )

    if not OPENAI_API_KEY:
        st.warning(
            "Voice transcription and speech generation require a valid "
            "OpenAI API key in your .env file."
        )

    if mic_recorder is None:
        st.error(
            "The microphone component is unavailable. Install it with: "
            "`./venv/bin/python -m pip install streamlit-mic-recorder`"
        )
    else:
        st.markdown("### Record your question")

        try:
            audio_data = mic_recorder(
                start_prompt="🎙️ Start recording",
                stop_prompt="⏹️ Stop recording",
                just_once=True,
                use_container_width=True,
                key="voltpilot_microphone",
            )
        except Exception as exc:
            audio_data = None
            st.error(f"Microphone component error: {exc}")

        if audio_data and audio_data.get("bytes"):
            if st.button("📝 Transcribe recording", key="transcribe_button"):
                with st.spinner("Transcribing your audio..."):
                    transcript = transcribe_audio(audio_data["bytes"])

                st.session_state["last_transcript"] = transcript

        transcript = st.session_state.get("last_transcript", "")

        if transcript:
            st.markdown("### Transcript")

            edited_transcript = st.text_area(
                "Review or edit your question",
                value=transcript,
                height=120,
                key="edited_voice_transcript",
            )

            if st.button(
                "🤖 Ask VoltPilot",
                use_container_width=True,
                key="ask_from_voice",
            ):
                if edited_transcript.strip():
                    system_prompt = (
                        "You are VoltPilot, an EV mobility assistant. "
                        "Give practical and accurate answers. "
                        "Never claim to know live charger availability unless "
                        "that information has actually been verified."
                    )

                    with st.spinner("Generating AI response..."):
                        reply = ask_ai(
                            [
                                ("system", system_prompt),
                                ("human", edited_transcript.strip()),
                            ]
                        )

                    st.session_state["last_ai_reply"] = reply

                    st.markdown("### VoltPilot response")
                    st.markdown(reply)

                    st.session_state["chat_history"].append(
                        {
                            "role": "user",
                            "content": edited_transcript.strip(),
                        }
                    )

                    st.session_state["chat_history"].append(
                        {
                            "role": "assistant",
                            "content": reply,
                        }
                    )

                    with st.spinner("Generating spoken response..."):
                        spoken_audio = generate_speech(reply)

                    if spoken_audio:
                        st.audio(spoken_audio, format="audio/mpeg")


# ============================================================
# FOOTER
# ============================================================

st.divider()

footer_col1, footer_col2 = st.columns(2)

with footer_col1:
    st.caption("⚡ VoltPilot — Predict range. Find chargers. Drive smarter.")

with footer_col2:
    st.caption(
        "Educational project. Verify route conditions and charger information "
        "before starting a real journey."
    )
