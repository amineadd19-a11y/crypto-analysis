export default async function handler(req, res) {
  try {
    const { id, days = "1" } = req.query;

    if (!id) {
      return res.status(400).json({
        error: "Coin ID is required"
      });
    }

    const allowedDays = ["1", "7", "30", "90"];

    if (!allowedDays.includes(String(days))) {
      return res.status(400).json({
        error: "Invalid period"
      });
    }

    const coinId = encodeURIComponent(String(id));

    const url =
      "https://api.coingecko.com/api/v3/coins/" +
      coinId +
      "/market_chart" +
      "?vs_currency=usd" +
      "&days=" +
      days;

    const response = await fetch(url, {
      headers: {
        Accept: "application/json"
      }
    });

    if (!response.ok) {
      return res.status(response.status).json({
        error: "Chart data unavailable"
      });
    }

    const data = await response.json();

    res.setHeader(
      "Cache-Control",
      "s-maxage=120, stale-while-revalidate=600"
    );

    return res.status(200).json(data);

  } catch (error) {

    console.error("Chart API error:", error);

    return res.status(500).json({
      error: "Internal server error"
    });
  }
}
