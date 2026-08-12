(function () {
"use strict";

const marketGroups = {
stocks: {
title: "Stocks",
subtitle: "Major global stocks",
assets: [
["NASDAQ:AAPL", "Apple", "AAPL"],
["NASDAQ:MSFT", "Microsoft", "MSFT"],
["NASDAQ:NVDA", "NVIDIA", "NVDA"],
["NASDAQ:AMZN", "Amazon", "AMZN"],
["NASDAQ:GOOGL", "Alphabet", "GOOGL"],
["NASDAQ:META", "Meta Platforms", "META"],
["NASDAQ:TSLA", "Tesla", "TSLA"],
["NYSE:BRK.B", "Berkshire Hathaway", "BRK.B"],
["NYSE:JPM", "JPMorgan Chase", "JPM"],
["NYSE:V", "Visa", "V"],
["NYSE:WMT", "Walmart", "WMT"],
["NYSE:KO", "Coca-Cola", "KO"]
]
},

indices: {
  title: "Indices",
  subtitle: "Major global market indices",
  assets: [
    ["SP:SPX", "S&P 500", "SPX"],
    ["NASDAQ:NDX", "Nasdaq 100", "NDX"],
    ["DJ:DJI", "Dow Jones", "DJI"],
    ["TVC:VIX", "VIX", "VIX"],
    ["INDEX:DAX", "DAX", "DAX"],
    ["INDEX:FTSE", "FTSE 100", "FTSE"],
    ["INDEX:CAC40", "CAC 40", "CAC40"],
    ["INDEX:NKY", "Nikkei 225", "NIKKEI"],
    ["INDEX:HSI", "Hang Seng", "HSI"]
  ]
},

commodities: {
  title: "Commodities",
  subtitle: "Gold, silver, oil and energy markets",
  assets: [
    ["TVC:GOLD", "Gold", "GOLD"],
    ["TVC:SILVER", "Silver", "SILVER"],
    ["TVC:USOIL", "WTI Crude Oil", "WTI"],
    ["TVC:UKOIL", "Brent Crude Oil", "BRENT"],
    ["NYMEX:NG1!", "Natural Gas", "GAS"],
    ["COMEX:COPPER", "Copper", "COPPER"]
  ]
}

};

function injectStyles() {
if (document.getElementById("markets-extra-style")) {
return;
}

const style =
  document.createElement("style");

style.id =
  "markets-extra-style";

style.textContent = `
  .asset-tabs {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin: 0 0 22px;
    padding: 6px;
    background: rgba(255,255,255,.035);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 12px;
  }

  .asset-tab {
    border: 0;
    background: transparent;
    color: #8f98a8;
    padding: 10px 18px;
    border-radius: 9px;
    cursor: pointer;
    font-weight: 700;
    transition: .2s ease;
  }

  .asset-tab:hover {
    color: #fff;
    background: rgba(255,255,255,.06);
  }

  .asset-tab.active {
    color: #fff;
    background: rgba(255,255,255,.10);
  }

  .asset-market-panel {
    display: none;
  }

  .asset-market-panel.active {
    display: block;
  }

  .asset-grid {
    display: grid;
    grid-template-columns:
      repeat(auto-fill, minmax(210px, 1fr));
    gap: 14px;
  }

  .asset-card {
    padding: 18px;
    border-radius: 14px;
    border: 1px solid rgba(255,255,255,.08);
    background: rgba(255,255,255,.025);
    cursor: pointer;
    transition:
      transform .18s ease,
      border-color .18s ease,
      background .18s ease;
  }

  .asset-card:hover {
    transform: translateY(-2px);
    border-color: rgba(255,255,255,.18);
    background: rgba(255,255,255,.045);
  }

  .asset-card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 18px;
  }

  .asset-card-name {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .asset-card-name strong {
    color: #fff;
    font-size: 14px;
  }

  .asset-card-name span {
    color: #7f899a;
    font-size: 11px;
    font-weight: 700;
  }

  .asset-symbol {
    width: 36px;
    height: 36px;
    display: grid;
    place-items: center;
    border-radius: 10px;
    background: rgba(255,255,255,.07);
    color: #fff;
    font-size: 10px;
    font-weight: 800;
  }

  .asset-card-chart {
    height: 115px;
    border-radius: 10px;
    overflow: hidden;
    background: rgba(0,0,0,.15);
  }

  .asset-full-chart {
    margin-top: 22px;
    height: 620px;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.08);
  }

  .asset-selected-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 15px;
    margin-bottom: 14px;
  }

  .asset-selected-title strong {
    color: #fff;
    font-size: 18px;
  }

  .asset-selected-title span {
    color: #8f98a8;
    font-size: 12px;
  }

  @media (max-width: 700px) {
    .asset-tab {
      flex: 1;
      min-width: 90px;
    }

    .asset-grid {
      grid-template-columns: 1fr;
    }

    .asset-full-chart {
      height: 480px;
    }
  }
`;

document.head.appendChild(style);

}

function createTradingView(
container,
symbol,
interval
) {
container.innerHTML = "";

const wrapper =
  document.createElement("div");

wrapper.className =
  "tradingview-widget-container";

wrapper.style.width =
  "100%";

wrapper.style.height =
  "100%";

const widget =
  document.createElement("div");

widget.className =
  "tradingview-widget-container__widget";

widget.style.width =
  "100%";

widget.style.height =
  "100%";

wrapper.appendChild(widget);

container.appendChild(wrapper);

const script =
  document.createElement("script");

script.src =
  "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";

script.type =
  "text/javascript";

script.async = true;

script.textContent =
  JSON.stringify({
    autosize: true,
    symbol: symbol,
    interval: interval || "60",
    timezone: "Etc/UTC",
    theme: "dark",
    style: "1",
    locale: "en",
    enable_publishing: false,
    allow_symbol_change: false,
    hide_top_toolbar: false,
    hide_legend: true,
    save_image: false,
    backgroundColor:
      "rgba(0,0,0,0)"
  });

wrapper.appendChild(script);

}

function createAssetCard(
asset
) {
const card =
document.createElement("article");

card.className =
  "asset-card";

card.innerHTML = `
  <div class="asset-card-head">
    <div class="asset-card-name">
      <strong>${asset[1]}</strong>
      <span>${asset[2]}</span>
    </div>

    <div class="asset-symbol">
      ${asset[2].slice(0, 4)}
    </div>
  </div>

  <div class="asset-card-chart"></div>
`;

const chart =
  card.querySelector(
    ".asset-card-chart"
  );

createTradingView(
  chart,
  asset[0],
  "60"
);

card.addEventListener(
  "click",
  function () {
    showFullChart(
      asset[0],
      asset[1],
      asset[2]
    );
  }
);

return card;

}

function showFullChart(
symbol,
name,
ticker
) {
const title =
document.getElementById(
"asset-selected-title"
);

const chart =
  document.getElementById(
    "asset-full-chart"
  );

if (!title || !chart) {
  return;
}

title.innerHTML = "";

const titleDiv =
document.createElement("div");

const titleStrong =
document.createElement("strong");

titleStrong.textContent = name;

titleDiv.appendChild(titleStrong);

const titleSpan =
document.createElement("span");

titleSpan.textContent = ticker;

titleDiv.appendChild(titleSpan);

title.appendChild(titleDiv);

createTradingView(
  chart,
  symbol,
  "60"
);

chart.scrollIntoView({
  behavior: "smooth",
  block: "start"
});

}

function createPanel(
key,
group
) {
const panel =
document.createElement("div");

panel.className =
  "asset-market-panel";

panel.dataset.market =
  key;

panel.innerHTML = `
  <div class="section-header">
    <div>
      <h2 class="section-title">
        ${group.title}
      </h2>

      <p class="section-subtitle">
        ${group.subtitle}
      </p>
    </div>
  </div>

  <div class="asset-grid"></div>
`;

const grid =
  panel.querySelector(
    ".asset-grid"
  );

group.assets.forEach(
  function (asset) {
    grid.appendChild(
      createAssetCard(asset)
    );
  }
);

return panel;

}

function buildMarkets() {
const markets =
document.getElementById(
"markets"
);

if (!markets) {
  console.warn(
    "Markets section not found"
  );

  return;
}

if (
  document.getElementById(
    "extra-markets"
  )
) {
  return;
}

const wrapper =
  document.createElement("div");

wrapper.id =
  "extra-markets";

wrapper.innerHTML = `
  <div class="asset-tabs">

    <button
      class="asset-tab active"
      data-market-tab="stocks"
      type="button"
    >
      Stocks
    </button>

    <button
      class="asset-tab"
      data-market-tab="indices"
      type="button"
    >
      Indices
    </button>

    <button
      class="asset-tab"
      data-market-tab="commodities"
      type="button"
    >
      Commodities
    </button>

  </div>

  <div id="asset-panels"></div>

  <div class="card" style="margin-top:22px">
    <div class="card-body">

      <div
        id="asset-selected-title"
        class="asset-selected-title"
      >
        <div>
          <strong>
            Select a market
          </strong>

          <span>
            TradingView
          </span>
        </div>
      </div>

      <div
        id="asset-full-chart"
        class="asset-full-chart"
      ></div>

    </div>
  </div>
`;

const coinGrid =
  document.getElementById(
    "coinGrid"
  );

if (
  coinGrid &&
  coinGrid.parentElement
) {
  coinGrid.parentElement.appendChild(
    wrapper
  );
} else {
  markets.appendChild(
    wrapper
  );
}

const panels =
  document.getElementById(
    "asset-panels"
  );

Object.keys(
  marketGroups
).forEach(
  function (key) {
    panels.appendChild(
      createPanel(
        key,
        marketGroups[key]
      )
    );
  }
);

activateTab(
  "stocks"
);

document
  .querySelectorAll(
    "[data-market-tab]"
  )
  .forEach(
    function (button) {
      button.addEventListener(
        "click",
        function () {
          activateTab(
            button.dataset.marketTab
          );
        }
      );
    }
  );

}

function activateTab(
key
) {
document
.querySelectorAll(
"[data-market-tab]"
)
.forEach(
function (button) {
button.classList.toggle(
"active",
button.dataset.marketTab ===
key
);
}
);

document
  .querySelectorAll(
    ".asset-market-panel"
  )
  .forEach(
    function (panel) {
      panel.classList.toggle(
        "active",
        panel.dataset.market ===
          key
      );
    }
  );

}

function init() {
injectStyles();
buildMarkets();
}

if (
document.readyState ===
"loading"
) {
document.addEventListener(
"DOMContentLoaded",
init
);
} else {
init();
}
})();
