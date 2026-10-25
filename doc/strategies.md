# Stratégies

Une stratégie analyse un `DataFrame` OHLCV et retourne une liste de `Signal`.
Elle est indépendante de l'interface : elle peut être testée en dehors de Qt.

## Composants

| Fichier | Rôle |
| --- | --- |
| `strategies/base.py` | `Side`, `Signal`, `StrategyContext`, `BaseStrategy` |
| `strategies/engine.py` | `StrategyEngine` : exécution + filtres |
| `strategies/registry.py` | `StrategyRegistry` : découverte built-in + perso |
| `strategies/utils.py` | ATR, engulfing, pinbar, helpers |
| `strategies/price_action/` | Modules de la stratégie Price Action |
| `strategies/user_strategies/` | Stratégies personnalisées |

## Modèle de données

### `Side`

```python
class Side(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"
```

### `Signal`

```python
@dataclass(slots=True)
class Signal:
    time: pd.Timestamp
    side: Side
    entry: float
    sl: float
    tp1: float
    tp2: float | None = None
    confidence: int = 50               # 0-100
    setup_type: str = "price_action"
    reason: list[str] = []
    zone_price_low: float | None = None
    zone_price_high: float | None = None
    meta: dict = {}
```

| Champ | Obligatoire | Rôle |
| --- | --- | --- |
| `time` | oui | Timestamp de la bougie de signal (doit exister dans l'index) |
| `side` | oui | Sens du trade |
| `entry` | oui | Prix d'entrée |
| `sl` | oui | Stop Loss |
| `tp1` | oui | Premier objectif |
| `tp2` | non | Second objectif |
| `confidence` | non | Score de confluence |
| `setup_type` | non | Identifiant du setup (affiché dans le tableau) |
| `reason` | non | Liste de raisons lisibles |
| `zone_price_low/high` | non | Si renseignés, une bande est dessinée sur le graphique |
| `meta` | non | Données libres (`rr`, `atr`, etc.) |

Le moteur utilise `meta["rr"]` pour le filtrage R:R.

L'interface ajoute aussi `strategy_id`, `strategy_name`, `symbol` et
`timeframe` dans `meta` après l'analyse : ces informations servent de contexte
à l'[analyse IA](analyse-ia.md).

### `StrategyContext`

```python
@dataclass
class StrategyContext:
    df: pd.DataFrame
    symbol: str = ""
    timeframe: str = ""
    params: dict = {}
```

### `BaseStrategy`

```python
class BaseStrategy:
    id: str = "base"
    name: str = "Base Strategy"
    description: str = ""
    params_schema: dict = {}

    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        raise NotImplementedError
```

## `params_schema`

Les paramètres sont déclarés dans un dictionnaire et génèrent automatiquement
des widgets dans le panneau **Stratégies**.

```python
params_schema = {
    "period":  {"type": "int",   "default": 20,  "min": 5,   "max": 200, "label": "Période"},
    "ratio":   {"type": "float", "default": 1.5, "min": 0.5, "max": 5.0, "step": 0.1, "label": "Ratio"},
    "strict":  {"type": "bool",  "default": True, "label": "Mode strict"},
}
```

| Type | Widget |
| --- | --- |
| `int` | `QSpinBox` |
| `float` | `QDoubleSpinBox` |
| `bool` | `QCheckBox` |
| `str` | `QLineEdit` |

Clés reconnues : `type`, `default`, `min`, `max`, `step`, `label`.

## Registre

`StrategyRegistry` scanne :

1. les stratégies **intégrées** (`_builtin_strategies()`)
2. les fichiers `.py` de `strategies/user_strategies/` (hors `_*.py`)

Pour chaque fichier perso, toutes les classes héritant de `BaseStrategy`
(autres que `BaseStrategy` elle-même) sont instanciées et enregistrées par
leur `id`. **Un `id` doit être unique** : en cas de collision, la dernière
stratégie chargée écrase la précédente.

```python
registry = StrategyRegistry()
registry.discover()
registry.items          # dict[id, StrategyEntry]
registry.get("pa_general")
registry.default_params("pa_general")
```

`StrategyEntry` expose : `id`, `name`, `description`, `instance`, `source`
(`builtin` / `user`), `path`, `params_schema`.

## Moteur

```python
engine = StrategyEngine(registry)
signals = engine.run(
    "pa_general",
    df,
    symbol="AAPL",
    timeframe="1d",
    params={"min_rr": 1.5},
    filters={
        "side": "LONG",          # "LONG" | "SHORT" | None
        "min_confidence": 60,
        "min_rr": 1.2,
        "max_signals": 20,
    },
)
```

Étapes :

1. récupération de la stratégie
2. fusion des paramètres (`default_params` puis `params`)
3. appel de `instance.analyze(ctx)`
4. filtrage des signaux
5. tri chronologique

Les filtres sont **cumulatifs** avec les seuils internes de la stratégie.

## Créer une stratégie personnalisée

### 1. Créer le fichier

Exemple `strategies/user_strategies/ma_strategie.py` :

```python
from strategies.base import BaseStrategy, Side, Signal, StrategyContext
from strategies.utils import atr

class MaStrategie(BaseStrategy):
    id = "ma_strategie"
    name = "Ma stratégie"
    description = "Croisement de prix avec une EMA"
    params_schema = {
        "period": {"type": "int", "default": 20, "min": 5, "max": 200, "label": "Période"},
    }

    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        df = ctx.df
        period = int(ctx.params.get("period", 20))
        ema = df["Close"].ewm(span=period, adjust=False).mean()
        atr_series = atr(df, 14)

        signals = []
        for i in range(period + 1, len(df)):
            prev_close, close = df["Close"].iloc[i - 1], df["Close"].iloc[i]
            a = atr_series.iloc[i]
            if not (prev_close < ema.iloc[i - 1] and close > ema.iloc[i]):
                continue
            if a != a:  # NaN
                continue

            sl = close - 1.5 * float(a)
            risk = close - sl
            signals.append(
                Signal(
                    time=df.index[i],
                    side=Side.LONG,
                    entry=float(close),
                    sl=sl,
                    tp1=close + 2 * risk,
                    confidence=60,
                    setup_type="EMA_RECLAIM",
                    reason=[f"Clôture au-dessus de l'EMA{period}"],
                    meta={"rr": 2.0},
                )
            )
        return signals
```

### 2. Recharger

Dans le panneau **Stratégies**, cliquer sur **Rafraîchir stratégies**.
La stratégie apparaît dans la liste et ses paramètres sont générés.

### 3. Analyser

Sélectionner la stratégie → **Analyser le graphique**.

## Bonnes pratiques

- **Pas de lookahead** : pour la bougie `i`, n'utiliser que `df.iloc[:i+1]`
  (ou des séries causales comme EMA/ATR).
- Vérifier les `NaN` (`atr`, moyennes) avant de générer un signal.
- Éviter les signaux redondants : appliquer un *cooldown* ou n'autoriser qu'un
  signal par zone.
- Retourner des `time` présents dans l'index (sinon le marqueur est ignoré).
- Documenter `description` et `reason` : ils sont visibles dans l'interface.
- Tester la stratégie hors UI :

```python
from data.demo import generate_demo
from strategies.registry import StrategyRegistry
from strategies.engine import StrategyEngine

registry = StrategyRegistry(); registry.discover()
engine = StrategyEngine(registry)
df = generate_demo("TEST", days=300)
signals = engine.run("ma_strategie", df)
print(len(signals))
```

## Exemple fourni

`strategies/user_strategies/example_ema_cross_atr.py` implémente un croisement
EMA rapide/lente avec SL basé sur l'ATR. Il sert de modèle complet.

## Limites actuelles

- Pas de **backtest** intégré (winrate, R moyen, equity curve)
- Pas de **multi-timeframe** (confluence HTF/LTF)
- Pas d'**alertes** ni de persistance
- L'analyse s'exécute sur le thread UI ; les très gros historiques peuvent
  ralentir l'interface
- Les stratégies perso sont chargées par `importlib` : une erreur de syntaxe
  empêche leur découverte (message en console)
