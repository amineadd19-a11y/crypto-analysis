export default async function handler(req, res) {
  try {
    const response = await fetch(
      "https://api.coingecko.com/api/v3/coins/markets" +
      "?vs_currency=usd" +
      "&order=market_cap_desc" +
      "&per_page=100" +
      "&page=1" +
      "&sparkline=false" +
      "&price_change_percentage=24h",
      {
        headers: {
          Accept: "application/json"
        }
      }
    );

    if (!response.ok) {
      return res.status(response.status).json({
        error: "Market data unavailable"
      });
    }

    const data = await response.json();

    res.setHeader(
      "Cache-Control",
      "s-maxage=60, stale-while-revalidate=300"
    );

    res.status(200).json(data);

  } catch (error) {

    console.error(error);

    res.status(500).json({
      error: "Internal server error"
    });
  }
}
