# 🇿🇦 South Africa Live Weather

A live weather dashboard for **12 stations across all 9 South African provinces**, built
on the free [Open-Meteo](https://open-meteo.com/) API and hosted as static files on
Cloudflare.

**Live site:** <https://south-africa-weather.amitka.workers.dev/>

---

## How it works

The page is genuinely live: **the browser calls Open-Meteo itself on every visit**, so
what you see is current to within about 15 minutes, not to the last build.

```
                    ┌──────────────────────────────┐
  every 3 hours     │  GitHub Actions              │
  ────────────────► │  python fetch_data.py        │
                    │  → commits data/weather.json │
                    └──────────────┬───────────────┘
                                   │ push
                    ┌──────────────▼───────────────┐
                    │  Cloudflare (static files)   │
                    └──────────────┬───────────────┘
                                   │ page load
                    ┌──────────────▼───────────────┐
                    │  Browser                     │
                    │  1. paints data/weather.json │  ← instant, no spinner
                    │  2. fetches api.open-meteo   │  ← live values
                    │  3. re-fetches every 10 min  │
                    └──────────────────────────────┘
```

The committed snapshot earns its place three ways: the page paints real numbers before
any network call finishes, it keeps working when Open-Meteo is unreachable, and
`data/weather.json` doubles as a small public JSON feed anyone can reuse.

Open-Meteo sends `Access-Control-Allow-Origin: *` and needs no API key, so the browser
can call it directly with nothing secret in the client.

---

## Stations

| Province | Station | Note |
| --- | --- | --- |
| Gauteng | Johannesburg | Highveld / economic hub |
| Gauteng | Pretoria | Administrative capital |
| Western Cape | Cape Town | Coastal / Atlantic |
| KwaZulu-Natal | Durban | Coastal / Indian Ocean |
| Eastern Cape | Gqeberha | Coastal / Windy City |
| Free State | Bloemfontein | Judicial capital |
| Mpumalanga | Mbombela | Lowveld / Kruger gateway |
| Limpopo | Polokwane | Northern hub |
| North West | Mahikeng | Provincial capital |
| Northern Cape | Kimberley | Diamond City / Karoo |
| Northern Cape | Upington | Kalahari, usually the hottest reading |
| Northern Cape | Sutherland | Karoo, usually the coldest reading |

Stations live in [`data/cities.json`](data/cities.json) — the single source of truth,
read by both the Python job and the browser. Add a `{ id, name, province, tag, lat, lon }`
entry and both pick it up; nothing else needs to change.

---

## What the dashboard shows

- **Per station** — temperature, feels-like, condition, today's high/low, humidity,
  wind speed with gusts and a compass arrow, rain probability and UV index.
- **24-hour trend** — an inline SVG sparkline per station, no charting library.
- **Expandable detail** — daylight progress bar with sunrise/sunset, a 7-day outlook
  with temperature-range bars, plus pressure, cloud cover, rainfall, peak wind,
  elevation and coordinates.
- **National summary** — average, warmest, coolest, highest rain chance, windiest.
- **Controls** — filter by city or province, six sort orders, °C/°F and km/h/mph toggle,
  and a light/dark theme. All preferences persist in `localStorage`.
- **Honest status** — the badge reports whether you are seeing live data or a snapshot,
  and how old it is. It never claims "live" for stale data.

---

## Project layout

```
index.html            static shell — markup only, no generated content
assets/styles.css     light and dark themes as CSS custom properties
assets/app.js         fetch, normalise, render, interactions (no dependencies)
assets/favicon.svg
data/cities.json      canonical station list (hand-edited)
data/weather.json     generated fallback snapshot (committed by CI)
fetch_data.py         builds data/weather.json from Open-Meteo
```

---

## Local development

```bash
git clone https://github.com/amitka2222/south-africa-weather.git
cd south-africa-weather
pip install -r requirements.txt
python fetch_data.py          # refresh data/weather.json
python -m http.server 8788    # then open http://localhost:8788
```

Serve over HTTP rather than opening `index.html` from disk — `fetch` of the local JSON
files is blocked on `file://`.

To check the API without touching the committed snapshot:

```bash
python fetch_data.py --dry-run
```

---

## Automation notes

[`.github/workflows/update.yml`](.github/workflows/update.yml) runs every 3 hours and on
manual dispatch. It commits `data/weather.json` only when the content actually changed,
so the history stays readable instead of filling up with whole-page rewrites.

Two things worth knowing about GitHub's scheduler: cron runs on shared runners can be
delayed by 10–30 minutes at busy times, and **scheduled workflows are disabled
automatically after 60 days without repository activity** — push something or re-enable
the workflow if the snapshot goes quiet.

---

## Credits

Weather data by [Open-Meteo](https://open-meteo.com/), licensed CC BY 4.0.

## License

MIT
