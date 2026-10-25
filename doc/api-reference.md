# Référence API

Cette page liste les classes et fonctions principales exposées par le projet.

## `core.config`

Constantes globales.

| Nom | Type | Valeur / rôle |
| --- | --- | --- |
| `APP_NAME` | `str` | `"Trading Matrix"` |
| `WINDOW_WIDTH` / `WINDOW_HEIGHT` | `int` | `1400` / `900` |
| `THEME_DARK` | `bool` | `True` |
| `AppConfig` | dataclass | Regroupe les constantes ci-dessus |
| `INTERVALS` | `list[str]` | `1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk, 1mo` |
| `PERIODS` | `list[str]` | `1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max` |
| `DEFAULT_SYMBOL` | `str` | `"AAPL"` |
| `DEFAULT_INTERVAL` | `str` | `"1d"` |
| `DEFAULT_PERIOD` | `str` | `"6mo"` |
| `PALETTE` | `dict[str, str]` | Couleurs du thème (`bg`, `up`, `down`, `text`...) |

## `core.ollama_client`

Client de l'API locale [Ollama](https://ollama.com) (analyse IA).

```python
class OllamaError(RuntimeError)

@dataclass
class OllamaStatus:
    installed: bool
    running: bool
    models: list[str] = []
    error: str = ""
    executable: str | None = None

    @property
    def ready(self) -> bool

def base_url() -> str
def find_executable() -> str | None
def fetch_models(timeout: float = 4.0) -> list[str]
def get_status(timeout: float = 2.5) -> OllamaStatus
def chat_stream(
    model: str,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    num_ctx: int = 8192,
    timeout: tuple[float, float | None] = (5.0, 600.0),
    stop_event: threading.Event | None = None,
) -> Iterator[tuple[str, str]]
```

`chat_stream` diffuse des tuples `(kind, texte)` où `kind` vaut `"content"` ou
`"thinking"`. L'URL du serveur peut être changée avec `OLLAMA_HOST`.

## `core.signal_context`

Construction du contexte de marché et du prompt d'analyse IA d'un signal.

```python
SYSTEM_PROMPT: str

@dataclass(frozen=True)
class AIPrompt:
    system: str
    user: str
    @property
    def messages(self) -> list[dict[str, str]]
    def display_text(self) -> str

def find_bar_index(df: pd.DataFrame, timestamp) -> int | None
def build_signal_prompt(
    sig: Signal,
    df: pd.DataFrame,
    *,
    symbol: str = "",
    timeframe: str = "",
    strategy_name: str = "",
    strategy_description: str = "",
    candles: int = 40,
) -> AIPrompt
```

Seules les bougies **jusqu'au signal inclus** sont incluses dans le prompt.

## `data`

### `OpenBBClient`

```python
class OpenBBClient:
    def is_available(self) -> bool
    def get_ohlcv(self, symbol: str, interval="1d", period="6mo", **kwargs) -> pd.DataFrame
```

- `is_available()` : `True` si OpenBB **ou** yfinance est importable
- `get_ohlcv()` : applique la chaîne OpenBB → yfinance → démo et retourne un
  DataFrame normalisé (`DatetimeIndex`, colonnes OHLCV)

### `data.demo`

```python
def generate_demo(symbol: str = "DEMO", days: int = 200) -> pd.DataFrame
```

Génère une marche aléatoire OHLCV déterministe (seed basée sur le symbole).

## `indicators`

### `IndicatorManager`

```python
class IndicatorManager:
    def sma(df, period=20, column="Close") -> pd.Series
    def ema(df, period=20, column="Close") -> pd.Series
    def rsi(df, period=14, column="Close") -> pd.Series
    def macd(df, fast=12, slow=26, signal=9, column="Close") -> tuple[Series, Series, Series]
    def bollinger(df, period=20, std=2.0, column="Close") -> tuple[Series, Series, Series]
```

### `indicators.base`

```python
@dataclass
class PlotItem:
    label: str
    series: pd.Series
    color: str = "#d1d4dc"
    width: int = 2
    style: str = "solid"

@dataclass
class IndicatorResult:
    name: str
    kind: Literal["overlay", "subplot"] = "overlay"
    plots: list[PlotItem] = []
    height: int = 120
    hlines: list[tuple[float, str]] = []
    vlines: list[tuple[float, str]] = []
```

### `CustomIndicatorExecutor`

```python
class CustomIndicatorExecutor:
    def __init__(self, root: str | Path = "user_indicators")
    def load_module(self, path: Path) -> ModuleType
    def execute(self, mod, df: pd.DataFrame, params: dict | None = None)
```

### `CustomRegistry`

