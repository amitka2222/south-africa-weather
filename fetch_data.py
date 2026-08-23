import datetime
import json
import os
import sys
import requests

# Major cities covering all provinces across South Africa
CITIES = [
    {
        "name": "Johannesburg",
        "province": "Gauteng",
        "lat": -26.2041,
        "lon": 28.0473,
        "tag": "Inland / Economic Hub"
    },
    {
        "name": "Cape Town",
        "province": "Western Cape",
        "lat": -33.9249,
        "lon": 18.4241,
        "tag": "Coastal / Atlantic"
    },
    {
        "name": "Durban",
        "province": "KwaZulu-Natal",
        "lat": -29.8587,
        "lon": 31.0218,
        "tag": "Coastal / Indian Ocean"
    },
    {
        "name": "Pretoria",
        "province": "Gauteng",
        "lat": -25.7479,
        "lon": 28.2293,
        "tag": "Administrative Capital"
    },
    {
        "name": "Gqeberha",
        "province": "Eastern Cape",
        "lat": -33.9608,
        "lon": 25.6022,
        "tag": "Coastal / Windy City"
    },
    {
        "name": "Bloemfontein",
        "province": "Free State",
        "lat": -29.1181,
        "lon": 26.2249,
        "tag": "Judicial Capital / Central"
    },
    {
        "name": "Mbombela",
        "province": "Mpumalanga",
        "lat": -25.4753,
        "lon": 30.9694,
        "tag": "Lowveld / Kruger Gateway"
    },
    {
        "name": "Polokwane",
        "province": "Limpopo",
        "lat": -23.9045,
        "lon": 29.4689,
        "tag": "Northern Hub"
    },
    {
        "name": "Kimberley",
        "province": "Northern Cape",
        "lat": -28.7282,
        "lon": 24.7499,
        "tag": "Diamond City / Karoo"
    },
]

WEATHER_CODES = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Depositing rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Moderate drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    61: ("Slight rain", "🌧️"),
    63: ("Moderate rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    71: ("Slight snow fall", "🌨️"),
    73: ("Moderate snow fall", "🌨️"),
    75: ("Heavy snow fall", "❄️"),
    80: ("Slight rain showers", "🌦️"),
    81: ("Moderate rain showers", "🌧️"),
    82: ("Violent rain showers", "⛈️"),
    95: ("Thunderstorm", "⚡"),
    96: ("Thunderstorm with hail", "⛈️"),
    99: ("Heavy thunderstorm", "⛈️"),
}


def get_weather_info(weather_code):
    return WEATHER_CODES.get(weather_code, ("Fair", "🌡️"))


def fetch_south_africa_weather():
    lats = ",".join(str(c["lat"]) for c in CITIES)
    lons = ",".join(str(c["lon"]) for c in CITIES)
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lats}&longitude={lons}&current_weather=true"
    
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    data = response.json()
    
    if isinstance(data, dict):
        data = [data]
        
    results = []
    for city, item in zip(CITIES, data):
        current = item.get("current_weather", {})
        temp = current.get("temperature", 0.0)
        wind = current.get("windspeed", 0.0)
        direction = current.get("winddirection", 0)
        code = current.get("weathercode", 0)
        condition_text, condition_icon = get_weather_info(code)
        
        results.append({
            "name": city["name"],
            "province": city["province"],
            "tag": city["tag"],
            "temperature": temp,
            "windspeed": wind,
            "winddirection": direction,
            "condition_text": condition_text,
            "condition_icon": condition_icon,
        })
    return results


