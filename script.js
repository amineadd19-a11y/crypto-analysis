const COINGECKO_API =
"https://api.coingecko.com/api/v3/coins/markets";

const state = {
crypto: [],
selected: null,
favorites: JSON.parse(
localStorage.getItem("cv_favorites") || "[]"
),
marketType: "crypto"
};

const STOCKS = [
{ name: "Apple", symbol: "AAPL", tv: "NASDAQ:AAPL", type: "Stock" },
{ name: "NVIDIA", symbol: "NVDA", tv: "NASDAQ:NVDA", type: "Stock" },
{ name: "Microsoft", symbol: "MSFT", tv: "NASDAQ:MSFT", type: "Stock" },
{ name: "Amazon", symbol: "AMZN", tv: "NASDAQ:AMZN", type: "Stock" },
{ name: "Alphabet", symbol: "GOOGL", tv: "NASDAQ:GOOGL", type: "Stock" },
{ name: "Meta", symbol: "META", tv: "NASDAQ:META", type: "Stock" },
{ name: "Tesla", symbol: "TSLA", tv: "NASDAQ:TSLA", type: "Stock" },
{ name: "AMD", symbol: "AMD", tv: "NASDAQ:AMD", type: "Stock" },
{ name: "Netflix", symbol: "NFLX", tv: "NASDAQ:NFLX", type: "Stock" },
{ name: "Berkshire Hathaway", symbol: "BRK.B", tv: "NYSE:BRK.B", type: "Stock" },
{ name: "JPMorgan", symbol: "JPM", tv: "NYSE:JPM", type: "Stock" },
{ name: "Visa", symbol: "V", tv: "NYSE:V", type: "Stock" }
];

const INDICES = [
{ name: "S&P 500", symbol: "SPX", tv: "SP:SPX", type: "Index" },
{ name: "Nasdaq 100", symbol: "NDX", tv: "NASDAQ:NDX", type: "Index" },
{ name: "Dow Jones", symbol: "DJI", tv: "DJ:DJI", type: "Index" },
{ name: "Russell 2000", symbol: "RUT", tv: "CBOE:RUT", type: "Index" },
{ name: "VIX", symbol: "VIX", tv: "CBOE:VIX", type: "Index" }
];

const COMMODITIES = [
{ name: "Gold", symbol: "XAUUSD", tv: "OANDA:XAUUSD", type: "Commodity" },
{ name: "Silver", symbol: "XAGUSD", tv: "OANDA:XAGUSD", type: "Commodity" },
{ name: "Crude Oil", symbol: "WTI", tv: "TVC:USOIL", type: "Commodity" },
{ name: "Brent Oil", symbol: "BRENT", tv: "TVC:UKOIL", type: "Commodity" },
{ name: "Natural Gas", symbol: "NATGAS", tv: "TVC:NATURALGAS", type: "Commodity" }
];

const MEME_IDS = [
"dogecoin",
"shiba-inu",
"pepe",
"floki",
"bonk",
"dogwifcoin",
"mog-coin",
"brett",
"popcat",
"book-of-meme"
];

function $(selector) {
return document.querySelector(selector);
}

function money(value) {
const n = Number(value);

if (!Number.isFinite(n)) {
return "--";
}

if (n >= 1000) {
return (
"$" +
n.toLocaleString("en-US", {
maximumFractionDigits: 0
})
);
}

if (n >= 1) {
return (
"$" +
n.toLocaleString("en-US", {
minimumFractionDigits: 2,
maximumFractionDigits: 2
})
);
}

return (
"$" +
n.toLocaleString("en-US", {
minimumFractionDigits: 4,
maximumFractionDigits: 8
})
);
}

function percent(value) {
const n = Number(value);

if (!Number.isFinite(n)) {
return "--";
}

return (
(n >= 0 ? "+" : "") +
n.toFixed(2) +
"%"
);
}

function largeNumber(value) {
const n = Number(value);

if (!Number.isFinite(n)) {
return "--";
}

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
throw new Error("API " + response.status);
}

return await response.json();
}

function showMessage(message) {
const grid = $("#coinGrid");

if (!grid) {
return;
}

grid.innerHTML =
'<div class="loading-card">' +
escapeHTML(message) +
"</div>";
}

async function loadCrypto() {
try {
showMessage(
"Loading live cryptocurrency markets..."
);

const url =
  COINGECKO_API +
  "?vs_currency=usd" +
  "&order=market_cap_desc" +
  "&per_page=100" +
  "&page=1" +
  "&sparkline=false" +
  "&price_change_percentage=24h,7d";

const coins = await fetchJSON(url);

if (!Array.isArray(coins)) {
  throw new Error("Invalid market response");
}

state.crypto = coins;

renderCrypto(coins);
updateOverview(coins);

if (!state.selected) {
  state.selected = coins[0];
}

if (state.selected && state.selected.id) {
  const fresh =
    coins.find(
      coin => coin.id === state.selected.id
    );

  if (fresh) {
    state.selected = fresh;
    updateAnalysis(fresh);
  }
}

} catch (error) {
console.error(
"CryptoVision crypto error:",
error
);

showMessage(
  "Crypto market data temporarily unavailable."
);

}
}

