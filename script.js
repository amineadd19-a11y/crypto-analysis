"use strict";

const API = {
  market: "/api/market",
  chart: "/api/chart"
};

const state = {
  coins: [],
  selectedCoin: null,
  chartDays: 1,
  chartCache: new Map(),
  loading: false
};

const $ = (id) => document.getElementById(id);

function formatPrice(value) {
  const n = Number(value);

  if (!Number.isFinite(n)) return "—";

  if (n >= 1000) {
    return n.toLocaleString("en-US", {
      maximumFractionDigits: 2
    });
  }

  if (n >= 1) {
    return n.toLocaleString("en-US", {
      maximumFractionDigits: 4
    });
  }

  return n.toLocaleString("en-US", {
    maximumFractionDigits: 8
  });
}

function formatCompact(value) {
  const n = Number(value);

  if (!Number.isFinite(n)) return "—";

  if (n >= 1e12) return "$" + (n / 1e12).toFixed(2) + "T";
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(2) + "K";

  return "$" + n.toLocaleString("en-US");
}

function formatChange(value) {
  const n = Number(value) || 0;
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}

function escapeHTML(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      })[char]
  );
}

function setStatus(message) {
  const element = $("marketStatus");

  if (element) {
    element.textContent = message;
  }
}


/* =========================
   MARKET
========================= */

