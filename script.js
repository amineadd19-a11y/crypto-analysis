const API_URL =
"https://api.coingecko.com/api/v3/coins/markets";

const state = {
coins: [],
currency: "usd"
};

function money(value) {
const number = Number(value);

if (!Number.isFinite(number)) {
return "--";
}

if (number >= 1000) {
return (
"$" +
number.toLocaleString("en-US", {
maximumFractionDigits: 0
})
);
}

if (number >= 1) {
return (
"$" +
number.toLocaleString("en-US", {
minimumFractionDigits: 2,
maximumFractionDigits: 2
})
);
}

return (
"$" +
number.toLocaleString("en-US", {
minimumFractionDigits: 4,
maximumFractionDigits: 8
})
);
}

function percent(value) {
const number = Number(value);

if (!Number.isFinite(number)) {
return "--";
}

const sign = number >= 0 ? "+" : "";

return sign + number.toFixed(2) + "%";
}

function largeNumber(value) {
const number = Number(value);

if (!Number.isFinite(number)) {
return "--";
}

if (number >= 1000000000000) {
return "$" + (number / 1000000000000).toFixed(2) + "T";
}

if (number >= 1000000000) {
return "$" + (number / 1000000000).toFixed(2) + "B";
}

if (number >= 1000000) {
return "$" + (number / 1000000).toFixed(2) + "M";
}

return "$" + number.toLocaleString("en-US");
}

function showMessage(message) {
const grid = document.getElementById("coinGrid");

if (!grid) {
return;
}

grid.innerHTML =
'<div class="loading-card">' +
message +
"</div>";
}

async function getMarketData() {
const url =
API_URL +
"?vs_currency=" +
state.currency +
"&order=market_cap_desc" +
"&per_page=20" +
"&page=1" +
"&sparkline=false" +
"&price_change_percentage=24h";

const response = await fetch(url);

if (!response.ok) {
throw new Error(
"CoinGecko API error: " + response.status
);
}

return await response.json();
}

function renderCoins(coins) {
const grid = document.getElementById("coinGrid");

if (!grid) {
return;
}

if (!Array.isArray(coins) || coins.length === 0) {
showMessage("No market data available.");
return;
}

grid.innerHTML = "";

coins.forEach(function (coin) {
const change =
Number(coin.price_change_percentage_24h) || 0;

const card = document.createElement("article");

card.className = "coin-card";

card.innerHTML =
  '<div class="coin-card-top">' +
    '<div class="coin-identity">' +

      '<img ' +
        'class="coin-logo" ' +
        'src="' + coin.image + '" ' +
        'alt="' + coin.name + '"' +
      '>' +

      '<div>' +
        '<strong>' +
          coin.name +
        '</strong>' +

        '<span>' +
          coin.symbol.toUpperCase() +
        '</span>' +
      '</div>' +

    '</div>' +

    '<button ' +
      'class="star-button" ' +
      'type="button"' +
    '>' +
      "☆" +
    "</button>" +

  "</div>" +

  '<div class="coin-price">' +

    "<strong>" +
      money(coin.current_price) +
    "</strong>" +

    '<span class="' +
      (change >= 0
        ? "positive-text"
        : "negative-text") +
    '">' +
      percent(change) +
    "</span>" +

  "</div>" +

  '<div class="coin-card-bottom">' +

    "<span>" +
      "Market Cap" +
    "</span>" +

    "<strong>" +
      largeNumber(coin.market_cap) +
    "</strong>" +

  "</div>";

grid.appendChild(card);

card.addEventListener("click", function () {
  selectCoin(coin);
});

});
}

function updateMainPrices(coins) {
const bitcoin = coins.find(function (coin) {
return coin.id === "bitcoin";
});

const ethereum = coins.find(function (coin) {
return coin.id === "ethereum";
});

if (bitcoin) {
document
.querySelectorAll('[data-price="bitcoin"]')
.forEach(function (element) {
element.textContent =
money(bitcoin.current_price);
});
}

if (ethereum) {
document
.querySelectorAll('[data-price="ethereum"]')
.forEach(function (element) {
element.textContent =
money(ethereum.current_price);
});
}
}

function updateMarketScore(coins) {
const changes = coins
.map(function (coin) {
return Number(
coin.price_change_percentage_24h
);
})
.filter(function (value) {
return Number.isFinite(value);
});

if (!changes.length) {
return;
}

const average =
changes.reduce(function (total, value) {
return total + value;
}, 0) / changes.length;

let score =
Math.round(50 + average * 5);

score = Math.max(
0,
Math.min(100, score)
);

const marketScore =
document.getElementById("marketScore");

if (marketScore) {
marketScore.textContent = score;
}

document
.querySelectorAll(".score-small")
.forEach(function (element) {
element.textContent = score;
});
}

