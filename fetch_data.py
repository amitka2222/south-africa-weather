import datetime
import json
import os
import sys
import requests

API_URL = "https://api.open-meteo.com/v1/forecast?latitude=-26.316&longitude=27.833&current_weather=true"

# WMO Weather interpretation codes (WW)
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
    96: ("Thunderstorm with slight hail", "⛈️"),
    99: ("Thunderstorm with heavy hail", "⛈️"),
}


def get_weather_info(weather_code):
    return WEATHER_CODES.get(weather_code, ("Current Weather", "🌡️"))


def fetch_weather():
    response = requests.get(API_URL, timeout=15)
    response.raise_for_status()
    return response.json()


def generate_html(weather_data):
    current = weather_data.get("current_weather", {})
    temperature = current.get("temperature", "N/A")
    windspeed = current.get("windspeed", "N/A")
    winddirection = current.get("winddirection", "N/A")
    weather_code = current.get("weathercode", 0)
    api_time = current.get("time", "")

    condition_text, condition_icon = get_weather_info(weather_code)

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    # Lenasia is in SAST (UTC+2)
    sast_tz = datetime.timezone(datetime.timedelta(hours=2))
    now_sast = now_utc.astimezone(sast_tz)

    updated_sast_str = now_sast.strftime("%A, %d %B %Y | %H:%M SAST")
    updated_utc_str = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lenasia Weather Station | Live Forecast</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-gradient: radial-gradient(circle at 20% 20%, #1e293b 0%, #0f172a 100%);
            --card-bg: rgba(30, 41, 59, 0.7);
            --card-border: rgba(255, 255, 255, 0.08);
            --card-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255, 255, 255, 0.05);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-blue: #38bdf8;
            --accent-teal: #2dd4bf;
            --accent-amber: #fbbf24;
            --pill-bg: rgba(56, 189, 248, 0.1);
            --pill-border: rgba(56, 189, 248, 0.25);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #090d16;
            background-image: 
                radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.12) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(45, 212, 191, 0.1) 0px, transparent 50%),
                radial-gradient(at 50% 50%, #0f172a 0px, #070a12 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 24px 16px;
            color: var(--text-primary);
        }}

        .container {{
            width: 100%;
            max-width: 480px;
            margin: auto;
        }}

        .weather-card {{
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid var(--card-border);
            border-radius: 28px;
            padding: 36px 32px;
            box-shadow: var(--card-shadow);
            position: relative;
            overflow: hidden;
        }}

        .weather-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent-blue), var(--accent-teal), transparent);
            opacity: 0.8;
        }}

        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 24px;
        }}

        .location-group {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .location-title {{
            font-size: 1.75rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .location-sub {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .badge-live {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 9999px;
            background: var(--pill-bg);
            border: 1px solid var(--pill-border);
            color: var(--accent-blue);
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .pulse-dot {{
            width: 8px;
            height: 8px;
            background-color: #22c55e;
            border-radius: 50%;
            box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
            animation: pulse 2s infinite cubic-bezier(0.66, 0, 0, 1);
        }}

        @keyframes pulse {{
            to {{
                box-shadow: 0 0 0 8px rgba(34, 197, 94, 0);
            }}
        }}

        .hero-weather {{
            text-align: center;
            padding: 20px 0 28px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            margin-bottom: 24px;
        }}

        .weather-icon {{
            font-size: 4rem;
            line-height: 1;
            margin-bottom: 12px;
            filter: drop-shadow(0 8px 16px rgba(0,0,0,0.3));
        }}

        .temp-display {{
            font-size: 4.5rem;
            font-weight: 800;
            line-height: 1;
            letter-spacing: -0.04em;
            background: linear-gradient(180deg, #ffffff 30%, #cbd5e1 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}

        .temp-unit {{
            font-size: 2.25rem;
            font-weight: 400;
            vertical-align: super;
            color: var(--accent-blue);
            -webkit-text-fill-color: var(--accent-blue);
        }}

        .condition-badge {{
            display: inline-block;
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent-teal);
            margin-top: 4px;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            margin-bottom: 24px;
        }}

        .metric-card {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 18px;
            padding: 16px 18px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}

        .metric-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(56, 189, 248, 0.3);
        }}

        .metric-label {{
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .metric-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #ffffff;
        }}

        .metric-sub {{
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}

        .footer {{
            text-align: center;
            font-size: 0.75rem;
            color: var(--text-muted);
            line-height: 1.6;
        }}

        .footer a {{
            color: var(--accent-blue);
            text-decoration: none;
        }}

        .footer a:hover {{
            text-decoration: underline;
        }}

        .timestamp {{
            color: var(--text-secondary);
            font-weight: 500;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <main class="container">
        <div class="weather-card">
            <header class="header">
                <div class="location-group">
                    <h1 class="location-title">Lenasia</h1>
                    <div class="location-sub">
                        <span>Gauteng, South Africa</span>
                        <span>•</span>
                        <span>-26.316°, 27.833°</span>
                    </div>
                </div>
                <div class="badge-live">
                    <span class="pulse-dot"></span>
                    <span>Live</span>
                </div>
            </header>

            <section class="hero-weather">
                <div class="weather-icon">{condition_icon}</div>
                <div class="temp-display">{temperature}<span class="temp-unit">°C</span></div>
                <div class="condition-badge">{condition_text}</div>
            </section>

            <section class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-label">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/></svg>
                        Wind Speed
                    </div>
                    <div class="metric-value">{windspeed} <span style="font-size: 0.875rem; font-weight: 500; color: var(--text-secondary);">km/h</span></div>
                    <div class="metric-sub">Direction: {winddirection}°</div>
                </div>

                <div class="metric-card">
                    <div class="metric-label">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/></svg>
                        Temperature
                    </div>
                    <div class="metric-value">{temperature} <span style="font-size: 0.875rem; font-weight: 500; color: var(--text-secondary);">°C</span></div>
                    <div class="metric-sub">Lenasia Station</div>
                </div>
            </section>

            <footer class="footer">
                <div>Automated via <strong>GitHub Actions</strong> &bull; Source: <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo API</a></div>
                <div class="timestamp">Last updated: {updated_sast_str}</div>
                <div class="timestamp" style="font-size: 0.7rem; color: var(--text-muted);">({updated_utc_str})</div>
            </footer>
        </div>
    </main>
</body>
</html>
"""
    return html_content


def main():
    print("Fetching weather data for Lenasia...")
    try:
        data = fetch_weather()
        current = data.get("current_weather", {})
        temp = current.get("temperature")
        wind = current.get("windspeed")
        print(f"Data retrieved successfully: Temp = {temp}°C, Wind Speed = {wind} km/h")
        
        html = generate_html(data)
        output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"Successfully generated {output_file}")
    except Exception as e:
        print(f"Error fetching data or generating HTML: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
