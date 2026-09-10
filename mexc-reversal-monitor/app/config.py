from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    symbols: tuple[str, ...] = tuple(x.strip().upper() for x in os.getenv("SYMBOLS", "").split(",") if x.strip())
    move_1m_pct: float = float(os.getenv("MOVE_1M_PCT", "3"))
    move_5m_pct: float = float(os.getenv("MOVE_5M_PCT", "7"))
    volume_ratio: float = float(os.getenv("VOLUME_RATIO", "3"))
    ema_extension_pct: float = float(os.getenv("EMA_EXTENSION_PCT", "2"))
    vwap_extension_pct: float = float(os.getenv("VWAP_EXTENSION_PCT", "2"))
    min_score: int = int(os.getenv("MIN_SCORE", "70"))
    cooldown_minutes: int = int(os.getenv("COOLDOWN_MINUTES", "15"))
    poll_seconds: int = int(os.getenv("POLL_SECONDS", "2"))
    enable_short: bool = _bool("ENABLE_SHORT", True)
    enable_long: bool = _bool("ENABLE_LONG", True)
    alert_once_per_candle: bool = _bool("ALERT_ONCE_PER_CANDLE", True)


SETTINGS = Settings()
