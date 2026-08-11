"use strict";

const API_BASE = "https://api.coingecko.com/api/v3";

const state = {
  coins: [],
  selectedCoin: null,
  chartDays: 1,
  chartCache: new Map(),
  loading: false
};

const $ = (id) => document.getElementById(id);

const safeText = (value) =>
  String(value ?? "")
    .replace(/[&<>"']/g, (char) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    }[char]));

function formatPrice(value) {
  if (value == null || !Number.isFinite(Number(value))) return "—";

  const number = Number(value);

  if (number >= 1000) {
    return number.toLocaleString("en-US", {
      maximumFractionDigits: 2
    });
  }

  if (number >= 1) {
    return number.toLocaleString("en-US", {
      maximumFractionDigits: 4
    });
  }

  return number.toLocaleString("en-US", {
    maximumFractionDigits: 8
  });
}

function formatCompact(value) {
  if (value == null || !Number.isFinite(Number(value))) return "—";

  const number = Number(value);

  if (number >= 1e12) return "$" + (number / 1e12).toFixed(2) + "T";
  if (number >= 1e9) return "$" + (number / 1e9).toFixed(2) + "B";
  if (number >= 1e6) return "$" + (number / 1e6).toFixed(2) + "M";
  if (number >= 1e3) return "$" + (number / 1e3).toFixed(2) + "K";

  return "$" + number.toLocaleString("en-US");
}

function formatChange(value) {
  const number = Number(value) || 0;
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function setStatus(message, type = "") {
  const element = $("marketStatus");
  if (!element) return;

  element.textContent = message;
  element.className = "market-status";

  if (type) {
    element.classList.add(type);
  }
}


/* =========================
   MARKET API
========================= */

async function fetchMarket() {
  if (state.loading) return;

  state.loading = true;

  setStatus("Loading live cryptocurrency market...");

  try {
    const url =
      API_BASE +
      "/coins/markets" +
      "?vs_currency=usd" +
      "&order=market_cap_desc" +
      "&per_page=100" +
      "&page=1" +
      "&sparkline=false" +
      "&price_change_percentage=24h";

    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "application/json"
      },
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.status}`);
    }

    const data = await response.json();

    if (!Array.isArray(data)) {
      throw new Error("Invalid market response");
    }

    state.coins = data.filter(isValidCoin);

    renderMarket();
    updateBitcoin();
    updateMarketAnalysis();
    renderTrending();

    setStatus(
      `${state.coins.length} cryptocurrencies loaded successfully.`
    );

    $("updated").textContent =
      "Updated: " + new Date().toLocaleTimeString();

  } catch (error) {
    console.error("Market error:", error);

    setStatus(
      "Market data could not be loaded. Please try again.",
      "negative"
    );

    const container = $("coins");

    if (container) {
      container.innerHTML = `
        <div class="error-card">
          Unable to load live cryptocurrency data.
          Please wait a moment and press Refresh.
        </div>
      `;
    }

  } finally {
    state.loading = false;
  }
}


function isValidCoin(coin) {
  return Boolean(
    coin &&
    coin.id &&
    coin.name &&
    coin.symbol
  );
}


/* =========================
   MARKET RENDER
========================= */

function renderMarket() {
  const container = $("coins");

  if (!container) return;

  const query =
    ($("coinSearch")?.value || "")
      .trim()
      .toLowerCase();

  let coins = [...state.coins];

  if (query) {
    coins = coins.filter((coin) => {
      const name = String(coin.name).toLowerCase();
      const symbol = String(coin.symbol).toLowerCase();

      return (
        name.includes(query) ||
        symbol.includes(query)
      );
    });
  }

  const sort = $("coinSort")?.value || "rank";

  coins.sort((a, b) => {
    switch (sort) {
      case "price":
        return (b.current_price || 0) - (a.current_price || 0);

      case "change":
        return (
          (b.price_change_percentage_24h || 0) -
          (a.price_change_percentage_24h || 0)
        );

      case "volume":
        return (b.total_volume || 0) - (a.total_volume || 0);

      case "marketcap":
        return (b.market_cap || 0) - (a.market_cap || 0);

      default:
        return (
          (a.market_cap_rank || 99999) -
          (b.market_cap_rank || 99999)
        );
    }
  });

  if (!coins.length) {
    container.innerHTML = `
      <div class="loading-card">
        No cryptocurrency found.
      </div>
    `;
    return;
  }

  container.innerHTML = coins
    .slice(0, 100)
    .map(createCoinCard)
    .join("");

  container
    .querySelectorAll("[data-coin-id]")
    .forEach((card) => {
      card.addEventListener("click", () => {
        const coin = state.coins.find(
          (item) => item.id === card.dataset.coinId
        );

        if (coin) {
          showCoinDetails(coin);
        }
      });
    });
}


function createCoinCard(coin) {
  const change =
    Number(coin.price_change_percentage_24h) || 0;

  const changeClass =
    change >= 0 ? "positive" : "negative";

  const image =
    typeof coin.image === "string"
      ? coin.image
      : "";

  return `
    <article
      class="coin-card"
      data-coin-id="${safeText(coin.id)}"
      tabindex="0"
      role="button"
      aria-label="Open ${safeText(coin.name)} analysis"
    >

      <div class="coin-top">

        <div class="coin-identity">

          <img
            src="${safeText(image)}"
            alt="${safeText(coin.name)} logo"
            class="coin-image"
            loading="lazy"
            referrerpolicy="no-referrer"
          >

          <div>

            <div class="coin-name">
              ${safeText(coin.name)}
            </div>

            <div class="coin-symbol">
              ${safeText(coin.symbol).toUpperCase()}
            </div>

          </div>

        </div>

        <div class="coin-rank">
          #${coin.market_cap_rank || "—"}
        </div>

      </div>

      <div class="coin-price">
        $${formatPrice(coin.current_price)}
      </div>

      <div class="coin-change ${changeClass}">
        ${formatChange(change)}
      </div>

      <div class="coin-meta">

        <span>
          Market Cap ${formatCompact(coin.market_cap)}
        </span>

        <span>
          Volume ${formatCompact(coin.total_volume)}
        </span>

      </div>

    </article>
  `;
}


/* =========================
   BITCOIN
========================= */

function updateBitcoin() {
  const btc = state.coins.find(
    (coin) =>
      coin.id === "bitcoin" ||
      String(coin.symbol).toLowerCase() === "btc"
  );

  if (!btc) return;

  $("btcPrice").textContent =
    "$" + formatPrice(btc.current_price);

  $("btcChange").textContent =
    formatChange(btc.price_change_percentage_24h);

  $("btcChange").className =
    "hero-change " +
    (
      (btc.price_change_percentage_24h || 0) >= 0
        ? "positive"
        : "negative"
    );

  $("btcMarketCap").textContent =
    "Market cap: " +
    formatCompact(btc.market_cap);
}


/* =========================
   TRENDING
========================= */

function renderTrending() {
  const container = $("trendingCoins");

  if (!container) return;

  const coins = [...state.coins]
    .sort(
      (a, b) =>
        (b.price_change_percentage_24h || 0) -
        (a.price_change_percentage_24h || 0)
    )
    .slice(0, 4);

  if (!coins.length) {
    container.innerHTML = `
      <div class="loading-card">
        No trending data available.
      </div>
    `;
    return;
  }

  container.innerHTML = coins
    .map((coin) => {

      const change =
        Number(coin.price_change_percentage_24h) || 0;

      const image =
        typeof coin.image === "string"
          ? coin.image
          : "";

      return `
        <article
          class="trending-card"
          data-trending-id="${safeText(coin.id)}"
        >

          <div class="trending-card-top">

            <img
              src="${safeText(image)}"
              alt="${safeText(coin.name)} logo"
              loading="lazy"
              referrerpolicy="no-referrer"
            >

            <div>

              <h3>
                ${safeText(coin.name)}
              </h3>

              <p>
                ${safeText(coin.symbol).toUpperCase()}
              </p>

            </div>

          </div>

          <strong class="${
            change >= 0 ? "positive" : "negative"
          }">
            ${formatChange(change)}
          </strong>

          <p>
            $${formatPrice(coin.current_price)}
          </p>

        </article>
      `;
    })
    .join("");

  container
    .querySelectorAll("[data-trending-id]")
    .forEach((card) => {

      card.addEventListener("click", () => {

        const coin = state.coins.find(
          (item) =>
            item.id === card.dataset.trendingId
        );

        if (coin) {
          showCoinDetails(coin);
        }

      });

    });
}


/* =========================
   MARKET ANALYSIS
========================= */

function updateMarketAnalysis() {
  if (!state.coins.length) return;

  const changes = state.coins.map(
    (coin) =>
      Number(coin.price_change_percentage_24h) || 0
  );

  const average =
    changes.reduce(
      (sum, value) => sum + value,
      0
    ) / changes.length;

  let momentum =
    50 + average * 10;

  momentum =
    Math.max(0, Math.min(100, momentum));

  $("momentumValue").textContent =
    Math.round(momentum) + "/100";

  $("momentumBar").style.width =
    momentum + "%";

  let trend;

  if (average > 2) {

    trend = "Bullish";

    $("momentumText").textContent =
      "Strong positive market momentum.";

    $("marketTrendText").textContent =
      "Market conditions currently show strong positive movement.";

  } else if (average > .5) {

    trend = "Positive";

    $("momentumText").textContent =
      "Positive market momentum.";

    $("marketTrendText").textContent =
      "The market currently shows a positive bias.";

  } else if (average < -2) {

    trend = "Bearish";

    $("momentumText").textContent =
      "Strong negative market momentum.";

    $("marketTrendText").textContent =
      "The market is currently under stronger selling pressure.";

  } else if (average < -.5) {

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
      "No strong market direction is currently detected.";
  }

  $("marketTrend").textContent = trend;

  const shortScenario =
    Math.max(
      -20,
      Math.min(30, average * 4)
    );

  const mediumScenario =
    Math.max(
      -40,
      Math.min(70, average * 10)
    );

  $("shortTerm").textContent =
    formatScenario(shortScenario);

  $("mediumTerm").textContent =
    formatScenario(mediumScenario);
}


/* =========================
   COIN DETAILS
========================= */

async function showCoinDetails(coin) {
  state.selectedCoin = coin;

  const section = $("coinDetails");

  if (!section) return;

  section.classList.remove("hidden");

  $("selectedCoinName").textContent =
    coin.name;

  $("selectedCoinSymbol").textContent =
    coin.symbol.toUpperCase();

  const image = $("selectedCoinImage");

  if (image && coin.image) {
    image.src = coin.image;
    image.alt = coin.name + " logo";
    image.hidden = false;
  }

  $("detailPrice").textContent =
    "$" + formatPrice(coin.current_price);

  const change =
    Number(coin.price_change_percentage_24h) || 0;

  $("detailChange").textContent =
    formatChange(change);

  $("detailChange").className =
    change >= 0 ? "positive" : "negative";

  $("detailMarketCap").textContent =
    formatCompact(coin.market_cap);

  $("detailVolume").textContent =
    formatCompact(coin.total_volume);

  calculateCoinScore(coin);
  generateScenarios(coin);

  await loadChart(coin.id, state.chartDays);

  section.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });
}


/* =========================
   SCORE
========================= */

function calculateCoinScore(coin) {
  const change =
    Number(coin.price_change_percentage_24h) || 0;

  const marketCap =
    Number(coin.market_cap) || 0;

  const volume =
    Number(coin.total_volume) || 0;

  let score = 50;

  score += change * 4;

  if (
    marketCap > 0 &&
    volume / marketCap > .1
  ) {
    score += 8;
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
      "Current market indicators show stronger positive momentum. This does not guarantee future performance.";

  } else if (score >= 45) {

    signal = "Neutral";

    explanation =
      "Current indicators are mixed and do not provide a strong directional signal.";

  } else {

    signal = "Bearish";

    explanation =
      "Current indicators show weaker momentum and greater downside pressure.";
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
   SCENARIOS
========================= */

function generateScenarios(coin) {
  const change =
    Number(coin.price_change_percentage_24h) || 0;

  const short =
    clamp(change * 1.8, -20, 30);

  const medium =
    clamp(change * 4, -35, 60);

  const long =
    clamp(change * 7, -50, 100);

  $("shortPrediction").textContent =
    formatScenario(short);

  $("mediumPrediction").textContent =
    formatScenario(medium);

  $("longPrediction").textContent =
    formatScenario(long);
}

function formatScenario(value) {
  return (
    value >= 0 ? "+" : ""
  ) +
  Number(value).toFixed(1) +
  "%";
}

function clamp(value, min, max) {
  return Math.max(
    min,
    Math.min(max, value)
  );
}


/* =========================
   HISTORICAL CHART
========================= */

async function loadChart(coinId, days) {
  const chart = $("chart");

  if (!chart) return;

  chart.innerHTML = `
    <div class="chart-loading">
      Loading historical price data...
    </div>
  `;

  const cacheKey =
    `${coinId}-${days}`;

  if (state.chartCache.has(cacheKey)) {

    const prices =
      state.chartCache.get(cacheKey);

    renderChart(prices);

    return;
  }

  try {

    const url =
      API_BASE +
      `/coins/${encodeURIComponent(coinId)}/market_chart` +
      `?vs_currency=usd&days=${days}`;

    const response = await fetch(url, {
      headers: {
        Accept: "application/json"
      },
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(
        `Chart request failed: ${response.status}`
      );
    }

    const data = await response.json();

    if (
      !data ||
      !Array.isArray(data.prices) ||
      data.prices.length < 2
    ) {
      throw new Error("No chart data");
    }

    const prices =
      data.prices
        .filter(
          (item) =>
            Array.isArray(item) &&
            item.length >= 2 &&
            Number.isFinite(Number(item[1]))
        )
        .map((item) => [
          Number(item[0]),
          Number(item[1])
        ]);

    state.chartCache.set(
      cacheKey,
      prices
    );

    renderChart(prices);

  } catch (error) {

    console.error("Chart error:", error);

    chart.innerHTML = `
      <div class="chart-loading">
        Historical chart is temporarily unavailable.
      </div>
    `;
  }
}


function renderChart(prices) {
  const chart = $("chart");

  if (!chart || prices.length < 2) return;

  const width = 1000;
  const height = 300;

  const paddingX = 35;
  const paddingY = 25;

  const values =
    prices.map((item) => item[1]);

  const min =
    Math.min(...values);

  const max =
    Math.max(...values);

  const range =
    max - min || 1;

  const points =
    prices.map((item, index) => {

      const x =
        paddingX +
        (
          index /
          (prices.length - 1)
        ) *
        (width - paddingX * 2);

      const y =
        height -
        paddingY -
        (
          (item[1] - min) /
          range
        ) *
        (height - paddingY * 2);

      return [
        x,
        y
      ];
    });

  const line =
    points
      .map(
        ([x, y]) =>
          `${x.toFixed(2)},${y.toFixed(2)}`
      )
      .join(" ");

  const area =
    `${paddingX},${height - paddingY} ` +
    line +
    ` ${width - paddingX},${height - paddingY}`;

  const first = values[0];
  const last = values[values.length - 1];

  const performance =
    first !== 0
      ? ((last - first) / first) * 100
      : 0;

  const performanceClass =
    performance >= 0
      ? "positive"
      : "negative";

  chart.innerHTML = `
    <div
      style="
        position:absolute;
        top:12px;
        left:18px;
        z-index:2;
        font-size:12px;
        font-weight:800;
      "
      class="${performanceClass}"
    >
      ${performance >= 0 ? "+" : ""}
      ${performance.toFixed(2)}%
    </div>

    <svg
      viewBox="0 0 ${width} ${height}"
      preserveAspectRatio="none"
      role="img"
      aria-label="Historical cryptocurrency price chart"
    >

      <polygon
        points="${area}"
        fill="rgba(53,212,154,.07)"
      />

      <polyline
        points="${line}"
        fill="none"
        stroke="var(--green)"
        stroke-width="3"
        stroke-linecap="round"
        stroke-linejoin="round"
      />

    </svg>
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
  () => {

    state.chartCache.clear();

    fetchMarket();

  }
);

$("closeDetails")?.addEventListener(
  "click",
  () => {

    $("coinDetails")?.classList.add(
      "hidden"
    );

  }
);


document
  .querySelectorAll(".period-button")
  .forEach((button) => {

    button.addEventListener(
      "click",
      async () => {

        document
          .querySelectorAll(".period-button")
          .forEach((item) =>
            item.classList.remove("active")
          );

        button.classList.add("active");

        state.chartDays =
          Number(button.dataset.days) || 1;

        if (state.selectedCoin) {

          await loadChart(
            state.selectedCoin.id,
            state.chartDays
          );

        }

      }
    );

  });


/* Keyboard accessibility */

$("coins")?.addEventListener(
  "keydown",
  (event) => {

    const card =
      event.target.closest("[data-coin-id]");

    if (!card) return;

    if (
      event.key === "Enter" ||
      event.key === " "
    ) {

      event.preventDefault();

      card.click();

    }

  }
);


/* =========================
   START
========================= */

fetchMarket();
