# Indicateurs

Ce dossier contient **tous** les indicateurs du logiciel : les indicateurs
livrés par défaut (`sma.py`, `ema.py`, `bollinger.py`, `rsi.py`, `macd.py`) et
les indicateurs que tu écris toi-même. Le cœur du logiciel ne contient plus
aucun indicateur « en dur » : il fournit seulement le moteur de chargement.

Chaque fichier `.py` de ce dossier est détecté automatiquement et apparaît dans
l'onglet **Indicateurs** de l'application.

## Structure minimale

```python
import pandas as pd

NAME = "Mon indicateur"
DESCRIPTION = "Description courte"
PARAMS = {"period": 20}

def compute(df: pd.DataFrame, period: int = 20):
    from trading_matrix.indicators.base import IndicatorResult, PlotItem
    ma = df["Close"].rolling(period).mean()
    return IndicatorResult(
        name=f"SMA perso ({period})",
        kind="overlay",  # "overlay" sur le graphique prix ou "subplot" en dessous
        plots=[PlotItem(label="MA", series=ma, color="#f0b90b", width=2)],
    )
```

## Paramètres et interface

`PARAMS` décrit les paramètres de l'indicateur. Chaque entrée génère
automatiquement un widget dans le panneau. Deux formes sont acceptées :

```python
# Forme simple : le type est déduit de la valeur
PARAMS = {"period": 20}

# Forme détaillée : contrôle du widget (type, bornes, libellé)
PARAMS = {
    "period": {"type": "int", "default": 20, "min": 2, "max": 400, "label": "Période"},
    "std": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "step": 0.5, "label": "Écart-type"},
    "log": {"type": "bool", "default": False, "label": "Échelle log"},
    "color": {"type": "str", "default": "#f0b90b", "label": "Couleur"},
}
```

Types supportés : `int`, `float`, `bool`, `str`.

## Astuces

- `df` contient `Open`, `High`, `Low`, `Close`, `Volume` avec index datetime
- `kind="overlay"` s'affiche directement sur les bougies
- `kind="subplot"` crée un panneau séparé
- Tu peux importer `ta`, `numpy`, `pandas`
- Tu peux ajouter `hlines=[(70,"#ef5350"), (30,"#26a69a")]` (lignes horizontales)
- Recharge via le bouton **Rafraîchir** du panneau **Indicateurs**
- Crée un nouvel indicateur via **Nouveau...** (ouvre un éditeur pré-rempli)
