const API = "https://api.coingecko.com/api/v3";

const state = {
  coins: [],
  favorites: JSON.parse(localStorage.getItem("cv_favorites") || "[]"),
  selected: "bitcoin"
};

const $ = (s) => document.querySelector(s);

function money(n) {
  if (n == null) return "--";

  if (n >= 1000)
    return "$" + n.toLocaleString("en-US", {
      maximumFractionDigits: 0
    });

  if (n >= 1)
    return "$" + n.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });

  return "$" + n.toLocaleString("en-US", {
    minimumFractionDigits: 4,
    maximumFractionDigits: 8
  });
}

function percent(n) {
  if (n == null) return "--";

  return `${n >= 0 ? "+" : ""}${Number(n).toFixed(2)}%`;
}

function largeNumber(n) {
  if (!n) return "--";

  if (n >= 1e12)
    return "$" + (n / 1e12).toFixed(2) + "T";

  if (n >= 1e9)
    return "$" + (n / 1e9).toFixed(2) + "B";

  if (n >= 1e6)
    return "$" + (n / 1e6).toFixed(2) + "M";

  return "$" + Number(n).toLocaleString();
}


/* =========================
   LOAD MARKET
========================= */

async function loadMarket() {

  try {

    const url =
      `${API}/coins/markets` +
      `?vs_currency=usd` +
      `&order=market_cap_desc` +
      `&per_page=20` +
      `&page=1` +
      `&sparkline=true` +
      `&price_change_percentage=24h,7d`;

    const response = await fetch(url);

    if (!response.ok) {
      throw new Error("CoinGecko error " + response.status);
    }

    state.coins = await response.json();

    renderCoins();
    updateTicker();
    updatePrices();

    if (state.coins.length) {
      selectCoin(state.coins[0].id);
    }

  } catch (error) {

    console.error("CryptoVision:", error);

    showError();
  }
}


/* =========================
   COINS
========================= */

