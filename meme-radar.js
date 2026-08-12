(() => {
  "use strict";

  const API =
    "https://api.coingecko.com/api/v3/coins/markets";

  const MEME_COINS = [
    "dogecoin",
    "shiba-inu",
    "pepe",
    "bonk",
    "floki",
    "dogwifcoin",
    "brett",
    "mog-coin",
    "book-of-meme",
    "popcat",
    "cat-in-a-dogs-world",
    "moodeng",
    "official-trump",
    "fartcoin"
  ];

  /* Safe fetch wrapper */
  function createSafeFetch() {
    const CACHE_TTL = 60000;

    return async function safeFetch(url, opts = {}) {
      const timeout = opts.timeout || 10000;
      const maxRetries = opts.maxRetries || 2;
      const useCache = opts.useCache !== false;
      const cacheKey = "cache_" + url;

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
              ...opts,
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

  const safeFetch = createSafeFetch();

  const money = (value) => {
    if (!Number.isFinite(Number(value))) return "—";

    return "$" + Number(value).toLocaleString(undefined, {
      maximumFractionDigits: 8
    });
  };

  const compact = (value) => {
    if (!Number.isFinite(Number(value))) return "—";

    return "$" + Intl.NumberFormat(undefined, {
      notation: "compact",
      maximumFractionDigits: 2
    }).format(Number(value));
  };

  const percent = (value) => {
    if (!Number.isFinite(Number(value))) return "—";

    const n = Number(value);

    return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
  };

  function calculateScore(coin) {
    const change = Number(
      coin.price_change_percentage_24h || 0
    );

    const volume = Number(
      coin.total_volume || 0
    );

    const marketCap = Number(
      coin.market_cap || 0
    );

    const volumeRatio =
      marketCap > 0
        ? volume / marketCap
        : 0;

    const momentum = Math.max(
      0,
      Math.min(
        100,
        50 +
          change * 4 +
          Math.min(volumeRatio * 120, 25)
      )
    );

    const risk = Math.max(
      5,
      Math.min(
        100,
        70 -
          Math.min(
            (marketCap / 1000000000) * 12,
            45
          ) +
          Math.min(
            Math.abs(change) * 1.8,
            30
          )
      )
    );

    const memeScore = Math.round(
      Math.max(
        0,
        Math.min(
          100,
          momentum * 0.55 +
            Math.min(volumeRatio * 180, 35) +
            10
        )
      )
    );

    return {
      momentum: Math.round(momentum),
      risk: Math.round(risk),
      meme: memeScore
    };
  }

  function createCard(coin) {
    const score = calculateScore(coin);

    const change = Number(
      coin.price_change_percentage_24h || 0
    );

    return `
      <article class="meme-card">

        <div class="meme-card-head">

          <div class="meme-coin-name">

            <img
              src="${coin.image || ""}"
              alt=""
              loading="lazy"
            >

            <div>
              <strong>${coin.name}</strong>
              <span>
                ${(coin.symbol || "").toUpperCase()}
              </span>
            </div>

          </div>

          <span class="meme-score">
            ${score.meme}/100
          </span>

        </div>


        <div class="meme-price">

          ${money(coin.current_price)}

          <span class="${change >= 0 ? "up" : "down"}">
            ${percent(change)}
          </span>

        </div>


        <div class="meme-stats">

          <div>
            <small>Market Cap</small>
            <b>${compact(coin.market_cap)}</b>
          </div>

          <div>
            <small>Volume 24H</small>
            <b>${compact(coin.total_volume)}</b>
          </div>

        </div>


        <div class="meme-bars">

          <div>
            <span>Momentum</span>
            <b>${score.momentum}</b>
          </div>

          <div>
            <span>Risk</span>
            <b>${score.risk}</b>
          </div>

        </div>


        <button
          class="meme-analyze"
          data-id="${coin.id}"
        >
          🤖 AI ANALYZE
        </button>


        <div
          class="meme-ai"
          id="meme-ai-${coin.id}"
        ></div>

      </article>
    `;
  }


  function createAnalysis(coin) {

    const score =
      calculateScore(coin);

    let trend = "Neutral";

    if (score.momentum >= 65) {
      trend = "Bullish";
    }

    if (score.momentum <= 40) {
      trend = "Bearish";
    }

    let risk = "Lower";

    if (score.risk >= 70) {
      risk = "High";
    } else if (score.risk >= 45) {
      risk = "Medium";
    }

    return `
      <div class="meme-ai-panel">

        <div class="ai-title">
          🤖 AI MARKET ASSESSMENT
        </div>

        <p>
          Trend:
          <strong>${trend}</strong>
        </p>

        <p>
          Momentum:
          <strong>${score.momentum}/100</strong>
        </p>

        <p>
          Risk:
          <strong>${risk}</strong>
        </p>

        <p>
          Meme Score:
          <strong>${score.meme}/100</strong>
        </p>

        <p class="ai-description">
          Current price momentum and trading volume
          indicate the present market strength of this
          meme coin.
        </p>

        <small>
          ⚠️ This is a market-data assessment,
          not financial advice.
        </small>

      </div>
    `;
  }


  async function loadMemeRadar() {

    const container =
      document.getElementById("memeGrid");

    if (!container) {
      console.warn(
        "Meme Radar: #memeGrid not found."
      );
      return;
    }

    const loadingDiv =
      document.createElement("div");

    loadingDiv.className =
      "meme-loading";

    loadingDiv.textContent =
      "🔄 Loading Meme Radar...";

    container.innerHTML = "";
    container.appendChild(loadingDiv);

    try {

      const url =
        `${API}?vs_currency=usd` +
        `&ids=${encodeURIComponent(
          MEME_COINS.join(",")
        )}` +
        `&order=market_cap_desc` +
        `&sparkline=false` +
        `&price_change_percentage=24h`;

      const response =
        await safeFetch(url);

      if (!response.ok) {
        throw new Error(
          `CoinGecko HTTP ${response.status}`
        );
      }

      const coins =
        await response.json();

      if (
        !Array.isArray(coins) ||
        coins.length === 0
      ) {
        throw new Error(
          "No meme coins returned"
        );
      }

      container.innerHTML =
        coins.map(createCard).join("");


      container
        .querySelectorAll(".meme-analyze")
        .forEach((button) => {

          button.addEventListener(
            "click",
            () => {

              const coin =
                coins.find(
                  (item) =>
                    item.id ===
                    button.dataset.id
                );

              if (!coin) return;

              const box =
                document.getElementById(
                  `meme-ai-${coin.id}`
                );

              if (!box) return;

              box.innerHTML =
                createAnalysis(coin);
            }
          );

        });

    } catch (error) {

      console.error(
        "Meme Radar error:",
        error
      );

      const errorDiv =
        document.createElement("div");

      errorDiv.className =
        "meme-error";

      errorDiv.innerHTML = "";

      const text1 =
document.createTextNode(
"⚠️ Meme Radar is temporarily unavailable."
);

      errorDiv.appendChild(text1);

      const br1 =
document.createElement("br");

      errorDiv.appendChild(br1);

      const br2 =
document.createElement("br");

      errorDiv.appendChild(br2);

      const text2 =
document.createTextNode(
"Please refresh the page."
);

      errorDiv.appendChild(text2);

      container.innerHTML = "";
      container.appendChild(errorDiv);
    }
  }


  window.MemeRadar = {
    load: loadMemeRadar
  };


  if (
    document.readyState ===
    "loading"
  ) {

    document.addEventListener(
      "DOMContentLoaded",
      loadMemeRadar
    );

  } else {

    loadMemeRadar();

  }

})();
