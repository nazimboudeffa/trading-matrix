# Trading Matrix

Visualiseur de graphiques de trading desktop, construit avec **PySide6**, **pyqtgraph** et **OpenBB** (via `openbb-yfinance`).

## Fonctionnalités (MVP)

- Graphique en bougies japonaises + volume
- Chargement OHLCV via OpenBB / yfinance
- Barre d'outils : symbole, intervalle (1m, 5m, 15m, 1h, 1d, 1w), période (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y)
- Panneau indicateurs : SMA, EMA, RSI, MACD, Bandes de Bollinger
- Indicateurs personnalisés (dossier `user_indicators/`)
- **Stratégies** : moteur d'analyse avec stratégie Price Action générale
  - Structure de marché (swings, tendance)
  - Order Blocks non mitigés
  - Confirmations Price Action (engulfing, pinbar)
  - Signaux avec SL/TP, R:R et score de confluence
  - Affichage flèches / zones / SL / TP sur le graphique
  - Tableau des signaux avec navigation au double-clic
- Stratégies personnalisées (dossier `strategies/user_strategies/`)
- Thème sombre proche de TradingView
- Crosshair avec informations OHLCV
- Zoom / Pan

## Documentation

La documentation complète est disponible dans [`doc/`](doc/README.md) :
installation, architecture, utilisation, indicateurs, stratégies et dépannage.

## Installation

```bash
# 1) Créer et activer un environnement virtuel
python -m venv .venv
.\.venv\Scripts\activate        # Windows
# source .venv/bin/activate     # Linux/Mac

# 2) Installer les dépendances
pip install -r requirements.txt

# 3) Lancer l'application
python app.py
```

## Structure

```text
trading-matrix/
├── app.py
├── core/                  # Configuration, palette
├── data/                  # Client OpenBB/yfinance + données démo
├── charts/                # Marqueurs de signaux (flèches, zones, SL/TP)
├── indicators/            # Indicateurs techniques + moteur perso
├── strategies/            # Moteur de stratégies
│   ├── base.py            # Signal, StrategyContext, BaseStrategy
│   ├── engine.py          # Exécution + filtres
│   ├── registry.py        # Registre built-in + perso
│   ├── price_action/      # Structure, patterns, zones, stratégie générale
│   └── user_strategies/   # Tes stratégies perso
├── ui/                    # Fenêtre, panneaux, éditeur
├── user_indicators/       # Tes indicateurs perso
├── utils/
└── requirements.txt
```

## Indicateurs personnalisés

Chaque fichier `.py` dans `user_indicators/` doit exposer `compute(df, **params)`
et retourner un `IndicatorResult` (`overlay` ou `subplot`).
Voir `user_indicators/README.md`.

## Stratégies personnalisées

Chaque fichier `.py` dans `strategies/user_strategies/` doit définir une classe
héritant de `BaseStrategy` avec un `id` unique et une méthode
`analyze(ctx) -> list[Signal]`. Voir `strategies/user_strategies/README.md`.

Exemple fourni : `example_ema_cross_atr.py`.

## Dépendances principales

- PySide6
- pyqtgraph
- openbb
- openbb-yfinance
- pandas
- numpy
- ta

## Remarques

- OpenBB yfinance fonctionne sans clé API pour la majorité des symboles actions/ETFs/crypto.
- Pour les intervalles intraday, certains symboles/actions peuvent limiter la période.
- Si `ta-lib` pose problème à l'installation (notamment sous Windows), l'implémentation utilise `ta` en fallback.
- Si OpenBB/yfinance échoue, l'app bascule sur des données de démo pour tester l'interface.