async function fetchMarket() {
  if (state.loading) return;

  state.loading = true;

  setStatus("Loading live market data...");

  try {
    const response = await fetch(API.market, {
      method: "GET",
      headers: {
        Accept: "application/json"
      },
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error(
        `Market API error: ${response.status}`
      );
    }

    const data = await response.json();

    if (!Array.isArray(data)) {
      throw new Error("Invalid market data");
    }

    state.coins = data.filter(
      (coin) =>
        coin &&
        coin.id &&
        coin.name &&
        coin.symbol
    );

    renderMarket();
    updateBitcoin();
    updateMarketAnalysis();
    renderTrending();

    setStatus(
      `${state.coins.length} cryptocurrencies loaded.`
    );

    if ($("updated")) {
      $("updated").textContent =
        "Updated: " +
        new Date().toLocaleTimeString();
    }

  } catch (error) {

    console.error(error);

    setStatus(
      "Unable to load market data. Please try again."
    );

    if ($("coins")) {
      $("coins").innerHTML = `
        <div class="error-card">
          Market data is temporarily unavailable.
          Please press Refresh and try again.
        </div>
      `;
    }

  } finally {
    state.loading = false;
  }
}


/* =========================
   MARKET CARDS
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

      const name =
        String(coin.name).toLowerCase();

      const symbol =
        String(coin.symbol).toLowerCase();

      return (
        name.includes(query) ||
        symbol.includes(query)
      );
    });
  }

  const sort =
    $("coinSort")?.value || "rank";

  coins.sort((a, b) => {

    switch (sort) {

      case "price":
        return (
          (b.current_price || 0) -
          (a.current_price || 0)
        );

      case "change":
        return (
          (b.price_change_percentage_24h || 0) -
          (a.price_change_percentage_24h || 0)
        );

      case "volume":
        return (
          (b.total_volume || 0) -
          (a.total_volume || 0)
        );

      case "marketcap":
        return (
          (b.market_cap || 0) -
          (a.market_cap || 0)
        );

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

  container.innerHTML =
    coins
      .slice(0, 100)
      .map(createCoinCard)
      .join("");

  container
    .querySelectorAll("[data-coin-id]")
    .forEach((card) => {

      card.addEventListener(
        "click",
        () => {

          const coin =
            state.coins.find(
              (item) =>
                item.id ===
                card.dataset.coinId
            );

          if (coin) {
            showCoinDetails(coin);
          }
        }
      );

    });
}


function createCoinCard(coin) {

  const change =
    Number(
      coin.price_change_percentage_24h
    ) || 0;

  const changeClass =
    change >= 0
      ? "positive"
      : "negative";

  return `
    <article
      class="coin-card"
      data-coin-id="${escapeHTML(coin.id)}"
      tabindex="0"
      role="button"
    >

      <div class="coin-top">

        <div class="coin-identity">

          <img
            class="coin-image"
            src="${escapeHTML(coin.image)}"
            alt="${escapeHTML(coin.name)} logo"
            loading="lazy"
            referrerpolicy="no-referrer"
          >

          <div>

            <div class="coin-name">
              ${escapeHTML(coin.name)}
            </div>

            <div class="coin-symbol">
              ${escapeHTML(
                coin.symbol
              ).toUpperCase()}
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
          Market Cap
          ${formatCompact(coin.market_cap)}
        </span>

        <span>
          Volume
          ${formatCompact(coin.total_volume)}
        </span>

      </div>

    </article>
  `;
}


/* =========================
   BITCOIN
========================= */

function updateBitcoin() {

  const btc =
    state.coins.find(
      (coin) =>
        coin.id === "bitcoin" ||
        String(coin.symbol)
          .toLowerCase() === "btc"
    );

  if (!btc) return;

  if ($("btcPrice")) {
    $("btcPrice").textContent =
      "$" +
      formatPrice(
        btc.current_price
      );
  }

  if ($("btcChange")) {

    const change =
      Number(
        btc.price_change_percentage_24h
      ) || 0;

    $("btcChange").textContent =
      formatChange(change);

    $("btcChange").className =
      "hero-change " +
      (
        change >= 0
          ? "positive"
          : "negative"
      );
  }

  if ($("btcMarketCap")) {
    $("btcMarketCap").textContent =
      "Market cap: " +
      formatCompact(
        btc.market_cap
      );
  }
}


/* =========================
   TRENDING
========================= */

function renderTrending() {

  const container =
    $("trendingCoins");

  if (!container) return;

  const coins =
    [...state.coins]
      .sort(
        (a, b) =>
          (b.price_change_percentage_24h || 0) -
          (a.price_change_percentage_24h || 0)
      )
      .slice(0, 4);

  container.innerHTML =
    coins.map((coin) => {

      const change =
        Number(
          coin.price_change_percentage_24h
        ) || 0;

      return `
        <article
          class="trending-card"
          data-trending-id="${escapeHTML(coin.id)}"
        >

          <div class="trending-card-top">

            <img
              src="${escapeHTML(coin.image)}"
              alt="${escapeHTML(coin.name)} logo"
              loading="lazy"
              referrerpolicy="no-referrer"
            >

            <div>

              <h3>
                ${escapeHTML(coin.name)}
              </h3>

              <p>
                ${escapeHTML(
                  coin.symbol
                ).toUpperCase()}
              </p>

            </div>

          </div>

          <strong
            class="${
              change >= 0
                ? "positive"
                : "negative"
            }"
          >
            ${formatChange(change)}
          </strong>

          <p>
            $${formatPrice(
              coin.current_price
            )}
          </p>

        </article>
      `;
    }).join("");

  container
    .querySelectorAll(
      "[data-trending-id]"
    )
    .forEach((card) => {

      card.addEventListener(
        "click",
        () => {

          const coin =
            state.coins.find(
              (item) =>
                item.id ===
                card.dataset.trendingId
            );

          if (coin) {
            showCoinDetails(coin);
          }

        }
      );

    });
}


/* =========================
   MARKET ANALYSIS
========================= */

function updateMarketAnalysis() {

  if (!state.coins.length) return;

  const changes =
    state.coins.map(
      (coin) =>
        Number(
          coin.price_change_percentage_24h
        ) || 0
    );

  const average =
    changes.reduce(
      (sum, value) =>
        sum + value,
      0
    ) / changes.length;

  const momentum =
    Math.max(
      0,
      Math.min(
        100,
        50 + average * 10
      )
    );

  if ($("momentumValue")) {
    $("momentumValue").textContent =
      Math.round(momentum) +
      "/100";
  }

  if ($("momentumBar")) {
    $("momentumBar").style.width =
      momentum + "%";
  }

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
      "The market currently shows stronger selling pressure.";

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

  $("marketTrend").textContent =
    trend;

  $("shortTerm").textContent =
    scenario(average * 4);

  $("mediumTerm").textContent =
    scenario(average * 10);
}


/* =========================
   COIN DETAILS
========================= */

async function showCoinDetails(coin) {

  state.selectedCoin = coin;

  const section =
    $("coinDetails");

  if (!section) return;

  section.classList.remove(
    "hidden"
  );

  $("selectedCoinName").textContent =
    coin.name;

  $("selectedCoinSymbol").textContent =
    coin.symbol.toUpperCase();

  const image =
    $("selectedCoinImage");

  if (image && coin.image) {
    image.src = coin.image;
    image.alt =
      coin.name + " logo";
    image.hidden = false;
  }

  $("detailPrice").textContent =
    "$" +
    formatPrice(
      coin.current_price
    );

  const change =
    Number(
      coin.price_change_percentage_24h
    ) || 0;

  $("detailChange").textContent =
    formatChange(change);

  $("detailChange").className =
    change >= 0
      ? "positive"
      : "negative";

  $("detailMarketCap").textContent =
    formatCompact(
      coin.market_cap
    );

  $("detailVolume").textContent =
    formatCompact(
      coin.total_volume
    );

  calculateCoinScore(coin);
  generateScenarios(coin);

  await loadChart(
    coin.id,
    state.chartDays
  );

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
    Number(
      coin.price_change_percentage_24h
    ) || 0;

  const marketCap =
    Number(
      coin.market_cap
    ) || 0;

  const volume =
    Number(
      coin.total_volume
    ) || 0;

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
        Math.min(
          100,
          score
        )
      )
    );

  $("coinScore").textContent =
    score;

  let signal;
  let explanation;

  if (score >= 70) {

    signal = "Bullish";

    explanation =
      "Current indicators show stronger positive momentum. This is an educational signal, not a guaranteed prediction.";

  } else if (score >= 45) {

    signal = "Neutral";

    explanation =
      "Current indicators are mixed and do not show a strong directional signal.";

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
    Number(
      coin.price_change_percentage_24h
    ) || 0;

  $("shortPrediction").textContent =
    scenario(
      clamp(
        change * 1.8,
        -20,
        30
      )
    );

  $("mediumPrediction").textContent =
    scenario(
      clamp(
        change * 4,
        -35,
        60
      )
    );

  $("longPrediction").textContent =
    scenario(
      clamp(
        change * 7,
        -50,
        100
      )
    );
}

