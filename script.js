const API = "https://api.coingecko.com/api/v3";

const state = {
coins: [],
selected: "bitcoin",
currency: "usd",
favorites: JSON.parse(localStorage.getItem("cv_favorites") || "[]")
};

const $ = (selector) => document.querySelector(selector);

function money(value) {
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

function percent(value) {
const n = Number(value);

if (!Number.isFinite(n)) return "--";

return "${n >= 0 ? "+" : ""}${n.toFixed(2)}%";
}

function largeNumber(value) {
const n = Number(value);

if (!Number.isFinite(n) || n === 0) return "--";

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

function escapeHTML(value) {
return String(value ?? "")
.replaceAll("&", "&")
.replaceAll("<", "<")
.replaceAll(">", ">")
.replaceAll('"', """)
.replaceAll("'", "'");
}

async function fetchJSON(url) {
const response = await fetch(url, {
headers: {
Accept: "application/json"
}
});

if (!response.ok) {
throw new Error("API Error ${response.status}");
}

return response.json();
}

async function loadMarketData() {
const grid = $("#coinGrid");

try {
if (grid) {
grid.innerHTML = "<div class="loading-card"> Loading market data... </div>";
}

const url =
  `${API}/coins/markets` +
  `?vs_currency=${state.currency}` +
  `&order=market_cap_desc` +
  `&per_page=20` +
  `&page=1` +
  `&sparkline=true` +
  `&price_change_percentage=24h,7d`;

const data = await fetchJSON(url);

if (!Array.isArray(data)) {
  throw new Error("Invalid market data");
}

state.coins = data;

renderCoins(data);
updateTicker();
updatePrices();
updateMarketPulse();

if (
  !state.coins.some(
    (coin) => coin.id === state.selected
  )
) {
  if (state.coins[0]) {
    state.selected = state.coins[0].id;
  }
}

if (state.coins.length) {
  selectCoin(state.selected);
}

} catch (error) {
console.error(
"CryptoVision market error:",
error
);

if (grid) {
  grid.innerHTML = `
    <div class="loading-card error-card">
      <strong>Unable to load market data</strong>
      <small>${escapeHTML(error.message)}</small>
      <button
        class="secondary-button"
        type="button"
        id="retryMarket"
      >
        Retry
      </button>
    </div>
  `;

  const retry = $("#retryMarket");

  if (retry) {
    retry.addEventListener(
      "click",
      loadMarketData
    );
  }
}

}
}

const loadMarket = loadMarketData;

function renderCoins(coins) {
const grid = $("#coinGrid");

if (!grid) return;

if (!coins.length) {
grid.innerHTML = "<div class="loading-card"> No cryptocurrency found. </div>";

return;

}

grid.innerHTML = coins
.slice(0, 20)
.map((coin) => {

  const change =
    Number(
      coin.price_change_percentage_24h
    ) || 0;

  const favorite =
    state.favorites.includes(coin.id);

  return `
    <article
      class="coin-card"
      data-coin="${escapeHTML(coin.id)}"
    >

      <div class="coin-card-top">

        <div class="coin-identity">

          <img
            class="coin-logo"
            src="${escapeHTML(coin.image)}"
            alt="${escapeHTML(coin.name)}"
            loading="lazy"
          >

          <div>
            <strong>
              ${escapeHTML(coin.name)}
            </strong>

            <span>
              ${escapeHTML(
                coin.symbol.toUpperCase()
              )}
            </span>
          </div>

        </div>

        <button
          class="star-button ${
            favorite ? "active" : ""
          }"
          data-favorite="${escapeHTML(
            coin.id
          )}"
          type="button"
          aria-label="Favorite"
        >
          ${favorite ? "★" : "☆"}
        </button>

      </div>

      <div class="coin-price">

        <strong>
          ${money(coin.current_price)}
        </strong>

        <span
          class="${
            change >= 0
              ? "positive-text"
              : "negative-text"
          }"
        >
          ${percent(change)}
        </span>

      </div>

      <div class="coin-card-bottom">

        <span>Market Cap</span>

        <strong>
          ${largeNumber(coin.market_cap)}
        </strong>

      </div>

    </article>
  `;
})
.join("");

grid
.querySelectorAll(".coin-card")
.forEach((card) => {

  card.addEventListener(
    "click",
    () => {
      selectCoin(card.dataset.coin);
    }
  );

});

grid
.querySelectorAll("[data-favorite]")
.forEach((button) => {

  button.addEventListener(
    "click",
    (event) => {

      event.stopPropagation();

      toggleFavorite(
        button.dataset.favorite
      );

    }
  );

});

}

function updateTicker() {

const ticker =
$("#tickerItems") ||
$(".ticker-items");

if (!ticker) return;

ticker.innerHTML =
state.coins
.slice(0, 10)
.map((coin) => {

    const change =
      Number(
        coin.price_change_percentage_24h
      ) || 0;

    return `
      <div class="ticker-item">

        <span>
          ${escapeHTML(
            coin.symbol.toUpperCase()
          )}
        </span>

        <strong
          class="${
            change >= 0
              ? "positive-text"
              : "negative-text"
          }"
        >
          ${percent(change)}
        </strong>

      </div>
    `;
  })
  .join("");

}

function updatePrices() {

["bitcoin", "ethereum"].forEach(
(id) => {

  const coin =
    state.coins.find(
      (item) => item.id === id
    );

  if (!coin) return;

  document
    .querySelectorAll(
      `[data-price="${id}"]`
    )
    .forEach(
      (element) => {
        element.textContent =
          money(
            coin.current_price
          );
      }
    );
}

);
}

function updateMarketPulse() {

const changes =
state.coins
.map(
(coin) =>
Number(
coin.price_change_percentage_24h
)
)
.filter(Number.isFinite);

if (!changes.length) return;

const average =
changes.reduce(
(a, b) => a + b,
0
) / changes.length;

const score = Math.max(
0,
Math.min(
100,
Math.round(
50 + average * 5
)
)
);

const scoreElement =
$("#marketScore");

if (scoreElement) {
scoreElement.textContent =
score;
}

document
.querySelectorAll(".score-small")
.forEach(
(element) => {
element.textContent =
score;
}
);

const status =
document.querySelector(
".pulse-info strong"
);

if (!status) return;

if (score >= 65) {

status.textContent =
  "Bullish";

status.className =
  "positive-text";

} else if (score <= 35) {

status.textContent =
  "Bearish";

status.className =
  "negative-text";

} else {

status.textContent =
  "Neutral";

status.className =
  "warning-text";

}
}

function selectCoin(id) {

const coin =
state.coins.find(
(item) => item.id === id
);

if (!coin) return;

state.selected = id;

const name =
$(".selected-asset strong");

const symbol =
$(".selected-asset span");

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
money(
coin.current_price
);
}

if (change) {

const value =
  Number(
    coin.price_change_percentage_24h
  ) || 0;

change.textContent =
  percent(value);

change.className =
  value >= 0
    ? "positive-text"
    : "negative-text";

}

loadCoinDetails(id);

loadTradingView(
coin.symbol.toUpperCase()
);
}

async function loadCoinDetails(id) {

try {

const data =
  await fetchJSON(
    `${API}/coins/${encodeURIComponent(id)}` +
    `?localization=false` +
    `&tickers=false` +
    `&market_data=true` +
    `&community_data=false` +
    `&developer_data=false`
  );

updateAnalysis(data);

} catch (error) {

console.error(
  "Coin details error:",
  error
);

}
}

function updateAnalysis(data) {

const market =
data.market_data;

if (!market) return;

const price =
market.current_price?.usd;

const change =
market.price_change_percentage_24h;

const volume =
market.total_volume?.usd;

const rows =
document.querySelectorAll(
".indicator-row"
);

if (
rows[0]?.querySelector("strong")
) {
rows[0]
.querySelector("strong")
.textContent =
money(price);
}

if (
rows[1]?.querySelector("strong")
) {
rows[1]
.querySelector("strong")
.textContent =
percent(change);
}

if (
rows[2]?.querySelector("strong")
) {
rows[2]
.querySelector("strong")
.textContent =
largeNumber(volume);
}

const score =
Math.max(
0,
Math.min(
100,
Math.round(
50 +
Number(change || 0) * 4
)
)
);

document
.querySelectorAll(".score-small")
.forEach(
(element) => {
element.textContent =
score;
}
);

if ($("#marketScore")) {
$("#marketScore").textContent =
score;
}

updatePrediction(data);
}

function updatePrediction(data) {

const market =
data.market_data;

if (!market) return;

const price =
Number(
market.current_price?.usd
) || 0;

const day =
Number(
market.price_change_percentage_24h
) || 0;

const week =
Number(
market.price_change_percentage_7d
) || day;

const momentum =
day * 0.4 +
week * 0.6;

const predictions = [

price *
  (1 +
    (momentum / 100) *
    0.35),

price *
  (1 +
    (momentum / 100) *
    0.9),

price *
  (1 +
    (momentum / 100) *
    1.8)

];

document
.querySelectorAll(
".prediction-target"
)
.forEach(
(element, index) => {

    if (
      predictions[index] !==
      undefined
    ) {
      element.textContent =
        money(
          predictions[index]
        );
    }

  }
);

}

function loadTradingView(symbol) {

const container =
$("#tradingview-widget");

if (!container) return;

container.innerHTML = "";

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

const script =
document.createElement(
"script"
);

script.src =
"https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

script.async = true;

script.innerHTML =
JSON.stringify({

  autosize: true,

  symbol:
    `BINANCE:${symbol}USDT`,

  interval:
    "60",

  timezone:
    "Etc/UTC",

  theme:
    "dark",

  style:
    "1",

  locale:
    "en",

  enable_publishing:
    false,

  allow_symbol_change:
    true,

  hide_top_toolbar:
    false,

  hide_legend:
    false,

  save_image:
    false,

  studies: [
    "RSI@tv-basicstudies",
    "MACD@tv-basicstudies"
  ]

});

container.appendChild(
widget
);

container.appendChild(
script
);
}

function toggleFavorite(id) {

if (
state.favorites.includes(id)
) {

state.favorites =
  state.favorites.filter(
    (item) =>
      item !== id
  );

} else {

state.favorites = [
  ...state.favorites,
  id
];

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

function setupSearch() {

const input =
$(".topbar-search input");

if (!input) return;

input.addEventListener(
"input",
() => {

  const query =
    input.value
      .trim()
      .toLowerCase();

  const filtered =
    !query
      ? state.coins
      : state.coins.filter(
          (coin) =>
            coin.name
              .toLowerCase()
              .includes(query) ||
            coin.symbol
              .toLowerCase()
              .includes(query)
        );

  renderCoins(
    filtered
  );
}

);
}

function setupScanner() {

const button =
$("#runScanner");

if (!button) return;

button.addEventListener(
"click",
() => {

  const result =
    $(".scanner-results");

  if (!result) return;

  const coins =
    [...state.coins]
      .sort(
        (a, b) =>
          Number(
            b.price_change_percentage_24h
          ) -
          Number(
            a.price_change_percentage_24h
          )
      )
      .slice(0, 5);

  if (!coins.length) {

    result.innerHTML =
      `
        <div class="scanner-empty">
          Market data is still loading.
        </div>
      `;

    return;
  }

  result.innerHTML =
    coins
      .map(
        (coin) => {

          const change =
            Number(
              coin.price_change_percentage_24h
            ) || 0;

          return `
            <div
              class="mini-opportunity"
            >

              <div
                class="mini-opportunity-coin"
              >

                <img
                  src="${escapeHTML(
                    coin.image
                  )}"
                  width="34"
                  height="34"
                  alt=""
                >

                <div>

                  <strong>
                    ${escapeHTML(
                      coin.name
                    )}
                  </strong>

                  <small>
                    ${escapeHTML(
                      coin.symbol.toUpperCase()
                    )}
                  </small>

                </div>

              </div>

              <strong
                class="${
                  change >= 0
                    ? "positive-text"
                    : "negative-text"
                }"
              >
                ${percent(change)}
              </strong>

            </div>
          `;
        }
      )
      .join("");
}

);
}

function setupNavigation() {

document
.querySelectorAll(
'.nav-item[href^="#"]'
)
.forEach(
(item) => {

    item.addEventListener(
      "click",
      (event) => {

        const selector =
          item.getAttribute(
            "href"
          );

        const target =
          document.querySelector(
            selector
          );

        if (!target) return;

        event.preventDefault();

        target.scrollIntoView({
          behavior:
            "smooth",

          block:
            "start"
        });

        document
          .querySelectorAll(
            ".nav-item"
          )
          .forEach(
            (nav) =>
              nav.classList.remove(
                "active"
              )
          );

        item.classList.add(
          "active"
        );
      }
    );

  }
);

}

function setupMobileMenu() {

const button =
$(".mobile-menu");

const sidebar =
$(".sidebar");

if (!button || !sidebar) return;

button.addEventListener(
"click",
() => {
sidebar.classList.toggle(
"open"
);
}
);
}

function setupTimeButtons() {

document
.querySelectorAll(
".time-button"
)
.forEach(
(button) => {

    button.addEventListener(
      "click",
      () => {

        document
          .querySelectorAll(
            ".time-button"
          )
          .forEach(
            (item) =>
              item.classList.remove(
                "active"
              )
          );

        button.classList.add(
          "active"
        );

        const coin =
          state.coins.find(
            (item) =>
              item.id ===
              state.selected
          );

        if (coin) {

          loadTradingView(
            coin.symbol.toUpperCase()
          );

        }

      }
    );
  }
);

}

function init() {

setupSearch();

setupScanner();

setupNavigation();

setupMobileMenu();

setupTimeButtons();

loadMarketData();

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

document.addEventListener(
"DOMContentLoaded",
init
);
