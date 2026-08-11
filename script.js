const API = "https://api.coingecko.com/api/v3";

const state = {
coins: [],
favorites: JSON.parse(localStorage.getItem("cv_favorites") || "[]"),
selected: "bitcoin",
currency: "usd"
};

const $ = (selector) => document.querySelector(selector);

/* =========================================================
HELPERS
========================================================= */

function money(value) {
if (value === null || value === undefined) return "--";

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
if (value === null || value === undefined) return "--";

const n = Number(value);

if (!Number.isFinite(n)) return "--";

return "${n >= 0 ? "+" : ""}${n.toFixed(2)}%";
}

function largeNumber(value) {
if (!value) return "--";

const n = Number(value);

if (!Number.isFinite(n)) return "--";

if (n >= 1e12)
return "$" + (n / 1e12).toFixed(2) + "T";

if (n >= 1e9)
return "$" + (n / 1e9).toFixed(2) + "B";

if (n >= 1e6)
return "$" + (n / 1e6).toFixed(2) + "M";

return "$" + n.toLocaleString();
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
method: "GET",
headers: {
Accept: "application/json"
}
});

if (!response.ok) {
throw new Error("API Error ${response.status}");
}

return response.json();
}

/* =========================================================
MARKET DATA
========================================================= */

async function loadMarketData() {

try {

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

renderCoins(state.coins);
updateTicker();
updatePrices();
updateMarketPulse();

const selectedExists =
  state.coins.some(
    coin => coin.id === state.selected
  );

if (!selectedExists && state.coins.length) {
  state.selected = state.coins[0].id;
}

if (state.coins.length) {
  selectCoin(state.selected);
}

} catch (error) {

console.error(
  "CryptoVision market error:",
  error
);

showError();

}
}

/* Compatibility with previous versions */

const loadMarket = loadMarketData;

/* =========================================================
COIN GRID
========================================================= */

function renderCoins(coins) {

const grid = $("#coinGrid");

if (!grid) return;

grid.innerHTML = "";

if (!coins.length) {

grid.innerHTML = `
  <div class="loading-card">
    No cryptocurrency found.
  </div>
`;

return;

}

coins.slice(0, 20).forEach(coin => {

const change =
  Number(
    coin.price_change_percentage_24h || 0
  );

const positive =
  change >= 0;

const favorite =
  state.favorites.includes(coin.id);


const card =
  document.createElement("article");

card.className = "coin-card";

card.dataset.coin = coin.id;


card.innerHTML = `

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
      class="star-button ${favorite ? "active" : ""}"
      data-favorite="${escapeHTML(coin.id)}"
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
        positive
          ? "positive-text"
          : "negative-text"
      }"
    >
      ${percent(change)}
    </span>

  </div>


  <div class="coin-card-bottom">

    <span>
      Market Cap
    </span>

    <strong>
      ${largeNumber(coin.market_cap)}
    </strong>

  </div>


  <div class="mini-chart"></div>

`;


card.addEventListener(
  "click",
  () => selectCoin(coin.id)
);


const favoriteButton =
  card.querySelector(
    "[data-favorite]"
  );


favoriteButton?.addEventListener(
  "click",
  event => {

    event.stopPropagation();

    toggleFavorite(coin.id);

  }
);


grid.appendChild(card);

});
}

/* =========================================================
TICKER
========================================================= */