function scenario(value) {

  const n =
    Number(value) || 0;

  return (
    n >= 0 ? "+" : ""
  ) +
  n.toFixed(1) +
  "%";
}

function clamp(value, min, max) {
  return Math.max(
    min,
    Math.min(max, value)
  );
}


/* =========================
   CHART API
========================= */

async function loadChart(
  coinId,
  days
) {

  const chart =
    $("chart");

  if (!chart) return;

  const key =
    `${coinId}-${days}`;

  chart.innerHTML = `
    <div class="chart-loading">
      Loading historical price data...
    </div>
  `;

  if (
    state.chartCache.has(key)
  ) {

    renderChart(
      state.chartCache.get(key)
    );

    return;
  }

  try {

    const url =
      `${API.chart}?id=${encodeURIComponent(
        coinId
      )}&days=${encodeURIComponent(
        days
      )}`;

    const response =
      await fetch(url, {
        headers: {
          Accept: "application/json"
        },
        cache: "no-store"
      });

    if (!response.ok) {
      throw new Error(
        `Chart API error: ${response.status}`
      );
    }

    const data =
      await response.json();

    if (
      !data ||
      !Array.isArray(data.prices) ||
      data.prices.length < 2
    ) {
      throw new Error(
        "Invalid chart data"
      );
    }

    const prices =
      data.prices.filter(
        (item) =>
          Array.isArray(item) &&
          item.length >= 2 &&
          Number.isFinite(
            Number(item[1])
          )
      );

    state.chartCache.set(
      key,
      prices
    );

    renderChart(prices);

  } catch (error) {

    console.error(error);

    chart.innerHTML = `
      <div class="chart-loading">
        Historical chart is temporarily unavailable.
      </div>
    `;
  }
}


/* =========================
   CHART RENDER
========================= */

function renderChart(prices) {

  const chart =
    $("chart");

  if (
    !chart ||
    prices.length < 2
  ) {
    return;
  }

  const width = 1000;
  const height = 300;

  const padX = 35;
  const padY = 25;

  const values =
    prices.map(
      (item) =>
        Number(item[1])
    );

  const min =
    Math.min(...values);

  const max =
    Math.max(...values);

  const range =
    max - min || 1;

  const points =
    prices.map(
      (item, index) => {

        const x =
          padX +
          (
            index /
            (prices.length - 1)
          ) *
          (width - padX * 2);

        const y =
          height -
          padY -
          (
            (
              item[1] -
              min
            ) /
            range
          ) *
          (
            height -
            padY * 2
          );

        return [
          x,
          y
        ];
      }
    );

  const line =
    points
      .map(
        ([x, y]) =>
          `${x.toFixed(2)},${y.toFixed(2)}`
      )
      .join(" ");

  const area =
    `${padX},${height - padY} ` +
    line +
    ` ${width - padX},${height - padY}`;

  const first =
    values[0];

  const last =
    values[values.length - 1];

  const performance =
    first
      ? (
          (last - first) /
          first
        ) * 100
      : 0;

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
      class="${
        performance >= 0
          ? "positive"
          : "negative"
      }"
    >
      ${
        performance >= 0
          ? "+"
          : ""
      }${performance.toFixed(2)}%
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

    $("coinDetails")
      ?.classList.add("hidden");

  }
);

document
  .querySelectorAll(".period-button")
  .forEach((button) => {

    button.addEventListener(
      "click",
      async () => {

        document
          .querySelectorAll(
            ".period-button"
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

        state.chartDays =
          Number(
            button.dataset.days
          ) || 1;

        if (
          state.selectedCoin
        ) {

          await loadChart(
            state.selectedCoin.id,
            state.chartDays
          );
        }
      }
    );
  });


/* =========================
   START
========================= */

fetchMarket();
