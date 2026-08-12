const API_URL =
"https://api.coingecko.com/api/v3/coins/markets";

const state = {
coins: [],
selected: null,
favorites: JSON.parse(
localStorage.getItem("cv_favorites") || "[]"
)
};

/* =========================
FETCH WRAPPER WITH RETRY & CACHE
========================= */

function createFetchWrapper() {
const cache = {};
const CACHE_TTL = 60000;

return async function safeFetch(url, options = {}) {
const timeout = options.timeout || 10000;
const maxRetries = options.maxRetries || 2;
const useCache = options.useCache !== false;

const cacheKey =
  "cache_" + url;

if (useCache) {
  const cached =
    sessionStorage.getItem(
      cacheKey
    );

  if (cached) {
    const entry = JSON.parse(
      cached
    );

    if (
      Date.now() - entry.time <
      CACHE_TTL
    ) {
      return new Response(
        JSON.stringify(
          entry.data
        ),
        { status: 200 }
      );
    }
  }
}

let lastError;

for (
  let attempt = 0;
  attempt <= maxRetries;
  attempt++
) {
  try {
    const controller =
      new AbortController();

    const timeoutId =
      setTimeout(
        function () {
          controller.abort();
        },
        timeout
      );

    const response =
      await fetch(url, {
        ...options,
        signal:
          controller.signal
      });

    clearTimeout(timeoutId);

    if (response.ok) {
      const data =
        await response.clone()
          .json();

      if (useCache) {
        sessionStorage.setItem(
          cacheKey,
          JSON.stringify({
            data: data,
            time: Date.now()
          })
        );
      }

      return response;
    }

    if (response.status >= 500) {
      throw new Error(
        "Server error " +
        response.status
      );
    }

    return response;

  } catch (error) {
    lastError = error;

    if (attempt < maxRetries) {
      const delay =
        Math.pow(2, attempt) *
        1000;

      await new Promise(
        function (resolve) {
          setTimeout(
            resolve,
            delay
          );
        }
      );
    }
  }
}

throw lastError ||
  new Error("Fetch failed");
};
}

const safeFetch =
createFetchWrapper();

function $(selector) {
return document.querySelector(selector);
}

function formatPrice(value) {
const n = Number(value);

if (!Number.isFinite(n)) return "--";

if (n >= 1000) {
return "$" + n.toLocaleString("en-US", {
maximumFractionDigits: 0
});
}

if (n >= 1) {
return "$" + n.toLocaleString("en-US", {
minimumFractionDigits: 2,
maximumFractionDigits: 2
});
}

return "$" + n.toLocaleString("en-US", {
minimumFractionDigits: 4,
maximumFractionDigits: 8
});
}

function formatPercent(value) {
const n = Number(value);

if (!Number.isFinite(n)) return "--";

return (
(n >= 0 ? "+" : "") +
n.toFixed(2) +
"%"
);
}

function formatLarge(value) {
const n = Number(value);

if (!Number.isFinite(n)) return "--";

if (n >= 1e12) {
return "$" + (n / 1e12).toFixed(2) + "T";
}

if (n >= 1e9) {
return "$" + (n / 1e9).toFixed(2) + "B";
}

if (n >= 1e6) {
return "$" + (n / 1e6).toFixed(2) + "M";
}

return "$" + n.toLocaleString("en-US");
}

function showLoading(text) {
const grid = $("#coinGrid");

if (!grid) return;

const card =
document.createElement("div");

card.className =
"loading-card";

card.textContent = text;

grid.innerHTML = "";
grid.appendChild(card);
}

async function loadCoins() {
const url =
API_URL +
"?vs_currency=usd" +
"&order=market_cap_desc" +
"&per_page=100" +
"&page=1" +
"&sparkline=false" +
"&price_change_percentage=24h,7d";

const response =
await safeFetch(url);

if (!response.ok) {
throw new Error(
"CoinGecko error " +
response.status
);
}

const data = await response.json();

if (!Array.isArray(data)) {
throw new Error(
"Invalid market data"
);
}

return data;
}