def generate_html(weather_results):
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    sast_tz = datetime.timezone(datetime.timedelta(hours=2))
    now_sast = now_utc.astimezone(sast_tz)

    updated_sast_str = now_sast.strftime("%A, %d %B %Y | %H:%M SAST")
    updated_utc_str = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    # Aggregate stats
    temps = [w["temperature"] for w in weather_results if isinstance(w["temperature"], (int, float))]
    avg_temp = round(sum(temps) / len(temps), 1) if temps else 0
    max_temp = max(temps) if temps else 0
    min_temp = min(temps) if temps else 0
    hottest_city = next((w["name"] for w in weather_results if w["temperature"] == max_temp), "N/A")
    coolest_city = next((w["name"] for w in weather_results if w["temperature"] == min_temp), "N/A")

    # City cards HTML
    city_cards_html = ""
    for city in weather_results:
        city_cards_html += f"""
        <article class="city-card">
            <div class="card-header">
                <div>
                    <h3 class="city-name">{city['name']}</h3>
                    <p class="city-province">{city['province']} &bull; <span class="city-tag">{city['tag']}</span></p>
                </div>
                <div class="weather-icon-badge">{city['condition_icon']}</div>
            </div>
            
            <div class="card-main">
                <div class="card-temp">{city['temperature']}<span class="unit">°C</span></div>
                <div class="condition-pill">{city['condition_text']}</div>
            </div>

            <div class="card-metrics">
                <div class="metric-item">
                    <span class="metric-key">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/></svg>
                        Wind
                    </span>
                    <span class="metric-val">{city['windspeed']} km/h</span>
                </div>
                <div class="metric-item">
                    <span class="metric-key">
                        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/></svg>
                        Heading
                    </span>
                    <span class="metric-val">{city['winddirection']}°</span>
                </div>
            </div>
        </article>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>South Africa Live Weather | National Station & Forecast</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #070a12;
            --surface: rgba(18, 25, 43, 0.75);
            --surface-card: rgba(22, 32, 54, 0.65);
            --surface-hover: rgba(30, 43, 72, 0.8);
            --border: rgba(255, 255, 255, 0.08);
            --border-accent: rgba(56, 189, 248, 0.35);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-cyan: #38bdf8;
            --accent-emerald: #10b981;
            --accent-gold: #f59e0b;
            --accent-rose: #f43f5e;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg);
            background-image: 
                radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.1) 0px, transparent 40%),
                radial-gradient(at 100% 0%, rgba(16, 185, 129, 0.08) 0px, transparent 40%),
                radial-gradient(at 50% 100%, rgba(245, 158, 11, 0.06) 0px, transparent 50%);
            min-height: 100vh;
            color: var(--text-primary);
            padding: 40px 20px 60px;
        }}

        .wrapper {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        /* Header */
        .top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
            margin-bottom: 36px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}

        .flag-emblem {{
            font-size: 2.2rem;
            line-height: 1;
            filter: drop-shadow(0 4px 10px rgba(0,0,0,0.4));
        }}

        .brand-title {{
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            background: linear-gradient(135deg, #ffffff 40%, #94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .brand-subtitle {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            font-weight: 500;
        }}

        .live-tag {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34d399;
            padding: 8px 16px;
            border-radius: 9999px;
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .pulse-dot {{
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse 2s infinite cubic-bezier(0.66, 0, 0, 1);
        }}

        @keyframes pulse {{
            to {{
                box-shadow: 0 0 0 8px rgba(16, 185, 129, 0);
            }}
        }}

        /* National Overview Stats */
        .stats-banner {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 36px;
        }}

        .stat-card {{
            background: var(--surface);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 20px 24px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            position: relative;
            overflow: hidden;
        }}

        .stat-card::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--accent-cyan);
        }}

        .stat-card.hot::after {{ background: var(--accent-rose); }}
        .stat-card.cool::after {{ background: var(--accent-cyan); }}
        .stat-card.avg::after {{ background: var(--accent-gold); }}

        .stat-title {{
            font-size: 0.75rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }}

        .stat-number {{
            font-size: 2rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.02em;
        }}

        .stat-desc {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        /* Grid Section */
        .section-title {{
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
            color: #f1f5f9;
        }}

        .cities-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 48px;
        }}

        .city-card {{
            background: var(--surface-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: 22px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            transition: all 0.25s ease;
            position: relative;
        }}

        .city-card:hover {{
            background: var(--surface-hover);
            border-color: var(--border-accent);
            transform: translateY(-4px);
            box-shadow: 0 16px 32px -10px rgba(0, 0, 0, 0.5);
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 16px;
        }}

        .city-name {{
            font-size: 1.35rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.02em;
        }}

        .city-province {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: 2px;
        }}

        .city-tag {{
            color: var(--accent-cyan);
            font-weight: 500;
        }}

        .weather-icon-badge {{
            font-size: 2.2rem;
            line-height: 1;
        }}

        .card-main {{
            display: flex;
            align-items: baseline;
            gap: 12px;
            margin-bottom: 20px;
        }}

        .card-temp {{
            font-size: 3rem;
            font-weight: 800;
            line-height: 1;
            letter-spacing: -0.04em;
            color: #ffffff;
        }}

        .card-temp .unit {{
            font-size: 1.5rem;
            font-weight: 400;
            color: var(--accent-cyan);
            vertical-align: super;
        }}

        .condition-pill {{
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: var(--text-secondary);
            padding: 4px 10px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
        }}

        .card-metrics {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            padding-top: 14px;
            border-top: 1px solid rgba(255, 255, 255, 0.06);
        }}

        .metric-item {{
            display: flex;
            flex-direction: column;
            gap: 3px;
        }}

        .metric-key {{
            font-size: 0.7rem;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            display: flex;
            align-items: center;
            gap: 5px;
        }}

        .metric-val {{
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--text-primary);
        }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 24px;
            border-top: 1px solid var(--border);
            color: var(--text-muted);
            font-size: 0.8rem;
            line-height: 1.8;
        }}

        .footer a {{
            color: var(--accent-cyan);
            text-decoration: none;
        }}

        .footer a:hover {{
            text-decoration: underline;
        }}

        .footer .time-stamp {{
            color: var(--text-secondary);
            font-weight: 600;
        }}

        @media (max-width: 640px) {{
            body {{
                padding: 20px 14px 40px;
            }}
            .brand-title {{
                font-size: 1.5rem;
            }}
            .card-temp {{
                font-size: 2.5rem;
            }}
            .cities-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <header class="top-bar">
            <div class="brand">
                <span class="flag-emblem">🇿🇦</span>
                <div>
                    <h1 class="brand-title">South Africa Weather</h1>
                    <p class="brand-subtitle">Real-time provincial stations and meteorological monitoring</p>
                </div>
            </div>
            <div class="live-tag">
                <span class="pulse-dot"></span>
                <span>Active Feed</span>
            </div>
        </header>

        <!-- Stats Overview Banner -->
        <section class="stats-banner">
            <div class="stat-card avg">
                <span class="stat-title">National Average</span>
                <span class="stat-number">{avg_temp}°C</span>
                <span class="stat-desc">Across all 9 monitored regions</span>
            </div>
            <div class="stat-card hot">
                <span class="stat-title">Highest Temp</span>
                <span class="stat-number">{max_temp}°C</span>
                <span class="stat-desc">{hottest_city}</span>
            </div>
            <div class="stat-card cool">
                <span class="stat-title">Lowest Temp</span>
                <span class="stat-number">{min_temp}°C</span>
                <span class="stat-desc">{coolest_city}</span>
            </div>
        </section>

        <!-- Cities Grid -->
        <h2 class="section-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>
            Major Cities & Provincial Stations
        </h2>

        <section class="cities-grid">
            {city_cards_html}
        </section>

        <footer class="footer">
            <div>Automated by <strong>GitHub Actions</strong> &bull; Data provided by <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo API</a></div>
            <div>Last automated update: <span class="time-stamp">{updated_sast_str}</span> <span style="font-size: 0.72rem; color: var(--text-muted);">({updated_utc_str})</span></div>
        </footer>
    </div>
</body>
</html>
"""
    return html_content


def main():
    print("Fetching real-time weather data for South Africa...")
    try:
        results = fetch_south_africa_weather()
        print(f"Successfully fetched weather for {len(results)} South African cities.")
        for r in results:
            print(f" - {r['name']} ({r['province']}): {r['temperature']}°C, {r['windspeed']} km/h [{r['condition_text']}]")

        html = generate_html(results)
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"Successfully updated {output_file}")
    except Exception as e:
        print(f"Error updating South Africa weather data: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