function updateTicker() {

const ticker =
$("#tickerItems") ||
$(".ticker-items");

if (!ticker) return;

ticker.innerHTML =
state.coins
.slice(0, 10)
.map(coin => {

    const change =
      Number(
        coin.price_change_percentage_24h || 0
      );

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

/* =========================================================
BTC / ETH
========================================================= */

function updatePrices() {

const bitcoin =
state.coins.find(
coin => coin.id === "bitcoin"
);

const ethereum =
state.coins.find(
coin => coin.id === "ethereum"
);

if (bitcoin) {

document
  .querySelectorAll(
    '[data-price="bitcoin"]'
  )
  .forEach(
    element => {
      element.textContent =
        money(
          bitcoin.current_price
        );
    }
  );

}

if (ethereum) {

document
  .querySelectorAll(
    '[data-price="ethereum"]'
  )
  .forEach(
    element => {
      element.textContent =
        money(
          ethereum.current_price
        );
    }
  );

}
}

/* =========================================================
MARKET PULSE
========================================================= */

function updateMarketPulse() {

const changes =
state.coins
.map(
coin =>
Number(
coin.price_change_percentage_24h
)
)
.filter(
value => Number.isFinite(value)
);

if (!changes.length) return;

const average =
changes.reduce(
(a, b) => a + b,
0
) / changes.length;

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

const scoreElement =
$("#marketScore");

const smallScore =
$(".score-small");

if (scoreElement) {
scoreElement.textContent =
score;
}

if (smallScore) {
smallScore.textContent =
score;
}

const status =
$(".pulse-info strong");

if (status) {

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
}

/* =========================================================
SELECT COIN
========================================================= */

function selectCoin(id) {

const coin =
state.coins.find(
item => item.id === id
);

if (!coin) return;

state.selected = id;

const name =
$(".selected-asset strong");

const symbol =
$(".selected-asset span");

const price =
$(".chart-price strong");

const changeElement =
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
money(coin.current_price);
}

if (changeElement) {

const change =
  Number(
    coin.price_change_percentage_24h || 0
  );


changeElement.textContent =
  percent(change);


changeElement.className =
  change >= 0
    ? "positive-text"
    : "negative-text";

}

loadCoinDetails(id);

loadTradingView(
coin.symbol.toUpperCase()
);
}

/* =========================================================
COIN DETAILS
========================================================= */

async function loadCoinDetails(id) {

try {

const url =
  `${API}/coins/${encodeURIComponent(id)}` +
  `?localization=false` +
  `&tickers=false` +
  `&market_data=true` +
  `&community_data=false` +
  `&developer_data=false`;


const data =
  await fetchJSON(url);


updateAnalysis(data);

} catch (error) {

console.error(
  "Coin details error:",
  error
);

}
}

/* =========================================================
TECHNICAL ANALYSIS
========================================================= */

function updateAnalysis(data) {

const market =
data.market_data;

if (!market) return;

const price =
market.current_price?.usd || 0;

const change =
market.price_change_percentage_24h || 0;

const volume =
market.total_volume?.usd || 0;

const rows =
document.querySelectorAll(
".indicator-row"
);

if (rows[0]) {

const strong =
  rows[0].querySelector(
    "strong"
  );

if (strong) {
  strong.textContent =
    money(price);
}

}

if (rows[1]) {

const strong =
  rows[1].querySelector(
    "strong"
  );

if (strong) {

  strong.textContent =
    percent(change);

}

}

if (rows[2]) {

const strong =
  rows[2].querySelector(
    "strong"
  );

if (strong) {

  strong.textContent =
    largeNumber(volume);

}

}

const score =
Math.max(
0,
Math.min(
100,
Math.round(
50 + Number(change) * 4
)
)
);

const scoreSmall =
$(".score-small");

if (scoreSmall) {
scoreSmall.textContent =
score;
}

const marketScore =
$("#marketScore");

if (marketScore) {
marketScore.textContent =
score;
}

updatePrediction(data);
}

/* =========================================================
PREDICTION
========================================================= */

function updatePrediction(data) {

const market =
data.market_data;

if (!market) return;

const price =
market.current_price?.usd || 0;

const day =
Number(
market.price_change_percentage_24h || 0
);

const week =
Number(
market.price_change_percentage_7d ||
day
);

const momentum =
day * 0.4 +
week * 0.6;

const predictions = [

price *
  (1 + momentum / 100 * 0.35),

price *
  (1 + momentum / 100 * 0.9),

price *
  (1 + momentum / 100 * 1.8)

];

document
.querySelectorAll(
".prediction-target"
)
.forEach(
(element, index) => {

    if (
      predictions[index] !== undefined
    ) {

      element.textContent =
        money(
          predictions[index]
        );

    }

  }
);

}

/* =========================================================
TRADINGVIEW
========================================================= */

function loadTradingView(symbol) {

const container =
$("#tradingview-widget");

if (!container) return;

container.innerHTML = `

<div
  class="tradingview-widget-container__widget"
  style="
    width:100%;
    height:100%;
  "
></div>

`;

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

  interval: "60",

  timezone:
    "Etc/UTC",

  theme: "dark",

  style: "1",

  locale: "en",

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
script
);
}

/* =========================================================
FAVORITES
========================================================= */

function toggleFavorite(id) {

if (
state.favorites.includes(id)
) {

state.favorites =
  state.favorites.filter(
    coinId => coinId !== id
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

/* =========================================================
SEARCH
========================================================= */

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


  if (!query) {

    renderCoins(
      state.coins
    );

    return;

  }


  const filtered =
    state.coins.filter(
      coin =>
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

/* =========================================================
SCANNER
========================================================= */

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


  if (!state.coins.length) {

    result.innerHTML = `
      <div class="scanner-empty">
        Market data is still loading.
      </div>
    `;

    return;

  }


  const coins =
    [...state.coins]
      .sort(
        (a, b) =>
          Number(
            b.price_change_percentage_24h ||
            0
          ) -
          Number(
            a.price_change_percentage_24h ||
            0
          )
      )
      .slice(0, 5);


  result.innerHTML =
    coins
      .map(
        coin => `

          <div class="mini-opportunity">

            <div
              class="mini-opportunity-coin"
            >

              <img
                src="${escapeHTML(
                  coin.image
                )}"
                width="34"
                height="34"
                style="
                  border-radius:50%;
                "
                loading="lazy"
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
                Number(
                  coin.price_change_percentage_24h ||
                  0
                ) >= 0
                  ? "positive-text"
                  : "negative-text"
              }"
            >

              ${percent(
                coin.price_change_percentage_24h
              )}

            </strong>

          </div>

        `
      )
      .join("");

}

);
}

/* =========================================================
NAVIGATION
========================================================= */

function setupNavigation() {

document
.querySelectorAll(
'.nav-item[href^="#"]'
)
.forEach(
item => {

    item.addEventListener(
      "click",
      event => {

        const target =
          document.querySelector(
            item.getAttribute(
              "href"
            )
          );


        if (!target) return;


        event.preventDefault();


        target.scrollIntoView({
          behavior: "smooth",
          block: "start"
        });


        document
          .querySelectorAll(
            ".nav-item"
          )
          .forEach(
            nav =>
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

/* =========================================================
MOBILE MENU
========================================================= */

function setupMobileMenu() {

const button =
$(".mobile-menu");

const sidebar =
$(".sidebar");

if (!button || !sidebar)
return;

button.addEventListener(
"click",
() => {

  sidebar.classList.toggle(
    "open"
  );

}

);
}

/* =========================================================
TIME BUTTONS
========================================================= */

function setupTimeButtons() {

document
.querySelectorAll(
".time-button"
)
.forEach(
button => {

    button.addEventListener(
      "click",
      () => {

        document
          .querySelectorAll(
            ".time-button"
          )
          .forEach(
            b =>
              b.classList.remove(
                "active"
              )
          );


        button.classList.add(
          "active"
        );

      }
    );

  }
);

}

/* =========================================================
ERROR
========================================================= */

function showError() {

const grid =
$("#coinGrid");

if (!grid) return;

grid.innerHTML = `

<div
  class="loading-card"
  style="color:#ff6477"
>

  ⚠ Unable to load market data.

  <br><br>

  <button
    type="button"
    onclick="loadMarketData()"
    class="secondary-button"
  >
    Retry
  </button>

</div>

`;
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
INITIALIZATION
========================================================= */

document.addEventListener(
"DOMContentLoaded",
() => {

setupSearch();

setupScanner();

setupNavigation();

setupMobileMenu();

setupTimeButtons();

loadMarketData();

startAutoRefresh();

console.log(
  "CryptoVision initialized successfully."
);

}
);