function renderCoins(coins) {
const grid = $("#coinGrid");

if (!grid) return;

grid.innerHTML = "";

if (!coins.length) {
const card =
document.createElement("div");

card.className =
"loading-card";

card.textContent =
"No coins found.";

grid.appendChild(card);

return;

}

coins.forEach(function (coin) {
const change =
Number(
coin.price_change_percentage_24h
) || 0;

const card =
  document.createElement("article");

card.className = "coin-card";

const favorite =
  state.favorites.includes(
    coin.id
  );

card.innerHTML = `
  <div class="coin-card-top">

    <div class="coin-identity">

      <img
        class="coin-logo"
        src="${coin.image}"
        alt="${coin.name}"
        loading="lazy"
      >

      <div>
        <strong>${coin.name}</strong>
        <span>
          ${coin.symbol.toUpperCase()}
        </span>
      </div>

    </div>

    <button
      class="star-button ${
        favorite ? "active" : ""
      }"
      data-favorite="${coin.id}"
      type="button"
    >
      ${favorite ? "★" : "☆"}
    </button>

  </div>

  <div class="coin-price">

    <strong>
      ${formatPrice(
        coin.current_price
      )}
    </strong>

    <span class="${
      change >= 0
        ? "positive-text"
        : "negative-text"
    }">
      ${formatPercent(change)}
    </span>

  </div>

  <div class="coin-card-bottom">

    <span>Market Cap</span>

    <strong>
      ${formatLarge(
        coin.market_cap
      )}
    </strong>

  </div>
`;

grid.appendChild(card);

card.addEventListener(
  "click",
  function (event) {
    if (
      event.target.closest(
        "[data-favorite]"
      )
    ) {
      return;
    }

    selectCoin(coin);
  }
);

const star =
  card.querySelector(
    "[data-favorite]"
  );

if (star) {
  star.addEventListener(
    "click",
    function (event) {
      event.stopPropagation();

      toggleFavorite(
        coin.id
      );
    }
  );
}

});
}

function toggleFavorite(id) {
if (
state.favorites.includes(id)
) {
state.favorites =
state.favorites.filter(
function (item) {
return item !== id;
}
);
} else {
state.favorites.push(id);
}

localStorage.setItem(
"cv_favorites",
JSON.stringify(
state.favorites
)
);

renderCoins(
state.coins
);
}

function selectCoin(coin) {
state.selected = coin;

updateSelectedCoin(
coin
);

const symbol =
"BINANCE:" +
coin.symbol.toUpperCase() +
"USDT";

loadTradingView(
symbol
);
}

function updateSelectedCoin(coin) {
const name =
$(".selected-asset > strong");

const symbol =
$(".selected-asset > span");

const price =
$(".chart-price strong");

const change =
$(".chart-price span");

if (name) {
name.textContent =
coin.name;
}

if (symbol) {
symbol.textContent =
coin.symbol.toUpperCase();
}

if (price) {
price.textContent =
formatPrice(
coin.current_price
);
}

const day =
Number(
coin.price_change_percentage_24h
) || 0;

const week =
Number(
coin.price_change_percentage_7d
) || day;

if (change) {
change.textContent =
formatPercent(day);

change.className =
  day >= 0
    ? "positive-text"
    : "negative-text";

}

updateIndicators(
coin,
day,
week
);

updatePredictions(
coin.current_price,
day,
week
);
}

function updateIndicators(
coin,
day,
week
) {
const rows =
document.querySelectorAll(
".indicator-row strong"
);

if (rows[0]) {
rows[0].textContent =
formatPrice(
coin.current_price
);
}

if (rows[1]) {
rows[1].textContent =
formatPercent(day);
}

if (rows[2]) {
rows[2].textContent =
formatLarge(
coin.total_volume
);
}

if (rows[3]) {
const rsi =
Math.max(
15,
Math.min(
85,
Math.round(
50 +
day * 2 +
week
)
)
);

rows[3].textContent =
  rsi;

}

if (rows[4]) {
const momentum =
day * 0.4 +
week * 0.6;

if (momentum > 5) {
  rows[4].textContent =
    "Strong Bullish";
} else if (momentum > 1) {
  rows[4].textContent =
    "Bullish";
} else if (momentum < -5) {
  rows[4].textContent =
    "Strong Bearish";
} else if (momentum < -1) {
  rows[4].textContent =
    "Bearish";
} else {
  rows[4].textContent =
    "Neutral";
}

}
}

function updatePredictions(
price,
day,
week
) {
const current =
Number(price);

if (!Number.isFinite(current)) {
return;
}

const momentum =
day * 0.4 +
week * 0.6;

const values = [
current *
(1 + momentum / 100 * 0.35),

current *
  (1 + momentum / 100 * 0.9),

current *
  (1 + momentum / 100 * 1.8)

];

document
.querySelectorAll(
".prediction-target"
)
.forEach(
function (
element,
index
) {
if (
values[index] !==
undefined
) {
element.textContent =
formatPrice(
values[index]
);
}
}
);
}

function updateOverview(coins) {
const btc =
coins.find(
function (coin) {
return (
coin.id ===
"bitcoin"
);
}
);

const eth =
coins.find(
function (coin) {
return (
coin.id ===
"ethereum"
);
}
);

if (btc) {
document
.querySelectorAll(
'[data-price="bitcoin"]'
)
.forEach(
function (element) {
element.textContent =
formatPrice(
btc.current_price
);
}
);
}

if (eth) {
document
.querySelectorAll(
'[data-price="ethereum"]'
)
.forEach(
function (element) {
element.textContent =
formatPrice(
eth.current_price
);
}
);
}

const changes =
coins
.map(
function (coin) {
return Number(
coin.price_change_percentage_24h
);
}
)
.filter(
Number.isFinite
);

if (!changes.length) return;

const average =
changes.reduce(
function (a, b) {
return a + b;
},
0
) /
changes.length;

const score =
Math.max(
0,
Math.min(
100,
Math.round(
50 + average * 5
)
)
);

const marketScore =
$("#marketScore");

if (marketScore) {
marketScore.textContent =
score;
}

document
.querySelectorAll(
".score-small"
)
.forEach(
function (element) {
element.textContent =
score;
}
);
}

