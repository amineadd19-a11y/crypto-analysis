const API =
  "https://api.coingecko.com/api/v3/coins/markets" +
  "?vs_currency=usd&order=market_cap_desc&per_page=100&page=1" +
  "&sparkline=false&price_change_percentage=24h";

let allCoins = [];
let selectedCoin = null;

const $ = (id) => document.getElementById(id);

async function loadMarket() {
  try {
    const response = await fetch(API);

    if (!response.ok) {
      throw new Error("CoinGecko API error");
    }

    const coins = await response.json();

    allCoins = coins;

    renderMarket();
    updateBitcoin(coins);
    updateMarketAnalysis(coins);
    renderTrending(coins);

    $("updated").textContent =
      "Updated: " + new Date().toLocaleTimeString();

  } catch (error) {

    console.error(error);

    $("coins").innerHTML = `
      <div class="loading-card">
        Market data is temporarily unavailable.
        Please try again shortly.
      </div>
    `;

    $("updated").textContent =
      "Unable to update market data";
  }
}


/* =========================
   MARKET
========================= */

function renderMarket() {

  const search = $("coinSearch");
  const sort = $("coinSort");

  let coins = [...allCoins];

  const query =
    search?.value.trim().toLowerCase() || "";

  if (query) {

    coins = coins.filter(coin =>
      coin.name.toLowerCase().includes(query) ||
      coin.symbol.toLowerCase().includes(query)
    );

  }

  switch (sort?.value) {

    case "price":
      coins.sort(
        (a, b) =>
          (b.current_price || 0) -
          (a.current_price || 0)
      );
      break;

    case "change":
      coins.sort(
        (a, b) =>
          (b.price_change_percentage_24h || 0) -
          (a.price_change_percentage_24h || 0)
      );
      break;

    case "volume":
      coins.sort(
        (a, b) =>
          (b.total_volume || 0) -
          (a.total_volume || 0)
      );
      break;

    case "marketcap":
      coins.sort(
        (a, b) =>
          (b.market_cap || 0) -
          (a.market_cap || 0)
      );
      break;

    default:
      coins.sort(
        (a, b) =>
          (a.market_cap_rank || 9999) -
          (b.market_cap_rank || 9999)
      );
  }

  displayCoins(coins);
}


function displayCoins(coins) {

  const container = $("coins");

  if (!coins.length) {

    container.innerHTML = `
      <div class="loading-card">
        No cryptocurrency found.
      </div>
    `;

    return;
  }

  container.innerHTML = "";

  coins.slice(0, 100).forEach(coin => {

    const change =
      coin.price_change_percentage_24h || 0;

    const changeClass =
      change >= 0 ? "positive" : "negative";

    const sign =
      change >= 0 ? "+" : "";

    const card =
      document.createElement("div");

    card.className = "coin";

    card.innerHTML = `

      <div class="coin-top">

        <div>

          <div class="coin-name">
            ${escapeHTML(coin.name)}
          </div>

          <div class="coin-symbol">
            ${coin.symbol.toUpperCase()}
          </div>

        </div>

        <div>
          #${coin.market_cap_rank || "-"}
        </div>

      </div>

      <div class="coin-price">
        $${formatPrice(coin.current_price)}
      </div>

      <div class="${changeClass}">
        ${sign}${change.toFixed(2)}% 24h
      </div>

      <div class="coin-meta">

        <span>
          Market Cap:
          ${formatCompact(coin.market_cap)}
        </span>

        <span>
          Volume:
          ${formatCompact(coin.total_volume)}
        </span>

      </div>
    `;

    card.addEventListener(
      "click",
      () => showCoinDetails(coin)
    );

    container.appendChild(card);

  });
}


/* =========================
   BITCOIN
========================= */

function updateBitcoin(coins) {

  const btc = coins.find(
    coin =>
      coin.symbol.toLowerCase() === "btc"
  );

  if (!btc) return;

  $("btcPrice").textContent =
    "$" + formatPrice(btc.current_price);

  const change =
    btc.price_change_percentage_24h || 0;

  $("btcChange").textContent =
    `${change >= 0 ? "+" : ""}${change.toFixed(2)}% today`;

  $("btcChange").className =
    "hero-change " +
    (change >= 0 ? "positive" : "negative");
}


