# Indicateurs

Tous les indicateurs du logiciel vivent dans le dossier `user_indicators/` :
les indicateurs **livrés par défaut** et ceux que tu écris toi-même. Le cœur
du logiciel (`trading_matrix/indicators/`) ne contient **aucun indicateur en
dur** : il fournit uniquement le moteur de chargement.

Ils s'affichent de la même manière : soit **superposés au prix** (`overlay`),
soit dans un **sous-graphique** dédié (`subplot`).

## Indicateurs livrés par défaut

| Fichier | Nom | Type | Paramètres |
| --- | --- | --- | --- |
| `sma.py` | SMA | overlay | `period`, `color` |
| `ema.py` | EMA | overlay | `period`, `color` |
| `bollinger.py` | Bandes de Bollinger | overlay | `period`, `std` |
| `rsi.py` | RSI | subplot | `period` |
| `macd.py` | MACD | subplot | `fast`, `slow`, `signal` |

### Détails de calcul

- **SMA** : moyenne mobile simple (`rolling(period).mean()`)
- **EMA** : moyenne mobile exponentielle (`ewm(span=period, adjust=False)`)
- **Bollinger** : `SMA ± std × écart-type roulant`
- **RSI** : moyenne simple des gains/pertes, borné 0-100, lignes 70/30
- **MACD** : `EMA(fast) - EMA(slow)` + signal `EMA(signal)` + histogramme

### Rendu

- SMA, EMA, Bollinger → **overlay** sur le graphique principal
- RSI → **subplot** (hauteur ~110 px, lignes 70/30)
- MACD → **subplot** (hauteur ~130 px)

## Créer un indicateur

### Emplacement

Tous les fichiers `.py` de `user_indicators/` sont scannés, sauf ceux
commençant par `_`. Un fichier = un indicateur.

### Contrat d'un fichier

```python
import pandas as pd

NAME = "Nom affiché"
DESCRIPTION = "Description courte"
PARAMS = {"period": 20}

def compute(df: pd.DataFrame, period: int = 20):
    ...
    return IndicatorResult(...)
```

| Élément | Rôle |
| --- | --- |
| `NAME` | Nom affiché dans la liste (défaut : nom du fichier) |
| `DESCRIPTION` | Texte affiché sous le nom et en infobulle |
| `PARAMS` | Description des paramètres (voir ci-dessous) |
| `compute(df, **params)` | **Obligatoire**. Reçoit le DataFrame OHLCV et les paramètres |

Le `DataFrame` reçu contient :

- index : `DatetimeIndex`
- colonnes : `Open`, `High`, `Low`, `Close`, `Volume` (et parfois `Adj Close`)

### Paramètres (`PARAMS`)

Chaque entrée de `PARAMS` génère automatiquement un widget dans le panneau
**Indicateurs**. Deux formes sont acceptées :

```python
# Forme simple : le type est déduit de la valeur
PARAMS = {"period": 20}

# Forme détaillée : contrôle du widget (type, bornes, libellé, pas)
PARAMS = {
    "period": {"type": "int", "default": 20, "min": 2, "max": 400, "label": "Période"},
    "std": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "step": 0.5, "label": "Écart-type"},
    "log": {"type": "bool", "default": False, "label": "Échelle log"},
    "color": {"type": "str", "default": "#f0b90b", "label": "Couleur"},
}
```

| Type | Widget généré |
| --- | --- |
| `int` | `QSpinBox` (borné par `min`/`max`, pas `step`) |
| `float` | `QDoubleSpinBox` (borné par `min`/`max`, pas `step`) |
| `bool` | `QCheckBox` |
| `str` | `QLineEdit` |

Le libellé affiché est `label` (sinon le nom de la clé).

### Objets de retour

#### `IndicatorResult`

```python
from trading_matrix.indicators.base import IndicatorResult, PlotItem

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
    from trading_matrix.indicators.base import IndicatorResult, PlotItem
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
PARAMS = {"period": {"type": "int", "default": 14, "min": 2, "max": 100, "label": "Période"}}

def compute(df: pd.DataFrame, period: int = 14):
    from trading_matrix.indicators.base import IndicatorResult, PlotItem
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

Le panneau **Indicateurs** contient un bouton **Nouveau...** qui ouvre un
éditeur avec un template prêt à modifier.

1. Saisir un nom de fichier (`.py` ajouté automatiquement)
2. Écrire / coller le code
3. **Enregistrer** → écrit dans `user_indicators/`
4. **Rafraîchir** dans le panneau pour recharger la liste

Le bouton **Ouvrir le dossier** ouvre `user_indicators/` dans l'explorateur.

### Cycle de vie et erreurs

| Situation | Comportement |
| --- | --- |
| Erreur d'import au chargement | Message dans la console Python, fichier ignoré |
| `compute` absent | Erreur affichée à l'application de l'indicateur |
| Exception dans `compute` | Boîte de dialogue d'erreur |
| Colonne manquante | Exception Python remontée dans la boîte de dialogue |
| Retour invalide | `TypeError` explicite |

### Sécurité

Le code des indicateurs est **exécuté localement avec les privilèges Python
complets**. Il n'y a pas de bac à sable. N'exécute que du code que tu as écrit
ou dont tu comprends le contenu.

### Bonnes pratiques

- Ne jamais utiliser de données futures : travaille uniquement avec le
  `DataFrame` fourni.
- Retourner des séries **alignées sur l'index** du DataFrame (même longueur).
- Éviter les impressions console dans `compute` (appelé à chaque application).
- Pour les calculs lourds, préférer les opérations vectorisées pandas/numpy.