function renderCrypto(coins) {
const grid = $("#coinGrid");

if (!grid) {
return;
}

grid.innerHTML = "";

coins.forEach(coin => {
const change =
Number(
coin.price_change_percentage_24h
) || 0;

const card =
  document.createElement("article");

card.className = "coin-card";

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
      class="star-button ${
        state.favorites.includes(coin.id)
          ? "active"
          : ""
      }"
      type="button"
      data-favorite="${escapeHTML(
        coin.id
      )}"
    >
      ${
        state.favorites.includes(coin.id)
          ? "★"
          : "☆"
      }
    </button>

  </div>

  <div class="coin-price">

    <strong>
      ${money(coin.current_price)}
    </strong>

    <span class="${
      change >= 0
        ? "positive-text"
        : "negative-text"
    }">
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
`;

grid.appendChild(card);

card.addEventListener(
  "click",
  event => {

    if (
      event.target.closest(
        "[data-favorite]"
      )
    ) {
      return;
    }

    selectCrypto(coin);
  }
);

const favorite =
  card.querySelector(
    "[data-favorite]"
  );

if (favorite) {
  favorite.addEventListener(
    "click",
    event => {

      event.stopPropagation();

      toggleFavorite(
        favorite.dataset.favorite
      );
    }
  );
}

});
}

function toggleFavorite(id) {
if (state.favorites.includes(id)) {

state.favorites =
  state.favorites.filter(
    item => item !== id
  );

} else {

state.favorites.push(id);

}

localStorage.setItem(
"cv_favorites",
JSON.stringify(state.favorites)
);

renderCrypto(state.crypto);
}

function selectCrypto(coin) {
state.selected = coin;

updateAnalysis(coin);

loadTradingView(
"BINANCE:" +
coin.symbol.toUpperCase() +
"USDT"
);
}

function updateAnalysis(coin) {
const name =
$(".selected-asset > strong");

const symbol =
$(".selected-asset > span");

const price =
$(".chart-price strong");

const change =
$(".chart-price span");

if (name) {
name.textContent = coin.name;
}

if (symbol) {
symbol.textContent =
coin.symbol.toUpperCase();
}

if (price) {
price.textContent =
money(coin.current_price);
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
percent(day);

change.className =
  day >= 0
    ? "positive-text"
    : "negative-text";

}

const rows =
document.querySelectorAll(
".indicator-row strong"
);

if (rows[0]) {
rows[0].textContent =
money(coin.current_price);
}

if (rows[1]) {
rows[1].textContent =
percent(day);
}

if (rows[2]) {
rows[2].textContent =
largeNumber(coin.total_volume);
}

if (rows[3]) {
rows[3].textContent =
calculateRSIStyle(day, week);
}

if (rows[4]) {
rows[4].textContent =
calculateMomentum(day, week);
}

updatePredictions(
coin.current_price,
day,
week
);

updateRisk(
day,
week
);
}

function calculateRSIStyle(day, week) {
const score =
50 +
day * 2 +
week;

const rsi =
Math.max(
15,
Math.min(85, Math.round(score))
);

return rsi;
}

function calculateMomentum(day, week) {
const value =
day * 0.4 +
week * 0.6;

if (value > 5) {
return "Strong Bullish";
}

if (value > 1) {
return "Bullish";
}

if (value < -5) {
return "Strong Bearish";
}

if (value < -1) {
return "Bearish";
}

return "Neutral";
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

const targets = [
current *
(1 + momentum / 100 * 0.35),

current *
  (1 + momentum / 100 * 0.90),

current *
  (1 + momentum / 100 * 1.80)

];

document
.querySelectorAll(
".prediction-target"
)
.forEach(
(element, index) => {

    if (
      targets[index] !== undefined
    ) {
      element.textContent =
        money(targets[index]);
    }
  }
);

}

function updateRisk(day, week) {
const volatility =
Math.abs(day) +
Math.abs(week) * 0.35;

let risk =
Math.round(
Math.min(
100,
30 + volatility * 4
)
);

const aiCards =
document.querySelectorAll(
".ai-card"
);

if (
aiCards.length > 0
) {
const first =
aiCards[0].querySelector("p");

if (first) {
  first.textContent =
    "Risk Score: " +
    risk +
    "/100. Momentum and recent price volatility are being evaluated.";
}

}
}

function updateOverview(coins) {
const btc =
coins.find(
coin => coin.id === "bitcoin"
);

const eth =
coins.find(
coin => coin.id === "ethereum"
);

if (btc) {
document
.querySelectorAll(
'[data-price="bitcoin"]'
)
.forEach(
element => {
element.textContent =
money(
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
element => {
element.textContent =
money(
eth.current_price
);
}
);
}

const changes =
coins
.map(
coin =>
Number(
coin.price_change_percentage_24h
)
)
.filter(
Number.isFinite
);

if (!changes.length) {
return;
}

const average =
changes.reduce(
(a, b) => a + b,
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
element => {
element.textContent =
score;
}
);

const stateElement =
document.querySelector(
".pulse-info strong"
);

if (stateElement) {

if (score >= 65) {
  stateElement.textContent =
    "Bullish";

  stateElement.className =
    "positive-text";

} else if (score <= 35) {

  stateElement.textContent =
    "Bearish";

  stateElement.className =
    "negative-text";

} else {

  stateElement.textContent =
    "Neutral";

  stateElement.className =
    "warning-text";
}

}
}

function renderExternalMarkets(type) {
let assets = [];

if (type === "stocks") {
assets = STOCKS;
}

if (type === "indices") {
assets = INDICES;
}

if (type === "commodities") {
assets = COMMODITIES;
}

const grid = $("#coinGrid");

if (!grid) {
return;
}

grid.innerHTML = "";

assets.forEach(asset => {

const card =
  document.createElement(
    "article"
  );

card.className =
  "coin-card";

card.innerHTML = `

  <div class="coin-card-top">

    <div class="coin-identity">

      <div
        class="logo-mark"
        style="
          width:34px;
          height:34px;
          border-radius:50%;
        "
      >
        ${escapeHTML(
          asset.symbol.slice(0, 2)
        )}
      </div>

      <div>

        <strong>
          ${escapeHTML(
            asset.name
          )}
        </strong>

        <span>
          ${escapeHTML(
            asset.symbol
          )}
        </span>

      </div>

    </div>

  </div>

  <div class="coin-price">

    <strong>
      TradingView
    </strong>

    <span class="positive-text">
      LIVE
    </span>

  </div>

  <div class="coin-card-bottom">

    <span>
      Market
    </span>

    <strong>
      ${escapeHTML(
        asset.type
      )}
    </strong>

  </div>
