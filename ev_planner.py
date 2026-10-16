
from urllib.parse import urlencode

import streamlit as st


def calculate_ev_plan(
    battery_kwh: float,
    soc_percent: float,
    efficiency_kwh_per_100km: float,
    trip_distance_km: float,
    reserve_percent: float,
    target_soc_percent: float,
    charger_power_kw: float,
    charging_efficiency_percent: float,
    price_per_kwh: float,
):
    """Return transparent EV range, energy, charging-time and cost estimates."""

    usable_soc_percent = max(0.0, soc_percent - reserve_percent)

    available_energy_kwh = battery_kwh * usable_soc_percent / 100
    estimated_range_km = (
        available_energy_kwh / efficiency_kwh_per_100km * 100
    )

    trip_energy_kwh = (
        trip_distance_km * efficiency_kwh_per_100km / 100
    )

    arrival_energy_kwh = battery_kwh * soc_percent / 100 - trip_energy_kwh
    arrival_soc_percent = arrival_energy_kwh / battery_kwh * 100

    required_departure_soc_percent = (
        reserve_percent
        + trip_energy_kwh / battery_kwh * 100
    )

    trip_feasible = (
        estimated_range_km >= trip_distance_km
        and arrival_soc_percent >= reserve_percent
    )

    energy_to_target_kwh = max(
        0.0,
        battery_kwh * (target_soc_percent - soc_percent) / 100,
    )

    # Charging losses mean the charger must supply more energy than
    # the battery ultimately stores.
    energy_from_charger_kwh = (
        energy_to_target_kwh / (charging_efficiency_percent / 100)
    )

    estimated_charging_hours = (
        energy_from_charger_kwh / charger_power_kw
    )

    return {
        "available_energy_kwh": available_energy_kwh,
        "estimated_range_km": estimated_range_km,
        "trip_energy_kwh": trip_energy_kwh,
        "arrival_energy_kwh": arrival_energy_kwh,
        "arrival_soc_percent": arrival_soc_percent,
        "required_departure_soc_percent": required_departure_soc_percent,
        "trip_feasible": trip_feasible,
        "energy_to_target_kwh": energy_to_target_kwh,
        "energy_from_charger_kwh": energy_from_charger_kwh,
        "estimated_charging_hours": estimated_charging_hours,
        "estimated_charging_cost": energy_from_charger_kwh * price_per_kwh,
    }


