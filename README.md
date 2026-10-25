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
  - **Signaux à venir** : setups conditionnels sur Order Blocks non testés, projetés à droite du graphique avec un statut « En attente »
  - Tableau des signaux avec navigation au double-clic
  - **Analyse IA locale** de chaque signal (confirmé ou à venir) via Ollama (fenêtre dédiée, choix du modèle)
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
├── core/                  # Configuration, palette, client Ollama, contexte IA
├── data/                  # Client OpenBB/yfinance + données démo
├── charts/                # Marqueurs de signaux (flèches, zones, SL/TP)
├── indicators/            # Indicateurs techniques + moteur perso
├── strategies/            # Moteur de stratégies
│   ├── base.py            # Signal, StrategyContext, BaseStrategy
│   ├── engine.py          # Exécution + filtres
│   ├── registry.py        # Registre built-in + perso
│   ├── price_action/      # Structure, patterns, zones, stratégie générale
│   └── user_strategies/   # Tes stratégies perso
├── ui/                    # Fenêtre, panneaux, éditeur, fenêtre d'analyse IA
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
- requests (client Ollama pour l'analyse IA)

## Analyse IA (optionnelle)

Les signaux peuvent être analysés par un modèle local via **Ollama**.
Installer Ollama (<https://ollama.com/download>), lancer `ollama serve` puis
télécharger un modèle (`ollama pull llama3.1`). Le bouton **Analyser IA** du
tableau des signaux ouvre une fenêtre dédiée avec le contexte du signal et la
réponse du modèle. Les setups **En attente** peuvent aussi être analysés : le
prompt indique qu'ils sont conditionnels et demande d'évaluer leur condition de
déclenchement. Voir [`doc/analyse-ia.md`](doc/analyse-ia.md).

## Remarques

- OpenBB yfinance fonctionne sans clé API pour la majorité des symboles actions/ETFs/crypto.
- Pour les intervalles intraday, certains symboles/actions peuvent limiter la période.
- Si `ta-lib` pose problème à l'installation (notamment sous Windows), l'implémentation utilise `ta` en fallback.
- Si OpenBB/yfinance échoue, l'app bascule sur des données de démo pour tester l'interface.

## AVERTISSEMENT IMPORTANT

> [!WARNING]
> **PROJET STRICTEMENT EDUCATIF ET EXPERIMENTAL**
>
> Ce projet est fourni exclusivement a des fins d'apprentissage, de demonstration technique et d'experimentation. Il ne constitue **en aucun cas** un conseil en investissement, une recommandation financiere, une incitation a acheter ou vendre un actif, ni une promesse de performance.
>
> Tout algorithme de trading, aussi convaincant, sophistique ou automatise soit-il, peut produire des signaux faux, tardifs, incoherents ou desastreux dans des conditions de marche reelles. Les marches financiers sont volatils, imprevisibles et peuvent reagir brutalement a des evenements que le modele ne comprend pas, n'anticipe pas ou interprete mal.
>
> **Vous pouvez perdre une partie importante de votre capital, voire la totalite de l'argent engage.** Cela inclut les pertes liees aux faux signaux, aux erreurs de parametrage, aux biais de donnees, aux problemes techniques, a la latence, aux conditions de liquidite, au spread, au slippage, a l'effet de levier et a toute defaillance logicielle ou humaine.
>
> N'utilisez jamais cet outil avec de l'argent que vous ne pouvez pas vous permettre de perdre integralement. Si vous choisissez de vous en servir dans un contexte reel, vous le faites **a vos seuls risques**, sous votre **entiere responsabilite**.
>
> En resume : **ce projet peut vous aider a explorer des idees, pas a securiser votre argent.** Si vous cherchez une garantie, il n'y en a aucune.