```python
@dataclass
class CustomIndicator:
    id: str
    name: str
    path: Path
    module: Any
    description: str = ""
    params: dict = {}

class CustomRegistry:
    def __init__(self, root: str = "user_indicators")
    def discover(self) -> dict[str, CustomIndicator]
    def compute(self, cid: str, df, params: dict | None = None) -> IndicatorResult
```

## `strategies`

### `strategies.base`

```python
class Side(Enum): LONG / SHORT / NEUTRAL

@dataclass(slots=True)
class Signal:
    time: pd.Timestamp
    side: Side
    entry: float
    sl: float
    tp1: float
    tp2: float | None = None
    confidence: int = 50
    setup_type: str = "price_action"
    reason: list[str] = []
    zone_price_low: float | None = None
    zone_price_high: float | None = None
    meta: dict[str, Any] = {}

@dataclass
class StrategyContext:
    df: pd.DataFrame
    symbol: str = ""
    timeframe: str = ""
    params: dict[str, Any] = {}

class BaseStrategy:
    id: str
    name: str
    description: str
    params_schema: dict
    def analyze(self, ctx: StrategyContext) -> list[Signal]
```

### `strategies.utils`

```python
def atr(df, period=14) -> pd.Series
def body(df) -> pd.Series
def range_hl(df) -> pd.Series
def is_bullish_engulfing(df, i: int) -> bool
def is_bearish_engulfing(df, i: int) -> bool
def is_pinbar_bull(df, i: int, ratio=2.0) -> bool
def is_pinbar_bear(df, i: int, ratio=2.0) -> bool
```

### `strategies.price_action.structure`

```python
@dataclass
class Swing:
    index: int
    price: float
    kind: Literal["HIGH", "LOW"]
    confirmed: bool = True

def find_swings(df, left=3, right=3) -> list[Swing]
def get_trend(swings) -> Literal["BULLISH", "BEARISH", "RANGE"]
def detect_bos_choch(df, swings) -> dict
```

### `strategies.price_action.patterns`

```python
def detect_reaction(df, i: int) -> dict
# {"bull": bool, "bear": bool, "types": list[str]}
```

### `strategies.price_action.zones`

```python
@dataclass
class Zone:
    kind: Literal["OB_BULL", "OB_BEAR", "LIQ"]
    top: float
    bottom: float
    index: int
    mitigated: bool = False
    strength: int = 50

def find_order_blocks(df, lookback=50) -> list[Zone]
def is_price_in_zone(price, zone) -> bool
def mitigate_zones(zones, df) -> list[Zone]
```

### `strategies.price_action.general`

```python
class PriceActionGeneral(BaseStrategy):
    id = "pa_general"
    name = "Price Action Général"
    params_schema = {...}
    def analyze(self, ctx: StrategyContext) -> list[Signal]
```

### `strategies.registry`

```python
@dataclass
class StrategyEntry:
    id: str
    name: str
    description: str
    instance: BaseStrategy
    source: str            # "builtin" | "user"
    path: Path | None
    params_schema: dict

class StrategyRegistry:
    def __init__(self, user_dir="strategies/user_strategies")
    def discover(self) -> dict[str, StrategyEntry]
    def get(self, sid: str) -> StrategyEntry | None
    def default_params(self, sid: str) -> dict
```

### `strategies.engine`

```python
class StrategyEngine:
    def __init__(self, registry: StrategyRegistry | None = None)
    def run(
        self,
        strategy_id: str,
        df: pd.DataFrame,
        *,
        symbol: str = "",
        timeframe: str = "",
        params: dict | None = None,
        filters: dict | None = None,
    ) -> list[Signal]
```

Filtres supportés : `side`, `min_confidence`, `min_rr`, `max_signals`.

## `charts.markers`

```python
def draw_signals(chart: ChartWidget, signals: list[Signal]) -> None
def clear_signal_items(chart: ChartWidget) -> None
```

Dessine / supprime flèches, labels, bandes de zone et lignes SL/TP sur le
graphique principal.

## `ui`

### `ChartWidget`

```python
class ChartWidget(QWidget):
    hoverInfo = Signal(str)

    def set_data(self, df: pd.DataFrame) -> None
    def add_overlay(self, series, name, color="#f0b90b", width=2) -> None
    def add_bollinger(self, upper, mid, lower) -> None
    def add_subplot(self, title, series_list, height=120, hlines=None)
    def clear_indicators(self) -> None
    def focus_on_time(self, ts, span=60) -> None
```

`series_list` : `list[tuple[label, pd.Series, color]]`.
`hlines` : `list[tuple[valeur, couleur]]`.

### `CandlestickItem`

```python
class CandlestickItem(pg.GraphicsObject):
    def __init__(self, data: np.ndarray)  # forme (N, 5) = [x, open, high, low, close]
```

