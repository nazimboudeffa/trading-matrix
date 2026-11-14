# Stratégies personnalisées

Chaque fichier `.py` de ce dossier est chargé automatiquement dans le panneau **Stratégies**.

## Contrat

```python
from strategies.base import BaseStrategy, Signal, Side, StrategyContext

class MaStrategie(BaseStrategy):
    id = "mon_id_unique"           # obligatoire, unique
    name = "Nom affiché"
    description = "Ce que fait la stratégie"
    params_schema = {
        "period": {"type": "int", "default": 20, "min": 5, "max": 200, "label": "Période"},
        "ratio": {"type": "float", "default": 1.5, "min": 0.5, "max": 5.0, "label": "Ratio"},
        "strict": {"type": "bool", "default": True, "label": "Mode strict"},
    }

    def analyze(self, ctx: StrategyContext) -> list[Signal]:
        df = ctx.df                       # OHLCV, index datetime
        p = ctx.params.get("period", 20)
        signals = []
        # ... logique ...
        return signals
```

## Signal

```python
Signal(
    time=df.index[i],
    side=Side.LONG,        # ou Side.SHORT
    entry=close,
    sl=stop_loss,
    tp1=take_profit_1,
    tp2=take_profit_2,     # optionnel
    confidence=70,         # 0-100
    setup_type="MON_SETUP",
    reason=["Structure haussière", "Rejet sur OB"],
    zone_price_low=zone_bottom,   # optionnel : dessine une bande
    zone_price_high=zone_top,
    meta={"rr": 2.1},             # optionnel
)
```

## Affichage

- Les signaux sont dessinés sur le graphique (flèche, label, SL/TP, zone)
- Ils apparaissent dans le tableau **Signaux détectés**
- Double-clic sur une ligne -> centrage sur le signal

## Conseils

- Utilise `strategies.utils` (`atr`, `is_bullish_engulfing`, etc.)
- Réutilise `strategies.price_action.structure` et `zones` si utile
- Évite le *lookahead bias* : ne regarde que `df.iloc[:i+1]` pour la bougie `i`
- Retourne une liste triée chronologiquement (le moteur retrie de toute façon)