`;

grid.appendChild(card);

card.addEventListener(
  "click",
  () => {

    state.selected =
      asset;

    const name =
      $(".selected-asset > strong");

    const symbol =
      $(".selected-asset > span");

    if (name) {
      name.textContent =
        asset.name;
    }

    if (symbol) {
      symbol.textContent =
        asset.symbol;
    }

    loadTradingView(
      asset.tv
    );
  }
);

});
}

function loadTradingView(symbol) {
const container =
$("#tradingview-widget");

if (!container) {
return;
}

container.innerHTML = "";

const wrapper =
document.createElement(
"div"
);

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

const script =
document.createElement(
"script"
);

script.src =
"https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

script.async = true;

const active =
document.querySelector(
".time-button.active"
);

const interval =
active
? active.dataset.interval
: "60";

script.innerHTML =
JSON.stringify({
autosize: true,
symbol: symbol,
interval: interval,
timezone: "Etc/UTC",
theme: "dark",
style: "1",
locale: "en",
enable_publishing: false,
allow_symbol_change: true,
hide_top_toolbar: false,
hide_legend: false,
save_image: false,
studies: [
"RSI@tv-basicstudies",
"MACD@tv-basicstudies"
]
});

wrapper.appendChild(widget);
wrapper.appendChild(script);

container.appendChild(wrapper);
}

function setupMarketTabs() {
const tabs =
document.querySelectorAll(
"[data-market]"
);

tabs.forEach(tab => {

tab.addEventListener(
  "click",
  () => {

    tabs.forEach(
      item =>
        item.classList.remove(
          "active"
        )
    );

    tab.classList.add(
      "active"
    );

    const type =
      tab.dataset.market;

    state.marketType =
      type;

    if (type === "crypto") {
      renderCrypto(
        state.crypto
      );

      if (state.crypto[0]) {
        selectCrypto(
          state.crypto[0]
        );
      }

      return;
    }

    renderExternalMarkets(
      type
    );
  }
);

});
}

function setupSearch() {
const input =
document.querySelector(
".topbar-search input"
);

if (!input) {
return;
}

input.addEventListener(
"input",
() => {

  const query =
    input.value
      .trim()
      .toLowerCase();

  if (
    state.marketType !==
    "crypto"
  ) {
    return;
  }

  const filtered =
    state.crypto.filter(
      coin =>
        coin.name
          .toLowerCase()
          .includes(query) ||
        coin.symbol
          .toLowerCase()
          .includes(query)
    );

  renderCrypto(
    query
      ? filtered
      : state.crypto
  );
}

);
}

function setupScanner() {
const button =
$("#runScanner");

if (!button) {
return;
}

button.addEventListener(
"click",
() => {

  const result =
    document.querySelector(
      ".scanner-results"
    );

  if (!result) {
    return;
  }

  const sorted =
    [...state.crypto].sort(
      (a, b) =>
        (Number(
          b.price_change_percentage_24h
        ) || 0) -
        (Number(
          a.price_change_percentage_24h
        ) || 0)
    );

  result.innerHTML = "";

  sorted
    .slice(0, 10)
    .forEach(coin => {

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

        <strong class="${
          change >= 0
            ? "positive-text"
            : "negative-text"
        }">
          ${percent(change)}
        </strong>
      `;

      result.appendChild(
        row
      );
    });
}

);
}

