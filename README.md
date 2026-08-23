# 🇿🇦 South Africa Live Weather Station

An automated, self-updating dashboard monitoring real-time meteorological conditions across all 9 provinces and major hubs in South Africa.

Powered by Open-Meteo API and automated using GitHub Actions.

---

## 🌟 Features

- **National Overview**: National average temperature, highest, and lowest recorded temperatures in real-time.
- **Provincial Hubs Monitored**:
  - **Johannesburg** (Gauteng - Inland / Economic Hub)
  - **Cape Town** (Western Cape - Coastal / Atlantic)
  - **Durban** (KwaZulu-Natal - Coastal / Indian Ocean)
  - **Pretoria** (Gauteng - Administrative Capital)
  - **Gqeberha** (Eastern Cape - Coastal / Windy City)
  - **Bloemfontein** (Free State - Central / Judicial Capital)
  - **Mbombela** (Mpumalanga - Lowveld / Kruger Gateway)
  - **Polokwane** (Limpopo - Northern Hub)
  - **Kimberley** (Northern Cape - Karoo / Diamond City)
- **Live Metrics**: Temperature (°C), Weather Conditions & Icons, Wind Speed (km/h), and Wind Direction.
- **Automated Updates**: Powered by a GitHub Actions cron schedule running every 6 hours (`0 */6 * * *`) with bot auto-commits.
- **Responsive & Modern UI**: Built with a sleek dark aesthetic, responsive cards, and clean typography.

---

## 🚀 Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/amitka2222/south-africa-weather.git
   cd south-africa-weather
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Fetch latest weather & generate HTML**:
   ```bash
   python fetch_data.py
   ```

4. Open `index.html` in your browser.

---

## ⚙️ GitHub Actions Automation

The workflow `.github/workflows/update.yml`:
1. Executes on schedule every 6 hours (`0 */6 * * *`) and on manual dispatch (`workflow_dispatch`).
2. Runs `fetch_data.py` to retrieve the latest weather data from Open-Meteo.
3. Automatically commits and pushes changes back to `main` if changes are detected.

---

## 📄 License
MIT License