/* =========================
TRADINGVIEW
========================= */

function loadTradingView(symbol) {
const container =
document.getElementById(
"tradingview-widget"
);

if (!container) {
console.error(
"TradingView container not found"
);

return;

}

container.innerHTML = "";

const wrapper =
document.createElement(
"div"
);

wrapper.className =
"tradingview-widget-container";

wrapper.style.width =
"100%";

wrapper.style.height =
"100%";

const widget =
document.createElement(
"div"
);

widget.className =
"tradingview-widget-container__widget";

widget.style.width =
"100%";

widget.style.height =
"100%";

wrapper.appendChild(
widget
);

container.appendChild(
wrapper
);

const script =
document.createElement(
"script"
);

script.type =
"text/javascript";

script.src =
"https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

script.async = true;

script.textContent =
JSON.stringify({
autosize: true,
symbol: symbol,
interval: "60",
timezone: "Etc/UTC",
theme: "dark",
style: "1",
locale: "en",
backgroundColor:
"rgba(0,0,0,0)",
gridColor:
"rgba(255,255,255,0.06)",
hide_top_toolbar: false,
hide_legend: false,
allow_symbol_change: true,
save_image: false,
hide_volume: false,
support_host:
"https://www.tradingview.com"
});

wrapper.appendChild(
script
);
}

/* =========================
SEARCH
========================= */

function setupSearch() {
const input =
document.querySelector(
".topbar-search input"
);

if (!input) return;

input.addEventListener(
"input",
function () {
const query =
input.value
.trim()
.toLowerCase();

  if (!query) {
    renderCoins(
      state.coins
    );

    return;
  }

  const filtered =
    state.coins.filter(
      function (coin) {
        return (
          coin.name
            .toLowerCase()
            .includes(query) ||
          coin.symbol
            .toLowerCase()
            .includes(query)
        );
      }
    );

  renderCoins(
    filtered
  );
}

);
}

/* =========================
SCANNER
========================= */

function setupScanner() {
const button =
$("#runScanner");

if (!button) return;

button.addEventListener(
"click",
function () {
const result =
$(".scanner-results");

  if (!result) return;

  if (!state.coins.length) {
    const msg =
document.createElement(
"p"
);

    msg.textContent =
"Market data is loading...";

    result.innerHTML = "";
    result.appendChild(msg);

    return;
  }

  const sorted =
    state.coins
      .slice()
      .sort(
        function (a, b) {
          return (
            (Number(
              b.price_change_percentage_24h
            ) || 0) -
            (Number(
              a.price_change_percentage_24h
            ) || 0)
          );
        }
      );

  result.innerHTML = "";

  sorted
    .slice(0, 10)
    .forEach(
      function (coin) {
        const change =
          Number(
            coin.price_change_percentage_24h
          ) || 0;

        const row =
          document.createElement(
            "div"
          );

        row.className =
          "mini-opportunity";

        row.innerHTML = `
          <div class="mini-opportunity-coin">

            <img
              src="${coin.image}"
              width="34"
              height="34"
              alt=""
            >

            <div>
              <strong>
                ${coin.name}
              </strong>

              <small>
                ${coin.symbol.toUpperCase()}
              </small>
            </div>

          </div>

          <strong class="${
            change >= 0
              ? "positive-text"
              : "negative-text"
          }">
            ${formatPercent(change)}
          </strong>
        `;

        result.appendChild(
          row
        );
      }
    );
}

);
}

/* =========================
NAVIGATION
========================= */

function setupNavigation() {
document
.querySelectorAll(
'.nav-item[href^="#"]'
)
.forEach(
function (link) {
link.addEventListener(
"click",
function () {
document
.querySelectorAll(
".nav-item"
)
.forEach(
function (item) {
item.classList.remove(
"active"
);
}
);

        link.classList.add(
          "active"
        );
      }
    );
  }
);

}

/* =========================
MOBILE
========================= */

function setupMobileMenu() {
const button =
$(".mobile-menu");

const sidebar =
$(".sidebar");

if (!button || !sidebar) {
return;
}

button.addEventListener(
"click",
function () {
sidebar.classList.toggle(
"open"
);
}
);
}

/* =========================
START
========================= */

async function start() {
showLoading(
"Loading live cryptocurrency markets..."
);

setupSearch();
setupScanner();
setupNavigation();
setupMobileMenu();

try {
state.coins =
await loadCoins();

renderCoins(
  state.coins
);

updateOverview(
  state.coins
);

if (
  state.coins.length
) {
  selectCoin(
    state.coins[0]
  );
}

} catch (error) {
console.error(
"CryptoVision:",
error
);

showLoading(
  "Unable to load market data. Please refresh."
);

}
}

document.addEventListener(
"DOMContentLoaded",
start
);