/* =========================
   MARKET ANALYSIS
========================= */

function updateMarketAnalysis(coins) {

  if (!coins.length) return;

  const changes =
    coins.map(
      coin =>
        coin.price_change_percentage_24h || 0
    );

  const average =
    changes.reduce(
      (sum, value) => sum + value,
      0
    ) / changes.length;

  let momentum =
    50 + average * 10;

  momentum =
    Math.max(
      5,
      Math.min(95, momentum)
    );

  $("momentumBar").style.width =
    momentum + "%";

  $("momentumValue").textContent =
    Math.round(momentum) + "/100";

  let trend;

  if (average > 2) {

    trend = "Bullish";

    $("momentumText").textContent =
      "Strong positive market momentum.";

    $("marketTrendText").textContent =
      "Major cryptocurrencies are showing strong positive movement.";

  } else if (average > 0.5) {

    trend = "Positive";

    $("momentumText").textContent =
      "Positive market momentum.";

    $("marketTrendText").textContent =
      "The market is currently showing a positive bias.";

  } else if (average < -2) {

    trend = "Bearish";

    $("momentumText").textContent =
      "Strong negative market momentum.";

    $("marketTrendText").textContent =
      "The market is experiencing strong selling pressure.";

  } else if (average < -0.5) {

    trend = "Negative";

    $("momentumText").textContent =
      "Negative market momentum.";

    $("marketTrendText").textContent =
      "The market currently shows a negative bias.";

  } else {

    trend = "Neutral";

    $("momentumText").textContent =
      "Market momentum is currently neutral.";

    $("marketTrendText").textContent =
      "The market is moving without a strong directional signal.";
  }

  $("marketTrend").textContent =
    trend;

  const shortValue =
    Math.max(
      -20,
      Math.min(30, average * 4)
    );

  const mediumValue =
    Math.max(
      -40,
      Math.min(80, average * 10)
    );

  $("shortTerm").textContent =
    formatScenario(shortValue);

  $("mediumTerm").textContent =
    formatScenario(mediumValue);
}


/* =========================
   TRENDING
========================= */

function renderTrending(coins) {

  const container =
    $("trendingCoins");

  const trending =
    [...coins]
      .sort(
        (a, b) =>
          (b.price_change_percentage_24h || 0) -
          (a.price_change_percentage_24h || 0)
      )
      .slice(0, 4);

  container.innerHTML = "";

  trending.forEach(coin => {

    const change =
      coin.price_change_percentage_24h || 0;

    const card =
      document.createElement("div");

    card.className =
      "trending-card";

    card.innerHTML = `

      <h3>
        ${escapeHTML(coin.name)}
      </h3>

      <p>
        ${coin.symbol.toUpperCase()}
      </p>

      <strong class="${
        change >= 0
          ? "positive"
          : "negative"
      }">
        ${change >= 0 ? "+" : ""}
        ${change.toFixed(2)}%
      </strong>

      <p>
        Current price:
        $${formatPrice(coin.current_price)}
      </p>

    `;

    card.addEventListener(
      "click",
      () => showCoinDetails(coin)
    );

    container.appendChild(card);

  });
}


/* =========================
   COIN DETAILS
========================= */

function showCoinDetails(coin) {

  selectedCoin = coin;

  $("coinDetails")
    .classList.remove("hidden");

  $("selectedCoinName").textContent =
    coin.name;

  $("selectedCoinSymbol").textContent =
    coin.symbol.toUpperCase();

  $("detailPrice").textContent =
    "$" + formatPrice(coin.current_price);

  const change =
    coin.price_change_percentage_24h || 0;

  $("detailChange").textContent =
    `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`;

  $("detailChange").className =
    change >= 0
      ? "positive"
      : "negative";

  $("detailMarketCap").textContent =
    formatCompact(coin.market_cap);

  $("detailVolume").textContent =
    formatCompact(coin.total_volume);

  calculateCoinScore(coin);

  generatePredictions(coin);

  generateChartPlaceholder(coin);

  $("coinDetails").scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}


