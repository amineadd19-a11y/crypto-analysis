const API =
  "https://api.coingecko.com/api/v3/coins/markets" +
  "?vs_currency=usd&order=market_cap_desc&per_page=12&page=1" +
  "&sparkline=false&price_change_percentage=24h";

async function loadMarket() {
  const coinsContainer = document.getElementById("coins");

  coinsContainer.innerHTML = "Loading market data...";

  try {
    const response = await fetch(API);

    if (!response.ok) {
      throw new Error("Market API error");
    }

    const coins = await response.json();
allCoins = coins;
setupMarketTools();
    displayCoins(coins);
    updateAnalysis(coins);

    document.getElementById("updated").textContent =
      "Updated: " + new Date().toLocaleTimeString();

  } catch (error) {

    coinsContainer.innerHTML = `
      <div class="coin">
        <h3>Market data unavailable</h3>
        <p>
          Please try again in a few seconds.
        </p>
      </div>
    `;

    console.error(error);
  }
}

let allCoins = [];

function setupMarketTools() {

  const search = document.getElementById("coinSearch");
  const sort = document.getElementById("coinSort");

  if (!search || !sort) return;

  search.addEventListener("input", renderMarket);
  sort.addEventListener("change", renderMarket);
}

function renderMarket() {

  const search =
    document.getElementById("coinSearch");

  const sort =
    document.getElementById("coinSort");

  let filtered = [...allCoins];

  const query =
    search.value.trim().toLowerCase();

  if (query) {
    filtered = filtered.filter(coin =>
      coin.name.toLowerCase().includes(query) ||
      coin.symbol.toLowerCase().includes(query)
    );
  }

  if (sort.value === "price") {
    filtered.sort(
      (a, b) => b.current_price - a.current_price
    );
  }

  if (sort.value === "change") {
    filtered.sort(
      (a, b) =>
        (b.price_change_percentage_24h || 0) -
        (a.price_change_percentage_24h || 0)
    );
  }

  if (sort.value === "volume") {
    filtered.sort(
      (a, b) =>
        (b.total_volume || 0) -
        (a.total_volume || 0)
    );
  }

  displayCoins(filtered);
}
function displayCoins(coins) {

  const container = document.getElementById("coins");

  container.innerHTML = "";

  coins.forEach((coin) => {

    const change = coin.price_change_percentage_24h || 0;

    const changeClass =
      change >= 0 ? "positive" : "negative";

    const sign =
      change >= 0 ? "+" : "";

    const card = document.createElement("div");

    card.className = "coin";

    card.innerHTML = `

      <div class="coin-top">

        <div>

          <div class="coin-name">
            ${coin.name}
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
        ${sign}${change.toFixed(2)}%
      </div>

    `;

    container.appendChild(card);

  });

  const btc = coins.find(
    coin => coin.symbol.toLowerCase() === "btc"
  );

  if (btc) {

    document.getElementById("btcPrice").textContent =
      "$" + formatPrice(btc.current_price);

    const btcChange =
      btc.price_change_percentage_24h || 0;

    const btcElement =
      document.getElementById("btcChange");

    btcElement.textContent =
      `${btcChange >= 0 ? "+" : ""}${btcChange.toFixed(2)}% today`;

    btcElement.className =
      btcChange >= 0 ? "positive" : "negative";
  }
}


function updateAnalysis(coins) {

  if (!coins || coins.length === 0) {
    return;
  }

  const changes = coins
    .map(c => c.price_change_percentage_24h || 0);

  const average =
    changes.reduce((a, b) => a + b, 0) / changes.length;

  let momentum = 50 + average * 10;

  momentum =
    Math.max(5, Math.min(95, momentum));

  document.getElementById("momentumBar")
    .style.width = momentum + "%";


  let momentumText;

  if (average > 2) {

    momentumText =
      "Strong positive market momentum.";

  } else if (average > 0.5) {

    momentumText =
      "Positive market momentum.";

  } else if (average < -2) {

    momentumText =
      "Strong negative market momentum.";

  } else if (average < -0.5) {

    momentumText =
      "Negative market momentum.";

  } else {

    momentumText =
      "Market momentum is currently neutral.";

  }

  document.getElementById("momentumText")
    .textContent = momentumText;


  const shortPercent =
    Math.max(-20, Math.min(30, average * 4));

  const mediumPercent =
    Math.max(-40, Math.min(80, average * 10));


  document.getElementById("shortTerm")
    .textContent =
      formatScenario(shortPercent);


  document.getElementById("mediumTerm")
    .textContent =
      formatScenario(mediumPercent);
}


function formatScenario(value) {

  const sign = value >= 0 ? "+" : "";

  return sign + value.toFixed(1) + "%";
}


function formatPrice(price) {

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


loadMarket();