function selectCoin(coin) {
const name =
document.querySelector(
".selected-asset > strong"
);

const symbol =
document.querySelector(
".selected-asset > span"
);

const price =
document.querySelector(
".chart-price strong"
);

const change =
document.querySelector(
".chart-price span"
);

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

updateIndicators(coin);
loadTradingView(coin.symbol);
}

function updateIndicators(coin) {
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
percent(
coin.price_change_percentage_24h
);
}

if (rows[2]) {
rows[2].textContent =
largeNumber(coin.total_volume);
}

if (rows[3]) {
rows[3].textContent =
"Analyzing";
}

if (rows[4]) {
rows[4].textContent =
percent(
coin.price_change_percentage_24h
);
}
}

function loadTradingView(symbol) {
const container =
document.getElementById(
"tradingview-widget"
);

if (!container) {
return;
}

container.innerHTML = "";

const wrapper =
document.createElement("div");

wrapper.className =
"tradingview-widget-container";

wrapper.style.width = "100%";
wrapper.style.height = "100%";

const widget =
document.createElement("div");

widget.className =
"tradingview-widget-container__widget";

widget.style.width = "100%";
widget.style.height = "100%";

const script =
document.createElement("script");

script.src =
"https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

script.async = true;

script.innerHTML = JSON.stringify({
autosize: true,
symbol:
"BINANCE:" +
symbol.toUpperCase() +
"USDT",
interval: "60",
timezone: "Etc/UTC",
theme: "dark",
style: "1",
locale: "en",
enable_publishing: false,
allow_symbol_change: true,
hide_top_toolbar: false,
hide_legend: false,
save_image: false
});

wrapper.appendChild(widget);
wrapper.appendChild(script);

container.appendChild(wrapper);
}

async function loadMarket() {
showMessage(
"Loading live cryptocurrency prices..."
);

try {
const coins =
await getMarketData();

state.coins = coins;

renderCoins(coins);

updateMainPrices(coins);

updateMarketScore(coins);

if (coins.length > 0) {
  selectCoin(coins[0]);
}

} catch (error) {
console.error(error);

showMessage(
  "Unable to load market data. Please refresh the page."
);

}
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
function () {

  const query =
    input.value
      .trim()
      .toLowerCase();

  if (!query) {
    renderCoins(state.coins);
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

  renderCoins(filtered);
}

);
}

function setupScanner() {
const button =
document.getElementById(
"runScanner"
);

if (!button) {
return;
}

button.addEventListener(
"click",
function () {

  const container =
    document.querySelector(
      ".scanner-results"
    );

  if (!container) {
    return;
  }

  if (!state.coins.length) {
    container.innerHTML =
      '<div class="scanner-empty">' +
      "Market data is still loading." +
      "</div>";

    return;
  }

  const sorted =
    [...state.coins].sort(
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

  container.innerHTML = "";

  sorted
    .slice(0, 5)
    .forEach(function (coin) {

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

      row.innerHTML =
        '<div class="mini-opportunity-coin">' +

          '<img ' +
            'src="' +
            coin.image +
            '" ' +
            'width="34" ' +
            'height="34" ' +
            'alt=""' +
          ">" +

          "<div>" +

            "<strong>" +
              coin.name +
            "</strong>" +

            "<small>" +
              coin.symbol.toUpperCase() +
            "</small>" +

          "</div>" +

        "</div>" +

        '<strong class="' +
          (
            change >= 0
              ? "positive-text"
              : "negative-text"
          ) +
        '">' +

          percent(change) +

        "</strong>";

      container.appendChild(row);
    });
}

);
}

function setupMobileMenu() {
const button =
document.querySelector(
".mobile-menu"
);

const sidebar =
document.querySelector(
".sidebar"
);

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

function setupNavigation() {
document
.querySelectorAll(
'.nav-item[href^="#"]'
)
.forEach(function (link) {

  link.addEventListener(
    "click",
    function () {

      document
        .querySelectorAll(
          ".nav-item"
        )
        .forEach(function (item) {
          item.classList.remove(
            "active"
          );
        });

      link.classList.add(
        "active"
      );

      const sidebar =
        document.querySelector(
          ".sidebar"
        );

      if (sidebar) {
        sidebar.classList.remove(
          "open"
        );
      }
    }
  );

});

}

function setupTimeButtons() {
document
.querySelectorAll(
".time-button"
)
.forEach(function (button) {

  button.addEventListener(
    "click",
    function () {

      document
        .querySelectorAll(
          ".time-button"
        )
        .forEach(function (item) {
          item.classList.remove(
            "active"
          );
        });

      button.classList.add(
        "active"
      );

      const current =
        state.coins[0];

      if (current) {
        loadTradingView(
          current.symbol
        );
      }

    }
  );

});

}

document.addEventListener(
"DOMContentLoaded",
function () {

setupSearch();

setupScanner();

setupMobileMenu();

setupNavigation();

setupTimeButtons();

loadMarket();

setInterval(
  loadMarket,
  60000
);

}
);