Item pyqtgraph dessinant les chandeliers à partir d'un `QPicture`.

### `Toolbar`

```python
class Toolbar(QWidget):
    loadRequested = Signal(str, str, str)   # symbol, interval, period
    def set_status(self, text: str) -> None
```

### `IndicatorPanel`

```python
class IndicatorPanel(QWidget):
    indicatorsChanged = Signal(dict)
    clearRequested = Signal()
```

Structure du dictionnaire émis :

```python
{
  "sma": {"enabled": bool, "period": int},
  "ema": {"enabled": bool, "period": int},
  "bb":  {"enabled": bool, "period": int, "std": float},
  "rsi": {"enabled": bool, "period": int},
  "macd":{"enabled": bool, "fast": int, "slow": int, "signal": int},
}
```

### `CustomIndicatorPanel`

```python
class CustomIndicatorPanel(QWidget):
    applyCustom = Signal(str, dict)   # id, params
    clearCustom = Signal()
    def refresh(self) -> None
```

### `IndicatorEditorDialog`

```python
class IndicatorEditorDialog(QDialog):
    def __init__(self, parent=None, filename: str = "")
```

Écrit le fichier dans `user_indicators/` avec confirmation d'écrasement.

### `StrategyPanel`

```python
class StrategyPanel(QWidget):
    analyzeRequested = Signal(str, dict, dict)  # id, params, filters
    clearRequested = Signal()
    refreshRequested = Signal()                 # déclaré (non utilisé actuellement)

    def refresh_strategies(self) -> None
    def current_strategy_id(self) -> str | None
    def collect_params(self) -> dict
    def collect_filters(self) -> dict
    def set_result(self, count: int) -> None
```

### `SignalTable`

```python
class SignalTable(QWidget):
    signalActivated = Signal(object)       # Signal
    aiAnalysisRequested = Signal(object)   # Signal
    def set_signals(self, signals: list[Signal]) -> None
    def clear(self) -> None
```

Colonnes : `Heure, Sens, Setup, Entrée, SL, TP1, TP2, R:R, Conf., Raisons, IA`.

La colonne **IA** contient un bouton `Analyser IA` par ligne ; un clic émet
`aiAnalysisRequested(signal)`. Les boutons sont replacés après chaque tri du
tableau.

### `AIAnalysisDialog`

```python
class AIAnalysisDialog(QWidget):
    def __init__(
        self,
        sig: Signal,
        df: pd.DataFrame,
        *,
        symbol: str = "",
        timeframe: str = "",
        strategy_name: str = "",
        strategy_description: str = "",
        status: ollama_client.OllamaStatus | None = None,
        parent=None,
    )
```

Fenêtre indépendante : affiche le prompt exact (`prompt_view`), permet de
choisir le modèle Ollama, diffuse la réponse dans `answer` et propose
**Arrêter** / **Copier l'analyse**. L'analyse démarre automatiquement si un
modèle a déjà été utilisé (mémorisé via `QSettings`) ; sinon l'utilisateur
choisit le modèle puis lance l'analyse.

### `MainWindow`

```python
class MainWindow(QMainWindow):
    def load_data(self, symbol, interval, period) -> None
    def run_strategy(self, strategy_id, params, filters) -> None
    def clear_signals(self) -> None
    def focus_signal(self, sig) -> None
    def open_ai_analysis(self, sig) -> None
    def apply_indicators(self, cfg: dict) -> None
    def clear_indicators(self) -> None
    def apply_custom_indicator(self, cid: str, params: dict) -> None
    def clear_custom_indicators(self) -> None
```

Attributs notables : `current_df`, `current_symbol`, `current_interval`,
`signals`, `ai_dialogs`, `client`, `strategy_engine`, `strategy_registry`,
`custom_registry`.

`open_ai_analysis` vérifie Ollama (installé, démarré, modèles disponibles) et
affiche une boîte de dialogue explicite sinon ; dans le cas nominal, elle ouvre
une `AIAnalysisDialog` non modale et la conserve dans `ai_dialogs`.

## `utils.helpers`

```python
def df_to_candles(df) -> tuple[Index, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]
```

Retourne `(dates, opens, highs, lows, closes, volumes)`.

## Exemple headless

```python
from data.demo import generate_demo
from strategies.registry import StrategyRegistry
from strategies.engine import StrategyEngine

df = generate_demo("AAPL", days=300)

registry = StrategyRegistry()
registry.discover()

engine = StrategyEngine(registry)
signals = engine.run("pa_general", df, symbol="AAPL", timeframe="1d")

for s in signals:
    print(s.time, s.side.value, s.entry, s.sl, s.tp1, s.confidence, s.meta.get("rr"))
```
