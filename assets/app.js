/* South Africa Live Weather
 *
 * Data flow: render the cached or committed snapshot immediately so the page is
 * never blank, then fetch live conditions straight from Open-Meteo. All times in
 * the payload are Africa/Johannesburg wall-clock strings, so they are formatted
 * from the string itself and never pushed through the browser's timezone.
 */
(() => {
  "use strict";

  const API = "https://api.open-meteo.com/v1/forecast";
  const CITIES_URL = "data/cities.json";
  const SNAPSHOT_URL = "data/weather.json";
  const REFRESH_MS = 10 * 60 * 1000;   // Open-Meteo advances "current" every 15 min.
  const CACHE_TTL_MS = 10 * 60 * 1000;
  const STALE_MS = 60 * 60 * 1000;     // Older than this and we stop calling it live.

  const CURRENT_FIELDS = "temperature_2m,relative_humidity_2m,apparent_temperature,is_day," +
    "precipitation,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m";
  const HOURLY_FIELDS = "temperature_2m,precipitation_probability,weather_code";
  const DAILY_FIELDS = "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset," +
    "uv_index_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max";

  const KEY = { units: "saw:units", theme: "saw:theme", sort: "saw:sort", cache: "saw:cache" };

  /* ---------- Weather codes ---------- */

  const CODES = {
    0:  ["Clear sky", "sun", "moon"],
    1:  ["Mainly clear", "sun", "moon"],
    2:  ["Partly cloudy", "cloud-sun", "cloud-moon"],
    3:  ["Overcast", "cloud", "cloud"],
    45: ["Fog", "fog", "fog"],
    48: ["Freezing fog", "fog", "fog"],
    51: ["Light drizzle", "drizzle", "drizzle"],
    53: ["Drizzle", "drizzle", "drizzle"],
    55: ["Heavy drizzle", "drizzle", "drizzle"],
    56: ["Freezing drizzle", "sleet", "sleet"],
    57: ["Freezing drizzle", "sleet", "sleet"],
    61: ["Light rain", "rain", "rain"],
    63: ["Rain", "rain", "rain"],
    65: ["Heavy rain", "rain", "rain"],
    66: ["Freezing rain", "sleet", "sleet"],
    67: ["Freezing rain", "sleet", "sleet"],
    71: ["Light snow", "snow", "snow"],
    73: ["Snow", "snow", "snow"],
    75: ["Heavy snow", "snow", "snow"],
    77: ["Snow grains", "snow", "snow"],
    80: ["Light showers", "rain", "rain"],
    81: ["Showers", "rain", "rain"],
    82: ["Violent showers", "rain", "rain"],
    85: ["Snow showers", "snow", "snow"],
    86: ["Heavy snow showers", "snow", "snow"],
    95: ["Thunderstorm", "thunder", "thunder"],
    96: ["Thunderstorm, hail", "thunder", "thunder"],
    99: ["Severe thunderstorm", "thunder", "thunder"],
  };

  function describe(code, isDay = true) {
    const entry = CODES[code] || ["Unsettled", "cloud", "cloud"];
    return { label: entry[0], icon: isDay ? entry[1] : entry[2] };
  }

  const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                   "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];

  const compass = (deg) => COMPASS[Math.round(((deg || 0) % 360) / 22.5) % 16];

  function uvBand(uv) {
    if (uv == null) return "";
    if (uv < 3) return "Low";
    if (uv < 6) return "Moderate";
    if (uv < 8) return "High";
    if (uv < 11) return "Very high";
    return "Extreme";
  }

  /* Thermal ramp: cold blue through green to hot red, used for accents and bars. */
  function tempColor(c) {
    const t = Math.max(-5, Math.min(42, Number(c) || 0));
    const hue = 215 - ((t + 5) / 47) * 210;
    return `hsl(${hue.toFixed(0)} 82% 58%)`;
  }

  /* ---------- State ---------- */

  const state = {
    units: load(KEY.units) === "imperial" ? "imperial" : "metric",
    sort: load(KEY.sort) || "temp-desc",
    query: "",
    data: null,
    source: null,
    expanded: new Set(),
    timer: null,
  };

  function load(key) {
    try { return localStorage.getItem(key); } catch { return null; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, value); } catch { /* private mode */ }
  }

  /* ---------- Formatting ---------- */

  const isImperial = () => state.units === "imperial";

  const toTemp = (c) => (isImperial() ? c * 9 / 5 + 32 : c);
  const toSpeed = (kmh) => (isImperial() ? kmh * 0.621371 : kmh);
  const speedUnit = () => (isImperial() ? "mph" : "km/h");

  function fmtTemp(c, withDegree = true) {
    if (c == null || Number.isNaN(Number(c))) return "–";
    return `${Math.round(toTemp(Number(c)))}${withDegree ? "°" : ""}`;
  }

  const fmtSpeed = (kmh) => (kmh == null ? "–" : Math.round(toSpeed(Number(kmh))));

  /* "2026-08-23T20:00" -> "20:00". Never touches Date, so it is timezone-proof. */
  const clockOf = (iso) => (typeof iso === "string" && iso.includes("T") ? iso.slice(11, 16) : "–");

  /* "2026-08-23T20:00" -> minutes since midnight, SAST wall clock. */
  function minutesOf(iso) {
    const hhmm = clockOf(iso);
    if (hhmm === "–") return null;
    const [h, m] = hhmm.split(":").map(Number);
    return h * 60 + m;
  }

  /* Date-only construction keeps the weekday correct in any timezone. */
  function dayLabel(dateStr, index) {
    if (index === 0) return "Today";
    const [y, m, d] = dateStr.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("en-ZA", { weekday: "short" });
  }

  function relativeTime(iso) {
    const then = Date.parse(iso);
    if (Number.isNaN(then)) return "unknown";
    const mins = Math.round((Date.now() - then) / 60000);
    if (mins < 1) return "just now";
    if (mins === 1) return "1 min ago";
    if (mins < 60) return `${mins} min ago`;
    const hours = Math.round(mins / 60);
    if (hours < 24) return `${hours} h ago`;
    return `${Math.round(hours / 24)} d ago`;
  }

  const esc = (value) => String(value).replace(/[&<>"']/g,
    (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));

  const icon = (name, cls = "ico") =>
    `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;

  /* ---------- Data loading ---------- */

  async function fetchJSON(url, options = {}) {
    const response = await fetch(url, { cache: "no-store", ...options });
    if (!response.ok) throw new Error(`${url} responded ${response.status}`);
    return response.json();
  }

  function buildLiveURL(stations) {
    const params = new URLSearchParams({
      latitude: stations.map((s) => s.lat).join(","),
      longitude: stations.map((s) => s.lon).join(","),
      current: CURRENT_FIELDS,
      hourly: HOURLY_FIELDS,
      daily: DAILY_FIELDS,
      timezone: "Africa/Johannesburg",
      forecast_days: "7",
      forecast_hours: "24",
    });
    return `${API}?${params}`;
  }

  /* Reshape the raw Open-Meteo response into the same structure fetch_data.py writes. */
  function normalise(blocks, stations) {
    const list = Array.isArray(blocks) ? blocks : [blocks];
    return {
      generated: new Date().toISOString(),
      source: "live",
      stations: stations.map((station, i) => {
        const block = list[i] || {};
        const c = block.current || {};
        const daily = block.daily || {};
        const hourly = block.hourly || {};
        const days = (daily.time || []).map((date, j) => ({
          date,
          code: daily.weather_code?.[j],
          tmax: daily.temperature_2m_max?.[j],
          tmin: daily.temperature_2m_min?.[j],
          sunrise: daily.sunrise?.[j],
          sunset: daily.sunset?.[j],
          uvMax: daily.uv_index_max?.[j],
          precipSum: daily.precipitation_sum?.[j],
          precipProb: daily.precipitation_probability_max?.[j],
          windMax: daily.wind_speed_10m_max?.[j],
        }));
        return {
          id: station.id,
          name: station.name,
          province: station.province,
          tag: station.tag,
          lat: station.lat,
          lon: station.lon,
          elevation: block.elevation ?? station.elevation,
          current: {
            time: c.time,
            temp: c.temperature_2m,
            feels: c.apparent_temperature,
            humidity: c.relative_humidity_2m,
            isDay: Boolean(c.is_day ?? 1),
            precip: c.precipitation,
            code: c.weather_code,
            cloud: c.cloud_cover,
            pressure: c.pressure_msl,
            wind: c.wind_speed_10m,
            gust: c.wind_gusts_10m,
            windDir: c.wind_direction_10m,
          },
          today: days[0] || null,
          daily: days,
          hourly: (hourly.time || []).map((time, j) => ({
            time,
            temp: hourly.temperature_2m?.[j],
            precipProb: hourly.precipitation_probability?.[j],
            code: hourly.weather_code?.[j],
          })),
        };
      }),
    };
  }

  function readCache() {
    try {
      const raw = load(KEY.cache);
      if (!raw) return null;
      const entry = JSON.parse(raw);
      if (!entry?.data?.stations?.length) return null;
      if (Date.now() - Date.parse(entry.data.generated) > CACHE_TTL_MS) return null;
      return entry.data;
    } catch { return null; }
  }

  const writeCache = (data) => save(KEY.cache, JSON.stringify({ data }));

  /* ---------- Rendering: national summary ---------- */

  function renderSummary(stations) {
    const temps = stations.map((s) => s.current.temp).filter((t) => typeof t === "number");
    if (!temps.length) return;

    const avg = temps.reduce((a, b) => a + b, 0) / temps.length;
    const warmest = stations.reduce((a, b) => (b.current.temp > a.current.temp ? b : a));
    const coolest = stations.reduce((a, b) => (b.current.temp < a.current.temp ? b : a));
    const wettest = stations.reduce((a, b) =>
      ((b.today?.precipProb ?? -1) > (a.today?.precipProb ?? -1) ? b : a));
    const windiest = stations.reduce((a, b) => (b.current.wind > a.current.wind ? b : a));

    const tiles = [
      ["National average", `${fmtTemp(avg)}`, `Mean across ${stations.length} stations`, tempColor(avg)],
      ["Warmest now", fmtTemp(warmest.current.temp), `${warmest.name}, ${warmest.province}`, tempColor(warmest.current.temp)],
      ["Coolest now", fmtTemp(coolest.current.temp), `${coolest.name}, ${coolest.province}`, tempColor(coolest.current.temp)],
      ["Highest rain chance", `${wettest.today?.precipProb ?? 0}%`, `${wettest.name} today`, "var(--accent)"],
      ["Windiest now", `${fmtSpeed(windiest.current.wind)} ${speedUnit()}`, `${windiest.name}, ${compass(windiest.current.windDir)}`, "var(--good)"],
    ];

    el.summary.innerHTML = tiles.map(([label, value, note, accent]) => `
      <div class="tile" style="--tile-accent:${accent}">
        <span class="tile-label">${esc(label)}</span>
        <span class="tile-value">${esc(value)}</span>
        <span class="tile-note">${esc(note)}</span>
      </div>`).join("");
  }

  /* ---------- Rendering: 24-hour sparkline ---------- */

  function sparkline(hours) {
    const points = hours.filter((h) => typeof h.temp === "number");
    if (points.length < 2) return "";

    const W = 240, H = 40;
    const temps = points.map((h) => h.temp);
    const lo = Math.min(...temps), hi = Math.max(...temps);
    const span = hi - lo || 1;
    const x = (i) => (i / (points.length - 1)) * W;
    const y = (t) => H - ((t - lo) / span) * H;

    const line = points.map((h, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(h.temp).toFixed(1)}`).join(" ");
    const area = `${line} L${W} ${H + 4} L0 ${H + 4} Z`;

    const stamp = (i) => clockOf(points[i]?.time);
    const marks = [0, Math.floor(points.length / 3), Math.floor((2 * points.length) / 3), points.length - 1];

    return `
      <div class="spark">
        <div class="spark-head">
          <span>Next ${points.length} hours</span>
          <span class="spark-label">${fmtTemp(lo)} to ${fmtTemp(hi)}</span>
        </div>
        <svg viewBox="0 -4 ${W} ${H + 8}" preserveAspectRatio="none" role="img"
             aria-label="Temperature trend for the next ${points.length} hours, ${fmtTemp(lo)} to ${fmtTemp(hi)}">
          <path class="spark-fill" d="${area}"/>
          <path class="spark-line" d="${line}" vector-effect="non-scaling-stroke"/>
        </svg>
        <div class="spark-axis">
          ${marks.map((i, n) => `<span>${n === 0 ? "Now" : esc(stamp(i))}</span>`).join("")}
        </div>
      </div>`;
  }

  /* ---------- Rendering: expandable detail ---------- */

  function daylight(station) {
    const today = station.today;
    if (!today?.sunrise || !today?.sunset) return "";

    const rise = minutesOf(today.sunrise);
    const set = minutesOf(today.sunset);
    const now = minutesOf(station.current.time);
    if (rise == null || set == null) return "";

    const progress = now == null ? 0 : Math.max(0, Math.min(100, ((now - rise) / (set - rise)) * 100));
    const daylightHours = ((set - rise) / 60).toFixed(1);

    return `
      <div class="daylight">
        <p class="extra-title">Daylight · ${daylightHours} hours</p>
        <div class="daylight-track">
          <div class="daylight-fill" style="width:${progress.toFixed(1)}%"></div>
          <div class="daylight-marker" style="left:${progress.toFixed(1)}%"></div>
        </div>
        <div class="daylight-labels">
          <span>${icon("sun")} ${esc(clockOf(today.sunrise))}</span>
          <span>${esc(clockOf(today.sunset))} ${icon("moon")}</span>
        </div>
      </div>`;
  }

  function forecast(station) {
    const days = station.daily || [];
    if (!days.length) return "";

    const lows = days.map((d) => d.tmin).filter((n) => typeof n === "number");
    const highs = days.map((d) => d.tmax).filter((n) => typeof n === "number");
    const lo = Math.min(...lows), hi = Math.max(...highs);
    const span = hi - lo || 1;

    const rows = days.map((day, i) => {
      const left = ((day.tmin - lo) / span) * 100;
      const width = Math.max(4, ((day.tmax - day.tmin) / span) * 100);
      const wx = describe(day.code, true);
      return `
        <div class="day${i === 0 ? " is-today" : ""}">
          <span class="day-name">${esc(dayLabel(day.date, i))}</span>
          ${icon(wx.icon)}
          <div class="day-track" title="${esc(wx.label)}">
            <div class="day-bar" style="left:${left.toFixed(1)}%;width:${width.toFixed(1)}%;
                 --cool:${tempColor(day.tmin)};--warm:${tempColor(day.tmax)}"></div>
          </div>
          <span class="day-range">${fmtTemp(day.tmax)} <span>${fmtTemp(day.tmin)}</span></span>
        </div>`;
    }).join("");

    return `<p class="extra-title">7-day outlook</p><div class="days">${rows}</div>`;
  }

  function facts(station) {
    const now = station.current;
    const today = station.today || {};
    const rows = [
      ["Pressure", now.pressure == null ? "–" : `${Math.round(now.pressure)} hPa`],
      ["Cloud cover", now.cloud == null ? "–" : `${now.cloud}%`],
      ["Rain today", today.precipSum == null ? "–" : `${today.precipSum} mm`],
      ["Peak wind today", `${fmtSpeed(today.windMax)} ${speedUnit()}`],
      ["Elevation", station.elevation == null ? "–" : `${Math.round(station.elevation)} m`],
      ["Coordinates", `${station.lat.toFixed(2)}, ${station.lon.toFixed(2)}`],
    ];
    return `<dl class="facts">${rows.map(([k, v]) =>
      `<div class="fact"><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>`;
  }

  /* ---------- Rendering: station card ---------- */

  function card(station) {
    const now = station.current;
    const today = station.today || {};
    const wx = describe(now.code, now.isDay);
    const open = state.expanded.has(station.id);
    const panelId = `detail-${station.id}`;

    const gust = now.gust && now.wind && now.gust > now.wind * 1.25
      ? `<small> g${fmtSpeed(now.gust)}</small>` : "";

    return `
      <article class="card" style="--therm:${tempColor(now.temp)}" data-id="${esc(station.id)}">
        <div class="card-top">
          <div>
            <h3 class="card-city">${esc(station.name)}</h3>
            <p class="card-place">${esc(station.province)} · <b>${esc(station.tag)}</b></p>
          </div>
          <svg class="wx-icon" role="img" aria-label="${esc(wx.label)}"><use href="#i-${wx.icon}"/></svg>
        </div>

        <div class="card-now">
          <p class="temp">${fmtTemp(now.temp, false)}<span class="deg">°</span></p>
          <div class="now-meta">
            <p class="now-cond">${esc(wx.label)}</p>
            <p class="now-feels">Feels ${fmtTemp(now.feels)} · High ${fmtTemp(today.tmax)} / Low ${fmtTemp(today.tmin)}</p>
          </div>
        </div>

        <div class="metrics">
          <div class="metric">
            <span class="metric-label">${icon("drop")} Humidity</span>
            <span class="metric-value">${now.humidity == null ? "–" : `${now.humidity}%`}</span>
          </div>
          <div class="metric">
            <span class="metric-label">${icon("wind")} Wind</span>
            <span class="metric-value" title="From the ${esc(compass(now.windDir))}">
              <svg class="wind-arrow" style="--dir:${(now.windDir || 0)}deg" aria-hidden="true"
                   viewBox="0 0 24 24"><path d="M12 21V4M12 4l-5 5M12 4l5 5"/></svg>${fmtSpeed(now.wind)}${gust}
            </span>
          </div>
          <div class="metric">
            <span class="metric-label">${icon("cloudcover")} Rain</span>
            <span class="metric-value">${today.precipProb == null ? "–" : `${today.precipProb}%`}</span>
          </div>
          <div class="metric">
            <span class="metric-label">${icon("uv")} UV</span>
            <span class="metric-value">${today.uvMax == null ? "–" : Math.round(today.uvMax)}<small> ${esc(uvBand(today.uvMax))}</small></span>
          </div>
        </div>

        ${sparkline(station.hourly || [])}

        <button type="button" class="more" aria-expanded="${open}" aria-controls="${panelId}">
          <span>${open ? "Hide" : "Forecast &amp; detail"}</span>${icon("chevron")}
        </button>
        <div class="extra" id="${panelId}"${open ? "" : " hidden"}>
          ${open ? daylight(station) + forecast(station) + facts(station) : ""}
        </div>
      </article>`;
  }

  /* ---------- Rendering: comparison bars ---------- */

  function renderCompare(stations) {
    const temps = stations.map((s) => s.current.temp).filter((t) => typeof t === "number");
    if (!temps.length) { el.compare.innerHTML = ""; return; }

    const lo = Math.floor(Math.min(...temps)) - 1;
    const hi = Math.ceil(Math.max(...temps)) + 1;
    const span = hi - lo || 1;

    el.compare.innerHTML = [...stations]
      .sort((a, b) => b.current.temp - a.current.temp)
      .map((s) => {
        const pct = ((s.current.temp - lo) / span) * 100;
        return `
          <div class="bar-row">
            <span class="bar-city">${esc(s.name)}</span>
            <div class="bar-track"><div class="bar-fill"
                 style="width:${pct.toFixed(1)}%;background:${tempColor(s.current.temp)}"></div></div>
            <span class="bar-value">${fmtTemp(s.current.temp)}</span>
          </div>`;
      }).join("");
  }

  /* ---------- Rendering: status ---------- */

  function renderStatus() {
    if (!state.data) return;
    const age = Date.now() - Date.parse(state.data.generated);
    const live = state.source === "live" && age < STALE_MS;

    el.status.dataset.state = live ? "live" : state.source === "error" ? "error" : "stale";
    el.statusText.textContent = live
      ? `Live · ${relativeTime(state.data.generated)}`
      : `Snapshot · ${relativeTime(state.data.generated)}`;

    el.footerStamp.textContent =
      `Readings dated ${clockOf(state.data.stations[0]?.current?.time)} SAST · ` +
      `page data ${relativeTime(state.data.generated)} (${state.source})`;
  }

  /* ---------- Filter, sort, paint ---------- */

  function visibleStations() {
    const q = state.query.trim().toLowerCase();
    const list = state.data.stations.filter((s) =>
      !q || `${s.name} ${s.province} ${s.tag}`.toLowerCase().includes(q));

    const by = {
      "temp-desc": (a, b) => b.current.temp - a.current.temp,
      "temp-asc": (a, b) => a.current.temp - b.current.temp,
      "wind-desc": (a, b) => b.current.wind - a.current.wind,
      "rain-desc": (a, b) => (b.today?.precipProb ?? 0) - (a.today?.precipProb ?? 0),
      "name-asc": (a, b) => a.name.localeCompare(b.name),
      "province-asc": (a, b) => a.province.localeCompare(b.province) || a.name.localeCompare(b.name),
    };
    return list.sort(by[state.sort] || by["temp-desc"]);
  }

  function paint() {
    if (!state.data) return;
    const stations = visibleStations();

    el.grid.innerHTML = stations.length
      ? stations.map(card).join("")
      : `<p class="empty">No station matches “${esc(state.query)}”.</p>`;

    el.resultCount.textContent = state.query
      ? `${stations.length} of ${state.data.stations.length} stations`
      : `${state.data.stations.length} stations · 9 provinces`;

    renderSummary(state.data.stations);
    renderCompare(state.data.stations);
    renderStatus();
  }

  function apply(data, source) {
    if (!data?.stations?.length) return;
    state.data = data;
    state.source = source;
    paint();
  }

  /* ---------- Live refresh ---------- */

  let stationSeed = [];

  async function refresh({ manual = false } = {}) {
    if (!stationSeed.length) return;
    el.refreshBtn.classList.add("is-spinning");
    el.refreshBtn.disabled = true;

    try {
      const blocks = await fetchJSON(buildLiveURL(stationSeed));
      const data = normalise(blocks, stationSeed);
      apply(data, "live");
      writeCache(data);
      hideAlert();
    } catch (error) {
      console.warn("Live refresh failed:", error);
      if (state.data) {
        showAlert("Could not reach Open-Meteo just now — showing the last good reading, " +
                  `from ${relativeTime(state.data.generated)}.`);
        renderStatus();
      } else {
        state.source = "error";
        showAlert("Could not load weather data. Check your connection and try refreshing.");
        el.status.dataset.state = "error";
        el.statusText.textContent = "Offline";
      }
    } finally {
      el.refreshBtn.classList.remove("is-spinning");
      el.refreshBtn.disabled = false;
      if (manual) el.refreshBtn.focus();
    }
  }

  const showAlert = (message) => { el.alertText.textContent = message; el.alert.hidden = false; };
  const hideAlert = () => { el.alert.hidden = true; };

  /* ---------- Theme & units ---------- */

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    save(KEY.theme, theme);
    const next = theme === "dark" ? "light" : "dark";
    el.themeBtn.setAttribute("aria-label", `Switch to ${next} theme`);
    el.themeBtn.innerHTML = icon(theme === "dark" ? "sun" : "moon");
  }

  function applyUnits(units) {
    state.units = units;
    save(KEY.units, units);
    el.unitLabel.textContent = isImperial() ? "°F" : "°C";
    el.unitBtn.setAttribute("aria-label",
      `Switch to ${isImperial() ? "Celsius and kilometres" : "Fahrenheit and miles"} per hour`);
    paint();
  }

  /* ---------- Boot ---------- */

  const el = {};
  ["summary", "grid", "compare", "search", "sort", "resultCount", "status", "statusText",
   "alert", "alertText", "themeBtn", "unitBtn", "unitLabel", "refreshBtn", "footerStamp"]
    .forEach((id) => { el[id] = document.getElementById(id); });

  function wireEvents() {
    let debounce;
    el.search.addEventListener("input", (event) => {
      clearTimeout(debounce);
      const value = event.target.value;
      debounce = setTimeout(() => { state.query = value; paint(); }, 130);
    });

    el.sort.value = state.sort;
    el.sort.addEventListener("change", (event) => {
      state.sort = event.target.value;
      save(KEY.sort, state.sort);
      paint();
    });

    el.unitBtn.addEventListener("click", () =>
      applyUnits(isImperial() ? "metric" : "imperial"));

    el.themeBtn.addEventListener("click", () =>
      applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));

    el.refreshBtn.addEventListener("click", () => refresh({ manual: true }));

    /* Expanding a card renders its detail lazily and remembers the choice. */
    el.grid.addEventListener("click", (event) => {
      const button = event.target.closest(".more");
      if (!button) return;
      const id = button.closest(".card")?.dataset.id;
      if (!id) return;
      if (state.expanded.has(id)) state.expanded.delete(id);
      else state.expanded.add(id);
      paint();
      document.querySelector(`.card[data-id="${id}"] .more`)?.focus();
    });

    /* Pause the polling loop while the tab is hidden, and catch up on return. */
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        clearInterval(state.timer);
        state.timer = null;
      } else {
        if (Date.now() - Date.parse(state.data?.generated || 0) > CACHE_TTL_MS) refresh();
        startPolling();
      }
    });

    setInterval(renderStatus, 60000);   // Keep the "x min ago" label honest.
  }

  function startPolling() {
    clearInterval(state.timer);
    state.timer = setInterval(() => refresh(), REFRESH_MS);
  }

  async function boot() {
    applyTheme(load(KEY.theme) ||
      (window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark"));
    applyUnits(state.units);   // Also syncs the button's label and aria-label.
    wireEvents();

    const [cities, snapshot] = await Promise.allSettled([
      fetchJSON(CITIES_URL),
      fetchJSON(SNAPSHOT_URL),
    ]);

    const snapshotData = snapshot.status === "fulfilled" ? snapshot.value : null;

    /* The station list drives the live API call; either source can supply it. */
    stationSeed = cities.status === "fulfilled"
      ? cities.value.cities
      : (snapshotData?.stations || []).map(({ id, name, province, tag, lat, lon }) =>
          ({ id, name, province, tag, lat, lon }));

    const cached = readCache();
    if (cached) apply(cached, "cache");
    else if (snapshotData) apply(snapshotData, "snapshot");

    if (!stationSeed.length) {
      showAlert("Could not load the station list. Try reloading the page.");
      return;
    }

    await refresh();
    startPolling();
  }

  boot();
})();