/* =========================
   COIN SCORE
========================= */

function calculateCoinScore(coin) {

  const change =
    coin.price_change_percentage_24h || 0;

  const volume =
    coin.total_volume || 0;

  const marketCap =
    coin.market_cap || 0;

  let score = 50;

  score += change * 5;

  if (volume > marketCap * 0.1) {
    score += 10;
  }

  if (change > 5) {
    score += 8;
  }

  if (change < -5) {
    score -= 8;
  }

  score =
    Math.round(
      Math.max(
        0,
        Math.min(100, score)
      )
    );

  $("coinScore").textContent =
    score;

  let signal;
  let explanation;

  if (score >= 70) {

    signal = "Bullish";

    explanation =
      "Current market data shows positive momentum. Price movement and trading activity are supporting a stronger short-term trend.";

  } else if (score >= 45) {

    signal = "Neutral";

    explanation =
      "Current market conditions are mixed. There is no strong directional signal at the moment.";

  } else {

    signal = "Bearish";

    explanation =
      "Current market data shows weaker momentum and increased downside pressure.";
  }

  $("coinSignal").textContent =
    signal;

  $("coinSignal").className =
    signal === "Bullish"
      ? "positive"
      : signal === "Bearish"
        ? "negative"
        : "";

  $("coinExplanation").textContent =
    explanation;
}


/* =========================
   PREDICTIONS
========================= */

function generatePredictions(coin) {

  const change =
    coin.price_change_percentage_24h || 0;

  const short =
    Math.max(
      -20,
      Math.min(30, change * 2)
    );

  const medium =
    Math.max(
      -35,
      Math.min(60, change * 5)
    );

  const long =
    Math.max(
      -50,
      Math.min(100, change * 8)
    );

  $("shortPrediction").textContent =
    formatScenario(short);

  $("mediumPrediction").textContent =
    formatScenario(medium);

  $("longPrediction").textContent =
    formatScenario(long);
}


/* =========================
   CHART
========================= */

function generateChartPlaceholder(coin) {

  const chart =
    $("coinChart");

  chart.innerHTML = `
    <div>
      📈

      <br>

      <strong>
        ${escapeHTML(coin.name)}
      </strong>

      <br>

      Historical price chart will be connected
      to live market history in the next update.
    </div>
  `;
}


/* =========================
   EVENTS
========================= */

$("coinSearch")?.addEventListener(
  "input",
  renderMarket
);

$("coinSort")?.addEventListener(
  "change",
  renderMarket
);

$("refreshBtn")?.addEventListener(
  "click",
  loadMarket
);

$("closeDetails")?.addEventListener(
  "click",
  () => {

    $("coinDetails")
      .classList.add("hidden");

  }
);


/* =========================
   HELPERS
========================= */

function formatPrice(price) {

  if (price === null || price === undefined) {
    return "—";
  }

  if (price >= 1000) {

    return price.toLocaleString(
      "en-US",
      {
        maximumFractionDigits: 2
      }
    );

  }

  if (price >= 1) {

    return price.toLocaleString(
      "en-US",
      {
        maximumFractionDigits: 4
      }
    );

  }

  return price.toLocaleString(
    "en-US",
    {
      maximumFractionDigits: 8
    }
  );
}


function formatCompact(value) {

  if (!value) {
    return "—";
  }

  if (value >= 1e12) {
    return "$" +
      (value / 1e12).toFixed(2) +
      "T";
  }

  if (value >= 1e9) {
    return "$" +
      (value / 1e9).toFixed(2) +
      "B";
  }

  if (value >= 1e6) {
    return "$" +
      (value / 1e6).toFixed(2) +
      "M";
  }

  if (value >= 1e3) {
    return "$" +
      (value / 1e3).toFixed(2) +
      "K";
  }

  return "$" +
    value.toLocaleString();
}


function formatScenario(value) {

  return (
    value >= 0 ? "+" : ""
  ) + value.toFixed(1) + "%";
}


function escapeHTML(value) {

  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


/* =========================
   START
========================= */

loadMarket();