function renderCoins() {

  const grid = $("#coinGrid");

  if (!grid) return;

  grid.innerHTML = "";

  state.coins.slice(0, 8).forEach(coin => {

    const change =
      coin.price_change_percentage_24h || 0;

    const positive = change >= 0;

    const card =
      document.createElement("article");

    card.className = "coin-card";

    card.dataset.coin = coin.id;

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
          class="star-button"
          data-id="${coin.id}"
        >
          ${state.favorites.includes(coin.id) ? "★" : "☆"}
        </button>

      </div>


      <div class="coin-price">

        <strong>
          ${money(coin.current_price)}
        </strong>

        <span class="${
          positive
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

      <div class="mini-chart"></div>

    `;

    grid.appendChild(card);


    card.addEventListener(
      "click",
      () => selectCoin(coin.id)
    );


    const star =
      card.querySelector(".star-button");

    star.addEventListener(
      "click",
      event => {

        event.stopPropagation();

        toggleFavorite(coin.id);
      }
    );

  });
}


/* =========================
   TICKER
========================= */

function updateTicker() {

  const ticker =
    $("#tickerItems") ||
    $(".ticker-items");

  if (!ticker) return;

  ticker.innerHTML = "";

  state.coins.slice(0, 10).forEach(coin => {

    const change =
      coin.price_change_percentage_24h || 0;

    const item =
      document.createElement("div");

    item.className = "ticker-item";

    item.innerHTML = `

      <span>
        ${coin.symbol.toUpperCase()}
      </span>

      <strong class="${
        change >= 0
          ? "positive-text"
          : "negative-text"
      }">

        ${percent(change)}

      </strong>

    `;

    ticker.appendChild(item);
  });
}


/* =========================
   BTC / ETH
========================= */

function updatePrices() {

  const btc =
    state.coins.find(
      c => c.id === "bitcoin"
    );

  const eth =
    state.coins.find(
      c => c.id === "ethereum"
    );


  if (btc) {

    document
      .querySelectorAll(
        "[data-price='bitcoin']"
      )
      .forEach(el => {

        el.textContent =
          money(btc.current_price);

      });
  }


  if (eth) {

    document
      .querySelectorAll(
        "[data-price='ethereum']"
      )
      .forEach(el => {

        el.textContent =
          money(eth.current_price);

      });
  }
}


/* =========================
   SELECT COIN
========================= */

function selectCoin(id) {

  const coin =
    state.coins.find(
      c => c.id === id
    );

  if (!coin) return;

  state.selected = id;

  const name =
    document.querySelector(
      ".selected-asset strong"
    );

  const symbol =
    document.querySelector(
      ".selected-asset span"
    );

  const price =
    document.querySelector(
      ".chart-price strong"
    );

  const changeElement =
    document.querySelector(
      ".chart-price span"
    );


  if (name)
    name.textContent = coin.name;


  if (symbol)
    symbol.textContent =
      coin.symbol.toUpperCase();


  if (price)
    price.textContent =
      money(coin.current_price);


  if (changeElement) {

    const change =
      coin.price_change_percentage_24h || 0;

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


/* =========================
   COIN DETAILS
========================= */

async function loadCoinDetails(id) {

  try {

    const response =
      await fetch(
        `${API}/coins/${id}?localization=false&tickers=false&market_data=true`
      );

    if (!response.ok) return;

    const data =
      await response.json();

    updateAnalysis(data);

  } catch (error) {

    console.error(error);

  }
}


/* =========================
   ANALYSIS
========================= */

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

    const el =
      rows[0].querySelector("strong");

    if (el)
      el.textContent =
        money(price);
  }


  if (rows[1]) {

    const el =
      rows[1].querySelector("strong");

    if (el)
      el.textContent =
        percent(change);
  }


  if (rows[2]) {

    const el =
      rows[2].querySelector("strong");

    if (el)
      el.textContent =
        largeNumber(volume);
  }


  const score =
    Math.max(
      0,
      Math.min(
        100,
        Math.round(50 + change * 4)
      )
    );


  const scoreElement =
    document.querySelector(
      ".score-small"
    );

  if (scoreElement)
    scoreElement.textContent =
      score;


  const marketScore =
    document.querySelector(
      "#marketScore"
    );

  if (marketScore)
    marketScore.textContent =
      score;


  updatePrediction(data);
}


/* =========================
   PREDICTION
========================= */

function updatePrediction(data) {

  const market =
    data.market_data;

  if (!market) return;


  const price =
    market.current_price?.usd || 0;

  const day =
    market.price_change_percentage_24h || 0;

  const week =
    market.price_change_percentage_7d || day;


  const momentum =
    day * 0.4 + week * 0.6;


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
      (el, index) => {

        if (predictions[index] != null) {

          el.textContent =
            money(predictions[index]);

        }

      }
    );
}


/* =========================
   TRADINGVIEW
========================= */

function loadTradingView(symbol) {

  const container =
    $("#tradingview-widget");

  if (!container) return;


  container.innerHTML = `

    <div
      class="tradingview-widget-container__widget"
      style="height:100%;width:100%"
    ></div>

  `;


  const script =
    document.createElement("script");

  script.src =
    "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

  script.async = true;


  script.innerHTML =
    JSON.stringify({

      autosize: true,

      symbol:
        `BINANCE:${symbol}USDT`,

      interval: "60",

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


  container.appendChild(script);
}


/* =========================
   FAVORITES
========================= */

function toggleFavorite(id) {

  if (
    state.favorites.includes(id)
  ) {

    state.favorites =
      state.favorites.filter(
        x => x !== id
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


  renderCoins();
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
    () => {

      const query =
        input.value
          .trim()
          .toLowerCase();


      if (!query) {

        renderCoins();

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


      renderFiltered(filtered);

    }
  );
}


function renderFiltered(coins) {

  const grid =
    $("#coinGrid");

  if (!grid) return;


  grid.innerHTML = "";


  coins.forEach(coin => {

    const card =
      document.createElement(
        "article"
      );

    card.className =
      "coin-card";


    const change =
      coin.price_change_percentage_24h || 0;


    card.innerHTML = `

      <div class="coin-card-top">

        <div class="coin-identity">

          <img
            class="coin-logo"
            src="${coin.image}"
            alt="${coin.name}"
          >

          <div>

            <strong>
              ${coin.name}
            </strong>

            <span>
              ${coin.symbol.toUpperCase()}
            </span>

          </div>

        </div>

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

    `;


    card.addEventListener(
      "click",
      () => selectCoin(coin.id)
    );


    grid.appendChild(card);

  });
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
    () => {

      const result =
        document.querySelector(
          ".scanner-results"
        );

      if (!result) return;


      const coins =
        [...state.coins]
          .sort(
            (a, b) =>
              (b.price_change_percentage_24h || 0)
              -
              (a.price_change_percentage_24h || 0)
          )
          .slice(0, 5);


      result.innerHTML = "";


      coins.forEach(coin => {

        const div =
          document.createElement(
            "div"
          );

        div.className =
          "mini-opportunity";


        div.innerHTML = `

          <div
            class="mini-opportunity-coin"
          >

            <img
              src="${coin.image}"
              width="34"
              height="34"
              style="border-radius:50%"
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


          <strong
            class="${
              coin.price_change_percentage_24h >= 0
                ? "positive-text"
                : "negative-text"
            }"
          >

            ${percent(
              coin.price_change_percentage_24h
            )}

          </strong>

        `;


        result.appendChild(div);

      });

    }
  );
}


/* =========================
   ERROR
========================= */

function showError() {

  const grid =
    $("#coinGrid");

  if (grid) {

    grid.innerHTML = `

      <div
        class="loading-card"
        style="color:#ff6477"
      >

        ⚠ Unable to load market data.

        <br><br>

        Please refresh the page.

      </div>

    `;
  }
}


/* =========================
   AUTO REFRESH
========================= */

function startRefresh() {

  setInterval(
    loadMarket,
    60000
  );
}


/* =========================
   INIT
========================= */

document.addEventListener(
  "DOMContentLoaded",
  () => {

    setupSearch();

    setupScanner();

    loadMarket();

    startRefresh();

    console.log(
      "CryptoVision initialized"
    );

  }
);