def render_ev_planner():
    """Render the EV planner and return the latest trip inputs."""

    st.header("⚡ EV Range & Charging Planner")
    st.caption(
        "Estimate trip feasibility, battery reserve, charging time and cost. "
        "Results depend on your inputs and are not live vehicle telemetry."
    )

    with st.form("ev_range_planner_form"):
        st.subheader("1. Vehicle and battery")

        col1, col2, col3 = st.columns(3)

        with col1:
            vehicle_name = st.text_input(
                "Vehicle model",
                value="My EV",
                help="Enter your EV model for your trip notes.",
            )
            battery_kwh = st.number_input(
                "Usable battery capacity (kWh)",
                min_value=1.0,
                max_value=300.0,
                value=40.0,
                step=1.0,
            )

        with col2:
            soc_percent = st.slider(
                "Current battery (%)",
                min_value=0,
                max_value=100,
                value=60,
            )
            efficiency = st.number_input(
                "Consumption (kWh/100 km)",
                min_value=1.0,
                max_value=60.0,
                value=15.0,
                step=0.5,
                help="Use your vehicle's typical real-world consumption.",
            )

        with col3:
            reserve_percent = st.slider(
                "Minimum arrival reserve (%)",
                min_value=0,
                max_value=50,
                value=15,
            )
            target_soc = st.slider(
                "Target battery after charging (%)",
                min_value=20,
                max_value=100,
                value=80,
            )

        st.subheader("2. Trip details")

        col4, col5 = st.columns(2)

        with col4:
            origin = st.text_input("Starting area", value="Thane, Maharashtra")
            destination = st.text_input(
                "Destination",
                placeholder="e.g. Pune, Maharashtra",
            )

        with col5:
            distance_km = st.number_input(
                "One-way trip distance (km)",
                min_value=0.0,
                max_value=3000.0,
                value=120.0,
                step=5.0,
                help=(
                    "Enter the driving distance from your route. "
                    "This is not automatically fetched from Google Maps."
                ),
            )
            route_buffer_percent = st.slider(
                "Extra trip energy buffer (%)",
                min_value=0,
                max_value=40,
                value=10,
                help="Adds a margin for traffic, weather and driving conditions.",
            )

        st.subheader("3. Charging assumptions")

        col6, col7, col8 = st.columns(3)

        with col6:
            charger_power_kw = st.number_input(
                "Charger power (kW)",
                min_value=1.0,
                max_value=500.0,
                value=30.0,
                step=1.0,
            )

        with col7:
            charging_efficiency = st.slider(
                "Charging efficiency (%)",
                min_value=70,
                max_value=100,
                value=90,
            )

        with col8:
            price_per_kwh = st.number_input(
                "Charging tariff (₹/kWh)",
                min_value=0.0,
                max_value=200.0,
                value=18.0,
                step=1.0,
            )

        submitted = st.form_submit_button(
            "Calculate EV Trip Plan",
            type="primary",
            use_container_width=True,
        )

    if not submitted:
        st.info("Enter your trip details and calculate your EV plan.")
        return None

    if not origin.strip() or not destination.strip():
        st.error("Please enter both a starting area and a destination.")
        return None

    if distance_km <= 0:
        st.error("Trip distance must be greater than zero.")
        return None

    if battery_kwh <= 0 or efficiency <= 0 or charger_power_kw <= 0:
        st.error("Battery capacity, consumption and charger power must be positive.")
        return None

    if reserve_percent >= target_soc:
        st.error("The target battery percentage must be above the reserve.")
        return None

    # Include a buffer in the energy requirement, but display the
    # original route distance separately.
    buffered_distance_km = distance_km * (1 + route_buffer_percent / 100)

    plan = calculate_ev_plan(
        battery_kwh=battery_kwh,
        soc_percent=soc_percent,
        efficiency_kwh_per_100km=efficiency,
        trip_distance_km=buffered_distance_km,
        reserve_percent=reserve_percent,
        target_soc_percent=target_soc,
        charger_power_kw=charger_power_kw,
        charging_efficiency_percent=charging_efficiency,
        price_per_kwh=price_per_kwh,
    )

    st.divider()
    st.subheader("Your trip analysis")

    st.caption(
        f"{vehicle_name.strip() or 'Your EV'} · "
        f"{distance_km:.0f} km route · "
        f"{buffered_distance_km:.1f} km planning distance including buffer"
    )

    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Estimated range",
        f"{plan['estimated_range_km']:.0f} km",
        help="Range available above your chosen battery reserve.",
    )
    m2.metric(
        "Trip energy",
        f"{plan['trip_energy_kwh']:.1f} kWh",
        help="Includes the extra trip-energy buffer.",
    )
    m3.metric(
        "Estimated arrival battery",
        f"{plan['arrival_soc_percent']:.1f}%",
        help="Projected battery after the buffered trip.",
    )

    if plan["trip_feasible"]:
        st.success(
            "The trip appears feasible under your assumptions, "
            "with your selected battery reserve."
        )
    else:
        st.warning(
            "Your current battery may not be enough to complete the "
            "buffered trip while keeping your chosen reserve. Plan a "
            "compatible charging stop before departure."
        )

    if plan["required_departure_soc_percent"] > 100:
        st.error(
            "The estimated required departure charge exceeds 100%. "
            "You will need a charging stop or a shorter route."
        )
    else:
        st.write(
            "Estimated minimum departure charge to preserve your reserve: "
            f"**{plan['required_departure_soc_percent']:.1f}%**."
        )

    st.progress(max(0.0, min(1.0, soc_percent / 100)))
    st.caption(f"Starting battery: {soc_percent}%")

    st.subheader("Charging estimate")

    c1, c2, c3 = st.columns(3)
    c1.metric(
        "Energy to add",
        f"{plan['energy_to_target_kwh']:.1f} kWh",
    )
    c2.metric(
        "Approx. charging time",
        f"{plan['estimated_charging_hours'] * 60:.0f} min",
        help=(
            "Simplified estimate assuming constant charger power. "
            "Actual charging slows at higher battery levels."
        ),
    )
    c3.metric(
        "Estimated charging cost",
        f"₹{plan['estimated_charging_cost']:.0f}",
        help="Uses the tariff you entered, including estimated charging losses.",
    )

    st.caption(
        "Charging estimate assumes the current battery is charged to your "
        "selected target. Real charging time depends on the vehicle, charger, "
        "temperature and battery state of charge."
    )

    st.subheader("Continue with your existing mobility tools")

    directions_url = (
        "https://www.google.com/maps/dir/?"
        + urlencode(
            {
                "api": "1",
                "origin": origin.strip(),
                "destination": destination.strip(),
                "travelmode": "driving",
            }
        )
    )

    st.link_button(
        "Open driving directions in Google Maps",
        directions_url,
        use_container_width=True,
    )

    st.info(
        "Next: use your existing OpenStreetMap EV charging search to find "
        "stations along or near the route. Confirm connector compatibility, "
        "operating status and availability with the charging operator."
    )

    result = {
        "vehicle_name": vehicle_name.strip() or "Your EV",
        "origin": origin.strip(),
        "destination": destination.strip(),
        "distance_km": distance_km,
        "buffered_distance_km": buffered_distance_km,
        "battery_kwh": battery_kwh,
        "soc_percent": soc_percent,
        "efficiency_kwh_per_100km": efficiency,
        "reserve_percent": reserve_percent,
        "plan": plan,
        "directions_url": directions_url,
    }

    st.session_state["ev_trip_plan"] = result
    return result
