const API = "http://127.0.0.1:8000";

function getToken() {
  return localStorage.getItem("aurum_token");
}

function logout() {
  localStorage.removeItem("aurum_token");
  window.location.replace("login.html");
}

function authHeaders(extra = {}) {
  return { "Authorization": `Bearer ${getToken()}`, ...extra };
}

async function authFetch(url, options = {}) {
  if (!getToken()) {
    window.location.replace("login.html");
    return;
  }
  options.headers = { ...authHeaders(options.headers || {}) };
  const res = await fetch(url, options);
  if (res.status === 401) {
    logout();
    return;
  }
  return res;
}

if (!getToken()) {
  window.location.replace("login.html");
}

document.getElementById("logout-btn").addEventListener("click", logout);

function fmt(n) {
  return new Intl.NumberFormat("id-ID").format(n);
}

function setClass(el, value) {
  el.classList.remove("positive", "negative");
  if (value > 0) el.classList.add("positive");
  else if (value < 0) el.classList.add("negative");
}

async function loadPrediction() {
  const errEl = document.getElementById("predict-error");
  try {
    const res = await authFetch(`${API}/api/predict`);
    if (!res || !res.ok) throw new Error(`HTTP ${res?.status}`);
    const d = await res.json();

    document.getElementById("pred-price").textContent   = `Rp${fmt(d.predicted_price_idr)}`;
    document.getElementById("pred-date").textContent    = `Prediksi per ${d.date}`;
    document.getElementById("actual-price").textContent = `Rp${fmt(d.actual_ubs_price_idr)}`;

    document.getElementById("ubs-date-label").textContent = d.ubs_price_date;
    document.getElementById("xau-date-label").textContent = d.xauusd_date;

    const staleEl = document.getElementById("stale-warning");
    if (d.is_stale) {
      staleEl.classList.remove("hidden");
    } else {
      staleEl.classList.add("hidden");
    }

    const errIdrEl = document.getElementById("error-idr");
    const errPctEl = document.getElementById("error-pct");
    const sign = d.prediction_error_idr >= 0 ? "+" : "";
    errIdrEl.textContent = `${sign}Rp${fmt(Math.abs(d.prediction_error_idr))}`;
    errPctEl.textContent = `${sign}${d.prediction_error_pct}%`;
    setClass(errIdrEl, d.prediction_error_idr);
    setClass(errPctEl, d.prediction_error_pct);

    document.getElementById("xauusd").textContent  = `$${d.xauusd_live.toLocaleString("en-US", { minimumFractionDigits: 2 })}`;
    document.getElementById("usdidr").textContent  = `Rp${fmt(Math.round(d.usdidr_live))}`;
    document.getElementById("implied").textContent = `Rp${fmt(d.implied_spot_idr)}`;

    const premEl   = document.getElementById("premium");
    const premSign = d.premium_pct >= 0 ? "+" : "";
    premEl.textContent = `${premSign}${d.premium_pct}%`;
    setClass(premEl, d.premium_pct);

    errEl.classList.add("hidden");
  } catch (e) {
    errEl.textContent = `Gagal memuat prediksi: ${e.message}`;
    errEl.classList.remove("hidden");
  }
}

let historyChart = null;

async function loadHistory() {
  const errEl = document.getElementById("chart-error");
  try {
    const res = await authFetch(`${API}/api/history?days=30`);
    if (!res || !res.ok) throw new Error(`HTTP ${res?.status}`);
    const { data } = await res.json();

    const labels    = data.map(r => r.date);
    const ubsPrices = data.map(r => r.ubs_sell_idr);
    const implied   = data.map(r => r.implied_spot_idr);

    const ctx = document.getElementById("history-chart").getContext("2d");
    if (historyChart) historyChart.destroy();

    historyChart = new Chart(ctx, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Harga UBS (Rp/gram)",
            data: ubsPrices,
            borderColor: "#c9a84c",
            backgroundColor: "rgba(201,168,76,0.10)",
            borderWidth: 2,
            pointRadius: 2,
            tension: 0.3,
            fill: true,
          },
          {
            label: "Implied Spot (Rp/gram)",
            data: implied,
            borderColor: "#5c8de0",
            backgroundColor: "transparent",
            borderWidth: 1.5,
            borderDash: [4, 3],
            pointRadius: 0,
            tension: 0.3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            labels: { color: "#888899", font: { size: 12 } },
          },
          tooltip: {
            callbacks: {
              label(ctx) {
                return `${ctx.dataset.label}: Rp${new Intl.NumberFormat("id-ID").format(ctx.parsed.y)}`;
              },
            },
          },
        },
        scales: {
          x: {
            ticks: { color: "#888899", maxTicksLimit: 10 },
            grid:  { color: "#2e2e3e" },
          },
          y: {
            ticks: {
              color: "#888899",
              callback: v => `Rp${new Intl.NumberFormat("id-ID").format(v)}`,
            },
            grid: { color: "#2e2e3e" },
          },
        },
      },
    });

    errEl.classList.add("hidden");
  } catch (e) {
    errEl.textContent = `Gagal memuat riwayat harga: ${e.message}`;
    errEl.classList.remove("hidden");
  }
}

document.getElementById("budget-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const budgetVal = parseFloat(document.getElementById("budget-input").value);
  const weightVal = parseFloat(document.getElementById("weight-input").value);
  const btn       = document.getElementById("budget-btn");
  const resultEl  = document.getElementById("budget-result");
  const errEl     = document.getElementById("budget-error");

  if (!budgetVal || budgetVal <= 0) return;

  btn.disabled    = true;
  btn.textContent = "Menghitung...";
  resultEl.classList.add("hidden");
  errEl.classList.add("hidden");

  try {
    const res = await authFetch(`${API}/api/budget`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ budget_idr: budgetVal, weight_gram: weightVal }),
    });
    if (!res || !res.ok) {
      const err = await res?.json().catch(() => ({}));
      throw new Error(err?.detail || `HTTP ${res?.status}`);
    }
    const d = await res.json();

    document.getElementById("b-current-price").textContent =
      `Rp${fmt(d.current_price_idr)} / ${weightVal}g`;
    document.getElementById("b-current-units").textContent =
      `${d.current_units_affordable} unit`;
    document.getElementById("b-recommendation").textContent = d.recommendation;

    const tbody = document.getElementById("forecast-body");
    tbody.innerHTML = "";
    for (const row of d.forecast) {
      const tr = document.createElement("tr");
      if (row.is_best_day) tr.classList.add("best-day");
      tr.innerHTML = `
        <td>${row.date}</td>
        <td>Rp${fmt(row.predicted_price_idr)}</td>
        <td>${row.units_affordable} unit</td>
        <td>${row.is_best_day ? '<span class="badge-best">Terbaik</span>' : ""}</td>
      `;
      tbody.appendChild(tr);
    }

    resultEl.classList.remove("hidden");
  } catch (e) {
    errEl.textContent = `Gagal menghitung forecast: ${e.message}`;
    errEl.classList.remove("hidden");
  } finally {
    btn.disabled    = false;
    btn.textContent = "Hitung";
  }
});

loadPrediction();
loadHistory();
