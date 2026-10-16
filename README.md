
# ⚡ VoltPilot
### Predict range. Find chargers. Drive smarter.

**VoltPilot** is an AI-powered electric mobility assistant built with Python and Streamlit. It helps EV users estimate driving range, calculate charging requirements and costs, discover mapped charging stations, and get AI-powered guidance for electric vehicle journeys.

## 🚀 Features

- 🔋 **EV Range Calculator** — Estimate usable battery range based on battery capacity, state of charge, and energy consumption.
- 🧭 **Trip Energy Planner** — Estimate trip energy requirements with an adjustable safety buffer.
- ⚡ **Charging Estimator** — Calculate approximate charging time and electricity cost.
- 🗺️ **Nearby Station Discovery** — Search mapped EV charging stations and petrol pumps using OpenStreetMap.
- 📍 **Location Search** — Find places using OpenStreetMap's Nominatim service.
- 🛣️ **Route Directions** — Open routes in Google Maps.
- 🤖 **AI Mobility Assistant** — Ask electric mobility questions using LangChain and OpenAI.
- 🎙️ **Voice Assistant** — Supports audio transcription and AI-generated speech when configured.
- 📊 **Interactive Dashboard** — Explore trip calculations and station information through Streamlit.

## 🛠️ Tech Stack

- Python
- Streamlit
- LangChain
- OpenAI API
- Pandas
- Requests
- OpenStreetMap Nominatim
- OpenStreetMap Overpass API
- Google Maps Directions URLs

## 📁 Project Structure

```text
VoltPilot/
├── app.py
├── ev_planner.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
└── assets/
    └── voltpilot-dashboard.png
```

*The `assets/` folder and screenshot are optional. Keep only files and modules that actually exist in your repository.*

## ⚙️ Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/varadshinde2505/VoltPilot.git
cd VoltPilot
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
```

### 3. Activate the environment

**macOS / Linux**

```bash
source venv/bin/activate
```

**Windows**

```bash
venv\Scripts\activate
```

### 4. Install dependencies

```bash
python -m pip install -r requirements.txt
```

If a dependency is missing, install the required package in your active environment.

### 5. Configure environment variables

Create a `.env` file in the project root.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Replace the placeholder with your own API key. Never commit your actual `.env` file or expose API keys in screenshots or source code.

### 6. Run VoltPilot

```bash
streamlit run app.py
```

Streamlit will display a local URL in the terminal. Open it in your browser.

## 🔐 API Key and Privacy

VoltPilot uses an OpenAI API key for AI chat, transcription, and speech features. API access and model availability depend on your OpenAI account.

Keep credentials private. Do not upload `.env`, API keys, or other secrets to GitHub.

## ⚠️ Limitations

- Range, charging time, energy usage, and cost calculations are estimates.
- Real-world EV range varies with traffic, speed, temperature, terrain, load, and battery condition.
- OpenStreetMap data may be incomplete or outdated.
- Station listings do not guarantee live charger availability, working status, connector compatibility, or current pricing.
- Google Maps provides route navigation; this project does not independently verify live traffic or guarantee a route's suitability.
- AI-generated responses may require independent verification.

## 🔮 Future Improvements

- EV make, model, and variant selection
- Vehicle-specific battery and efficiency profiles
- Live charger availability and pricing integrations
- Route-aware charging-stop recommendations
- Interactive map markers and distance estimates
- Trip history and energy-consumption analytics
- Improved responsive design and deployment

## 🤝 Contributing

Contributions, suggestions, and bug reports are welcome.

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Push your branch.
5. Open a pull request.

## 📄 License

See the `LICENSE` file for licensing information.

## 👨‍💻 Author

**Varad Shinde**

GitHub: [@varadshinde2505](https://github.com/varadshinde2505)

---

*VoltPilot — exploring smarter electric mobility through AI and software.*
>>>>>>> 5cf574ec69bffc4463743f289d69b722fd642f51

*VoltPilot — exploring smarter electric mobility through AI and software.*
