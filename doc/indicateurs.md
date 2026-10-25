# Indicateurs

Le projet propose deux familles d'indicateurs :

- les **indicateurs intégrés** (calculés par `IndicatorManager`)
- les **indicateurs personnalisés**, chargés depuis `user_indicators/`

Les deux s'affichent de la même manière : soit **superposés au prix**
(`overlay`), soit dans un **sous-graphique** dédié (`subplot`).

## Indicateurs intégrés

Implémentation : `indicators/manager.py`.

| Méthode | Signature | Retour |
| --- | --- | --- |
| `sma` | `sma(df, period=20, column="Close")` | `pd.Series` |
| `ema` | `ema(df, period=20, column="Close")` | `pd.Series` |
| `rsi` | `rsi(df, period=14, column="Close")` | `pd.Series` (0-100) |
| `macd` | `macd(df, fast=12, slow=26, signal=9, column="Close")` | tuple `(macd, signal, histogram)` |
| `bollinger` | `bollinger(df, period=20, std=2.0, column="Close")` | tuple `(upper, mid, lower)` |

### Détails de calcul

- **SMA** : moyenne mobile simple (`rolling(period).mean()`)
- **EMA** : moyenne mobile exponentielle (`ewm(span=period, adjust=False)`)
- **RSI** : via `ta` si disponible, sinon moyenne simple des gains/pertes
- **MACD** : via `ta` si disponible, sinon `EMA(fast) - EMA(slow)` +
  signal `EMA(signal)` et histogramme `MACD - Signal`
- **Bollinger** : via `ta` si disponible, sinon `SMA ± std × écart-type roulant`

### Rendu

- SMA, EMA, Bollinger → **overlay** sur le graphique principal
- RSI → **subplot** (hauteur ~110 px)
- MACD → **subplot** (hauteur ~130 px)

Le RSI intégré affiche également des lignes à 70 et 30 (séries constantes).

## Indicateurs personnalisés

### Emplacement

Tous les fichiers `.py` de `user_indicators/` sont scannés, sauf ceux
commençant par `_`. Un fichier = un indicateur.

### Contrat d'un fichier

```python
import pandas as pd

NAME = "Nom affiché"
DESCRIPTION = "Description courte"
PARAMS = {"period": 20}   # valeurs par défaut passées à compute()

def compute(df: pd.DataFrame, period: int = 20):
    ...
    return IndicatorResult(...)
```

| Élément | Rôle |
| --- | --- |
| `NAME` | Nom affiché dans la liste (défaut : nom du fichier) |
| `DESCRIPTION` | Texte affiché sous la liste |
| `PARAMS` | Paramètres par défaut (dictionnaire) |
| `compute(df, **params)` | **Obligatoire**. Reçoit le DataFrame OHLCV et les paramètres |

Le `DataFrame` reçu contient :

- index : `DatetimeIndex`
- colonnes : `Open`, `High`, `Low`, `Close`, `Volume` (et parfois `Adj Close`)

### Objets de retour

#### `IndicatorResult`

```python
from indicators.base import IndicatorResult, PlotItem

IndicatorResult(
    name="Mon indicateur",
    kind="overlay",           # "overlay" ou "subplot"
    plots=[PlotItem(...)],
    height=120,               # hauteur du subplot en pixels
    hlines=[(70, "#ef5350"), (30, "#26a69a")],  # lignes horizontales (subplot)
    vlines=[],                # réservé
)
```

#### `PlotItem`

```python
PlotItem(
    label="SMA20",
    series=ma,          # pd.Series alignée sur l'index du DataFrame
    color="#f0b90b",
    width=2,            # utilisé pour les overlays
    style="solid",      # réservé (solid/dash)
)
```

#### Retour par dictionnaire

Pour alléger l'écriture, `compute()` peut retourner un `dict` :

```python
def compute(df, period=20):
    ma = df["Close"].rolling(period).mean()
    return {
        "name": f"SMA {period}",
        "kind": "overlay",
        "plots": [
            ("SMA", ma, "#f0b90b"),        # (label, series, color)
        ],
    }
```

Formats de tuple acceptés pour `plots` :

- `(label, series)` → couleur par défaut
- `(label, series, color)`
- `(label, series, color, width)`

### Exemples

#### Overlay — croisement de moyennes

Voir `user_indicators/example_cross_ma.py` :

```python
import pandas as pd

NAME = "Croisement MA Rapide/Lente"
DESCRIPTION = "Affiche SMA rapide et lente"
PARAMS = {"fast": 10, "slow": 30}

def compute(df: pd.DataFrame, fast: int = 10, slow: int = 30):
    from indicators.base import IndicatorResult, PlotItem
    sma_fast = df["Close"].rolling(fast).mean()
    sma_slow = df["Close"].rolling(slow).mean()
    return IndicatorResult(
        name=f"MA Croisement ({fast}/{slow})",
        kind="overlay",
        plots=[
            PlotItem(label=f"SMA{fast}", series=sma_fast, color="#f0b90b"),
            PlotItem(label=f"SMA{slow}", series=sma_slow, color="#2962ff"),
        ],
    )
```

#### Subplot — RSI maison avec lignes de référence

```python
import pandas as pd

NAME = "RSI maison"
DESCRIPTION = "RSI simple avec zones 70/30"
PARAMS = {"period": 14}

def compute(df: pd.DataFrame, period: int = 14):
    from indicators.base import IndicatorResult, PlotItem
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return IndicatorResult(
        name=f"RSI ({period})",
        kind="subplot",
        plots=[PlotItem(label="RSI", series=rsi, color="#9c27b0")],
        height=110,
        hlines=[(70, "#ef5350"), (30, "#26a69a")],
    )
```

### Éditeur intégré

L'onglet **Mes indicateurs** contient un bouton **Nouveau...** qui ouvre un
éditeur avec un template prêt à modifier.

1. Saisir un nom de fichier (`.py` ajouté automatiquement)
2. Écrire / coller le code
3. **Enregistrer** → écrit dans `user_indicators/`
4. **Rafraîchir** dans le panneau pour recharger la liste

Le bouton **Ouvrir dossier** ouvre `user_indicators/` dans l'explorateur.

### Cycle de vie et erreurs

| Situation | Comportement |
| --- | --- |
| Erreur d'import au chargement | Message dans la console Python, fichier ignoré |
| `compute` absent | Erreur affichée à l'application de l'indicateur |
| Exception dans `compute` | Boîte de dialogue d'erreur |
| Colonne manquante | Exception Python remontée dans la boîte de dialogue |
| Retour invalide | `TypeError` explicite |

Les paramètres (`PARAMS`) sont envoyés tels quels lors de l'application.
Il n'existe pas encore d'interface de réglage dynamique pour les indicateurs
personnalisés : modifie `PARAMS` dans le fichier puis **Rafraîchir**.

### Sécurité

Le code des indicateurs personnalisés est **exécuté localement avec les
privilèges Python complets**. Il n'y a pas de bac à sable. N'exécute que du
code que tu as écrit ou dont tu comprends le contenu.

### Bonnes pratiques

- Ne jamais utiliser de données futures : travaille uniquement avec le
  `DataFrame` fourni.
- Retourner des séries **alignées sur l'index** du DataFrame (même longueur).
- Éviter les impressions console dans `compute` (appelé à chaque application).
- Pour les calculs lourds, préférer les opérations vectorisées pandas/numpy.