function setupNavigation() {
document
.querySelectorAll(
'.nav-item[href^="#"]'
)
.forEach(link => {

  link.addEventListener(
    "click",
    () => {

      document
        .querySelectorAll(
          ".nav-item"
        )
        .forEach(
          item =>
            item.classList.remove(
              "active"
            )
        );

      link.classList.add(
        "active"
      );

      const sidebar =
        $(".sidebar");

      if (sidebar) {
        sidebar.classList.remove(
          "open"
        );
      }
    }
  );
});

}

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
.forEach(button => {

  button.addEventListener(
    "click",
    () => {

      document
        .querySelectorAll(
          ".time-button"
        )
        .forEach(
          item =>
            item.classList.remove(
              "active"
            )
        );

      button.classList.add(
        "active"
      );

      if (
        state.selected &&
        state.selected.symbol
      ) {

        if (
          state.selected.tv
        ) {

          loadTradingView(
            state.selected.tv
          );

        } else {

          loadTradingView(
            "BINANCE:" +
            state.selected.symbol
              .toUpperCase() +
            "USDT"
          );
        }
      }
    }
  );
});

}

function createMarketTabs() {
const section =
document.getElementById(
"markets"
);

if (!section) {
return;
}

if (
document.querySelector(
".market-tabs"
)
) {
return;
}

const tabs =
document.createElement(
"div"
);

tabs.className =
"market-tabs";

tabs.style.display =
"flex";

tabs.style.flexWrap =
"wrap";

tabs.style.gap =
"7px";

tabs.style.marginBottom =
"16px";

tabs.innerHTML = `
<button
class="time-button active"
data-market="crypto"
type="button"
>
Crypto
</button>

<button
  class="time-button"
  data-market="stocks"
  type="button"
>
  Stocks
</button>

<button
  class="time-button"
  data-market="indices"
  type="button"
>
  Indices
</button>

<button
  class="time-button"
  data-market="commodities"
  type="button"
>
  Commodities
</button>

`;

const grid =
$("#coinGrid");

section.insertBefore(
tabs,
grid
);

setupMarketTabs();
}

function createMemeRadar() {
const section =
document.getElementById(
"meme-radar"
);

if (!section) {
return;
}

const body =
section.querySelector(
".card-body"
);

if (!body) {
return;
}

const wrapper =
document.createElement(
"div"
);

wrapper.style.marginTop =
"20px";

wrapper.innerHTML = `
<h3
style="
margin:0 0 12px;
font-size:14px;
"
>
Live Meme Watchlist
</h3>

<div
  id="memeRadarList"
  class="scanner-results"
>
  Loading meme coins...
</div>

`;

body.appendChild(
wrapper
);

loadMemeRadar();
}

async function loadMemeRadar() {
const container =
document.getElementById(
"memeRadarList"
);

if (!container) {
return;
}

try {

const ids =
  MEME_IDS.join(",");

const url =
  COINGECKO_API +
  "?vs_currency=usd" +
  "&ids=" +
  ids +
  "&order=market_cap_desc" +
  "&per_page=50" +
  "&page=1" +
  "&sparkline=false" +
  "&price_change_percentage=24h";

const memes =
  await fetchJSON(url);

container.innerHTML = "";

memes.forEach(
  coin => {

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

      <strong class="${
        change >= 0
          ? "positive-text"
          : "negative-text"
      }">
        ${percent(change)}
      </strong>
    `;

    container.appendChild(
      row
    );
  }
);

} catch (error) {

console.error(
  "Meme Radar error:",
  error
);

container.innerHTML =
  '<div class="scanner-empty">' +
  "Meme Radar data temporarily unavailable." +
  "</div>";

}
}

function init() {
createMarketTabs();
createMemeRadar();

setupSearch();
setupScanner();
setupMobileMenu();
setupNavigation();
setupTimeButtons();

loadCrypto();

setInterval(
loadCrypto,
60000
);
}

document.addEventListener(
"DOMContentLoaded",
init
);
