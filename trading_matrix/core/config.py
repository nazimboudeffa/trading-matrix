from dataclasses import dataclass

APP_NAME = "Trading Matrix"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
THEME_DARK = True


@dataclass(frozen=True)
class AppConfig:
    APP_NAME: str = APP_NAME
    WINDOW_WIDTH: int = WINDOW_WIDTH
    WINDOW_HEIGHT: int = WINDOW_HEIGHT
    THEME_DARK: bool = THEME_DARK


# Intervalles et périodes supportés
INTERVALS = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo"]
PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]

DEFAULT_SYMBOL = "AAPL"
DEFAULT_INTERVAL = "1d"
DEFAULT_PERIOD = "6mo"

PALETTE = {
    "bg": "#131722",
    "panel": "#1e222d",
    "grid": "#2a2e39",
    "text": "#d1d4dc",
    "text_sub": "#787b86",
    "up": "#26a69a",
    "down": "#ef5350",
    "volume_up": "#26a69a80",
    "volume_down": "#ef535080",
    "ma_short": "#f0b90b",
    "ma_mid": "#2962ff",
    "ma_long": "#9c27b0",
    "bb": "#787b86",
    "cross": "#ffffff",
    "pending": "#f0b90b",
}
