const API_BASE = "https://api.coingecko.com/api/v3";

const state = {
coins: [],
favorites: JSON.parse(localStorage.getItem("crypto_favorites") || "[]"),
selectedCoin: "bitcoin",
currency: "usd",
chartInterval: "24h",
loading: false
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

function formatPrice(value) {
if (value === null || value === undefined) return "--";

if (value >= 1000) {
return "$" + value.toLocaleString("en-US", {
maximumFractionDigits: 0
});
}

if (value >= 1) {
return "$" + value.toLocaleString("en-US", {
minimumFractionDigits: 2,
maximumFractionDigits: 2
});
}

return "$" + value.toLocaleString("en-US", {
minimumFractionDigits: 4,
maximumFractionDigits: 8
});
}

function formatPercent(value) {
if (value === null || value === undefined) return "--";

const number = Number(value);
return "${number >= 0 ? "+" : ""}${number.toFixed(2)}%";
}

function formatLargeNumber(value) {
if (!value) return "--";

if (value >= 1e12) {
return "$" + (value / 1e12).toFixed(2) + "T";
}

if (value >= 1e9) {
return "$" + (value / 1e9).toFixed(2) + "B";
}

if (value >= 1e6) {
return "$" + (value / 1e6).toFixed(2) + "M";
}

return "$" + value.toLocaleString();
}

function saveFavorites() {
localStorage.setItem(
"crypto_favorites",
JSON.stringify(state.favorites)
);
}

function isFavorite(id) {
return state.favorites.includes(id);
}

function toggleFavorite(id) {
if (isFavorite(id)) {
state.favorites = state.favorites.filter(
coinId => coinId !== id
);
} else {
state.favorites.push(id);
}

saveFavorites();
renderCoins(state.coins);
}

async function fetchJSON(url) {
const response = await fetch(url);

if (!response.ok) {
throw new Error("API error: ${response.status}");
}

return response.json();
}

/* =========================================================
MARKET DATA
========================================================= */

async function loadMarketData() {
try {
state.loading = true;

const url =
  `${API_BASE}/coins/markets` +
  `?vs_currency=${state.currency}` +
  `&order=market_cap_desc` +
  `&per_page=20` +
  `&page=1` +
  `&sparkline=true` +
  `&price_change_percentage=1h,24h,7d`;

const data = await fetchJSON(url);

state.coins = data;

renderCoins(data);
updateTicker(data);
updateMarketPulse(data);
updateTopPrices(data);

} catch (error) {
console.error("Market data error:", error);

showApiError();

} finally {
state.loading = false;
}
}

/* =========================================================
COIN CARDS
========================================================= */

function renderCoins(coins) {
const container =
$("#coinGrid") ||
$(".coin-grid") ||
document.querySelector(".coin-grid");

if (!container) return;

const selected = coins.slice(0, 8);

container.innerHTML = selected.map((coin) => {
const change =
coin.price_change_percentage_24h ?? 0;

const positive = change >= 0;

return `
  <article class="coin-card"
    data-coin="${coin.id}">

    <div class="coin-card-top">

      <div class="coin-identity">

        <img
          class="coin-logo"
          src="${coin.image}"
          alt="${coin.name}"
          loading="lazy"
          style="object-fit:cover;"
        >

        <div>
          <strong>${escapeHTML(coin.name)}</strong>
          <span>${coin.symbol.toUpperCase()}</span>
        </div>

      </div>

      <button
        class="star-button ${isFavorite(coin.id) ? "active" : ""}"
        data-favorite="${coin.id}"
        aria-label="Add ${escapeHTML(coin.name)} to favorites">
        ${isFavorite(coin.id) ? "★" : "☆"}
      </button>

    </div>

    <div class="coin-price">

      <strong>
        ${formatPrice(coin.current_price)}
      </strong>

      <span class="${positive ? "positive-text" : "negative-text"}">
        ${formatPercent(change)}
      </span>

    </div>

    <div class="coin-card-bottom">

      <span>Market Cap</span>

      <strong>
        ${formatLargeNumber(coin.market_cap)}
      </strong>

    </div>

    <div class="mini-chart ${positive ? "positive" : ""}">
    </div>

  </article>
`;

}).join("");

$$("[data-favorite]").forEach(button => {
button.addEventListener("click", (event) => {
event.stopPropagation();

  toggleFavorite(
    button.dataset.favorite
  );
});

});

$$(".coin-card").forEach(card => {
card.addEventListener("click", () => {
selectCoin(card.dataset.coin);
});
});
}

/* =========================================================
TICKER
========================================================= */

function updateTicker(coins) {
const ticker =
$(".ticker-items") ||
$("#tickerItems");

if (!ticker) return;

ticker.innerHTML = coins.slice(0, 10).map(coin => {

const change =
  coin.price_change_percentage_24h ?? 0;

return `
  <div class="ticker-item">

    <span>
      ${coin.symbol.toUpperCase()}
    </span>

    <strong class="${change >= 0 ? "positive-text" : "negative-text"}">
      ${formatPercent(change)}
    </strong>

  </div>
`;

}).join("");
}

/* =========================================================
MARKET PULSE
========================================================= */

function updateMarketPulse(coins) {
if (!coins.length) return;

const changes = coins
.map(c => c.price_change_percentage_24h)
.filter(v => typeof v === "number");

if (!changes.length) return;

const average =
changes.reduce((a, b) => a + b, 0) /
changes.length;

const score =
Math.max(
0,
Math.min(
100,
Math.round(50 + average * 5)
)
);

const scoreElement =
$(".score-ring strong") ||
$("#marketScore");

if (scoreElement) {
scoreElement.textContent = score;
}

const status =
$(".pulse-info > strong");

if (status) {

if (score >= 70) {
  status.textContent = "Bullish";
  status.className = "positive-text";
} else if (score <= 35) {
  status.textContent = "Bearish";
  status.className = "negative-text";
} else {
  status.textContent = "Neutral";
  status.className = "warning-text";
}

}
}

/* =========================================================
TOP PRICES
========================================================= */

function updateTopPrices(coins) {
const btc = coins.find(c => c.id === "bitcoin");
const eth = coins.find(c => c.id === "ethereum");

if (btc) {
$$("[data-price='bitcoin']").forEach(el => {
el.textContent =
formatPrice(btc.current_price);
});
}

if (eth) {
$$("[data-price='ethereum']").forEach(el => {
el.textContent =
formatPrice(eth.current_price);
});
}
}

/* =========================================================
SELECT COIN
========================================================= */

function selectCoin(id) {
state.selectedCoin = id;

const coin =
state.coins.find(c => c.id === id);

if (!coin) return;

updateSelectedCoinUI(coin);
updateTradingView(coin.symbol);

loadCoinAnalysis(id);
}

function updateSelectedCoinUI(coin) {

const name =
$(".selected-asset strong");

const symbol =
$(".selected-asset span");

const price =
$(".chart-price strong");

if (name) {
name.textContent = coin.name;
}

if (symbol) {
symbol.textContent =
coin.symbol.toUpperCase();
}

if (price) {
price.textContent =
formatPrice(coin.current_price);
}

const change =
$(".chart-price span");

if (change) {

const value =
  coin.price_change_percentage_24h ?? 0;

change.textContent =
  formatPercent(value);

change.className =
  value >= 0
    ? "positive-text"
    : "negative-text";

}
}

/* =========================================================
TRADINGVIEW
========================================================= */

function updateTradingView(symbol) {

const container =
$("#tradingview-widget") ||
$(".tradingview-widget-container");

if (!container) return;

const pair =
symbol.toUpperCase() + "USDT";

container.innerHTML = "<div class="tradingview-widget-container__widget"></div>";

const script =
document.createElement("script");

script.src =
"https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

script.async = true;

script.innerHTML = JSON.stringify({
autosize: true,
symbol: "BINANCE:${pair}",
interval: "60",
timezone: "Etc/UTC",
theme: "dark",
style: "1",
locale: "en",
enable_publishing: false,
hide_top_toolbar: false,
hide_legend: false,
allow_symbol_change: true,
save_image: false,
studies: [
"RSI@tv-basicstudies",
"MACD@tv-basicstudies"
]
});

container.appendChild(script);
}

/* =========================================================
COIN ANALYSIS
========================================================= */

async function loadCoinAnalysis(id) {

try {

const data = await fetchJSON(
  `${API_BASE}/coins/${id}?localization=false&tickers=false&market_data=true&community_data=true&developer_data=false`
);

updateTechnicalAnalysis(data);
updatePrediction(data);

} catch (error) {

console.error(
  "Analysis error:",
  error
);

}
}

function updateTechnicalAnalysis(data) {

const market =
data.market_data;

if (!market) return;

const price =
market.current_price?.usd ?? 0;

const high24 =
market.high_24h?.usd ?? 0;

const low24 =
market.low_24h?.usd ?? 0;

const change =
market.price_change_percentage_24h ?? 0;

const technicalScore =
Math.max(
0,
Math.min(
100,
Math.round(
50 +
change * 4 +
((price - low24) /
Math.max(high24 - low24, 1)) * 20
)
)
);

const score =
$(".score-small");

if (score) {
score.textContent =
technicalScore;
}

const rows =
$$(".indicator-row");

if (rows.length >= 3) {

rows[0].querySelector("strong")
  ?.replaceChildren(
    document.createTextNode(
      formatPrice(price)
    )
  );

rows[1].querySelector("strong")
  ?.replaceChildren(
    document.createTextNode(
      formatPercent(change)
    )
  );

rows[2].querySelector("strong")
  ?.replaceChildren(
    document.createTextNode(
      formatLargeNumber(
        market.total_volume?.usd
      )
    )
  );

}
}

/* =========================================================
PREDICTION ENGINE
========================================================= */

function calculatePrediction(data) {

const market =
data.market_data;

if (!market) {
return {
short: "--",
medium: "--",
long: "--"
};
}

const price =
market.current_price?.usd || 0;

const change24 =
market.price_change_percentage_24h || 0;

const change7 =
market.price_change_percentage_7d || 0;

const momentum =
change24 * 0.4 +
change7 * 0.6;

const shortMultiplier =
1 + momentum / 100 * 0.35;

const mediumMultiplier =
1 + momentum / 100 * 0.9;

const longMultiplier =
1 + momentum / 100 * 1.8;

return {
short: price * shortMultiplier,
medium: price * mediumMultiplier,
long: price * longMultiplier
};
}

function updatePrediction(data) {

const prediction =
calculatePrediction(data);

const values =
$$(".prediction-target");

if (values.length >= 3) {

values[0].textContent =
  formatPrice(prediction.short);

values[1].textContent =
  formatPrice(prediction.medium);

values[2].textContent =
  formatPrice(prediction.long);

}
}

/* =========================================================
SEARCH
========================================================= */

function setupSearch() {

const input =
$(".topbar-search input");

if (!input) return;

let timer;

input.addEventListener(
"input",
() => {

  clearTimeout(timer);

  timer = setTimeout(
    () => performSearch(input.value),
    350
  );
}

);
}

async function performSearch(query) {

query = query.trim();

if (!query) return;

const overlay =
$("#searchOverlay") ||
$(".search-overlay");

if (overlay) {
overlay.hidden = false;
}

const results =
$("#searchResults");

if (results) {
results.innerHTML =
"Searching...";
}

try {

const data =
  await fetchJSON(
    `${API_BASE}/search?query=${encodeURIComponent(query)}`
  );

const coins =
  data.coins?.slice(0, 8) || [];

if (!results) return;

if (!coins.length) {

  results.innerHTML =
    "No coins found.";

  return;
}

results.innerHTML =
  coins.map(coin => `
    <button
      class="search-result"
      data-search-id="${coin.id}"
      style="
        width:100%;
        padding:10px;
        display:flex;
        align-items:center;
        gap:10px;
        color:#fff;
        background:transparent;
        border:0;
        border-bottom:1px solid rgba(255,255,255,.06);
        cursor:pointer;
        text-align:left;
      "
    >

      <img
        src="${coin.thumb || ""}"
        width="28"
        height="28"
        style="border-radius:50%"
        loading="lazy"
      >

      <span>
        <strong>
          ${escapeHTML(coin.name)}
        </strong>

        <small style="display:block;color:#8c98ad">
          ${coin.symbol || ""}
        </small>
      </span>

    </button>
  `).join("");

$$("[data-search-id]").forEach(button => {

  button.addEventListener(
    "click",
    () => {

      state.selectedCoin =
        button.dataset.searchId;

      closeSearch();

      loadMarketData();

      window.scrollTo({
        top: document.body.scrollHeight * 0.35,
        behavior: "smooth"
      });
    }
  );

});

} catch (error) {

console.error(
  "Search error:",
  error
);

if (results) {
  results.innerHTML =
    "Search temporarily unavailable.";
}

}
}

function closeSearch() {

const overlay =
$("#searchOverlay") ||
$(".search-overlay");

if (overlay) {
overlay.hidden = true;
}
}

/* =========================================================
MOBILE SIDEBAR
========================================================= */

function setupMobileMenu() {

const button =
$(".mobile-menu");

const sidebar =
$(".sidebar");

if (!button || !sidebar) return;

button.addEventListener(
"click",
() => {
sidebar.classList.toggle("open");
}
);

$$(".nav-item").forEach(item => {

item.addEventListener(
  "click",
  () => {
    sidebar.classList.remove("open");
  }
);

});
}

/* =========================================================
NAVIGATION
========================================================= */

function setupNavigation() {

$$(".nav-item").forEach(item => {

item.addEventListener(
  "click",
  (event) => {

    const href =
      item.getAttribute("href");

    if (!href || !href.startsWith("#")) {
      return;
    }

    event.preventDefault();

    $$(".nav-item").forEach(
      nav => nav.classList.remove("active")
    );

    item.classList.add("active");

    const section =
      document.querySelector(href);

    if (section) {

      section.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }
  }
);

});
}

/* =========================================================
TIME BUTTONS
========================================================= */

function setupTimeButtons() {

$$(".time-button").forEach(button => {

button.addEventListener(
  "click",
  () => {

    $$(".time-button").forEach(
      btn => btn.classList.remove("active")
    );

    button.classList.add("active");

    state.chartInterval =
      button.dataset.interval ||
      button.textContent.trim();

  }
);

});
}

/* =========================================================
MODAL
========================================================= */

function setupModal() {

const modal =
$("#analysisModal") ||
$(".modal-overlay");

if (!modal) return;

const closeButtons =
modal.querySelectorAll(
".modal-close"
);

closeButtons.forEach(button => {

button.addEventListener(
  "click",
  () => {
    modal.hidden = true;
  }
);

});

modal.addEventListener(
"click",
event => {

  if (event.target === modal) {
    modal.hidden = true;
  }

}

);
}

/* =========================================================
SCANNER
========================================================= */

function setupScanner() {

const button =
$("#runScanner") ||
document.querySelector(
"[data-action='scan']"
);

if (!button) return;

button.addEventListener(
"click",
runScanner
);
}

async function runScanner() {

const result =
$(".scanner-results");

if (!result) return;

result.innerHTML = "<div class="scanner-empty"> <span>◌</span> <strong>Scanning market...</strong> <p>Analyzing momentum, volume and volatility.</p> </div>";

await loadMarketData();

const candidates =
state.coins
.map(coin => {

    const change =
      coin.price_change_percentage_24h || 0;

    const volume =
      coin.total_volume || 0;

    const score =
      Math.round(
        Math.max(
          0,
          Math.min(
            100,
            50 +
            change * 5 +
            Math.log10(
              Math.max(volume, 1)
            )
          )
        )
      );

    return {
      ...coin,
      scannerScore: score
    };
  })
  .sort(
    (a, b) =>
      b.scannerScore -
      a.scannerScore
  )
  .slice(0, 5);

result.innerHTML =
candidates.map(coin => `
<div class="mini-opportunity">

    <div class="mini-opportunity-coin">

      <img
        src="${coin.image}"
        width="34"
        height="34"
        style="border-radius:50%"
      >

      <div>
        <strong>
          ${escapeHTML(coin.name)}
        </strong>

        <small style="display:block;color:#8c98ad">
          ${coin.symbol.toUpperCase()}
        </small>
      </div>

    </div>

    <div class="mini-score">
      ${coin.scannerScore}
    </div>

  </div>
`).join("");

}

/* =========================================================
WATCHLIST
========================================================= */

function renderWatchlist() {

const panel =
$(".watchlist-panel");

if (!panel) return;

const coins =
state.coins.filter(
coin => isFavorite(coin.id)
);

if (!coins.length) {

panel.innerHTML = `
  <div class="watchlist-empty">

    <div class="empty-icon">☆</div>

    <h3>Your watchlist is empty</h3>

    <p>
      Add coins to your favorites to track them here.
    </p>

  </div>
`;

return;

}

panel.innerHTML =
coins.map(coin => `
<div class="mini-opportunity">

    <div class="mini-opportunity-coin">

      <img
        src="${coin.image}"
        width="30"
        height="30"
        style="border-radius:50%"
      >

      <strong>
        ${escapeHTML(coin.name)}
      </strong>

    </div>

    <strong>
      ${formatPrice(coin.current_price)}
    </strong>

  </div>
`).join("");

}

/* =========================================================
API ERROR
========================================================= */

function showApiError() {

const ticker =
$(".ticker-items");

if (ticker) {

ticker.innerHTML = `
  <div style="
    padding:0 15px;
    color:#ff5f72;
    font-size:9px;
  ">
    Market data temporarily unavailable.
  </div>
`;

}
}

/* =========================================================
SECURITY HELPERS
========================================================= */

function escapeHTML(value) {

return String(value ?? "")
.replaceAll("&", "&")
.replaceAll("<", "<")
.replaceAll(">", ">")
.replaceAll('"', """)
.replaceAll("'", "'");
}

/* =========================================================
KEYBOARD SHORTCUTS
========================================================= */

function setupKeyboard() {

document.addEventListener(
"keydown",
event => {

  if (
    event.key === "/" &&
    document.activeElement.tagName !== "INPUT"
  ) {

    event.preventDefault();

    const input =
      $(".topbar-search input");

    input?.focus();
  }

  if (event.key === "Escape") {
    closeSearch();
  }
}

);
}

/* =========================================================
AUTO REFRESH
========================================================= */

function startAutoRefresh() {

setInterval(
() => {

  if (
    document.visibilityState ===
    "visible"
  ) {
    loadMarketData();
  }

},
60000

);
}

/* =========================================================
INIT
========================================================= */

async function init() {

setupSearch();
setupMobileMenu();
setupNavigation();
setupTimeButtons();
setupModal();
setupScanner();
setupKeyboard();

await loadMarketData();

renderWatchlist();

startAutoRefresh();

const firstCoin =
state.coins[0];

if (firstCoin) {
selectCoin(firstCoin.id);
}

console.log(
"%c CryptoVision V5 ",
"background:#6d7cff;color:white;padding:5px 10px;border-radius:5px;font-weight:bold"
);

console.log(
"Market intelligence system initialized."
);
}

document.addEventListener(
"DOMContentLoaded",
init
);
