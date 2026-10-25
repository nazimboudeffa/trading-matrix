# Documentation — Trading Matrix

Bienvenue dans la documentation du projet **Trading Matrix**, un visualiseur de graphiques de trading desktop écrit en Python.

## Sommaire

| Document | Contenu |
| --- | --- |
| [Installation](installation.md) | Prérequis, environnement virtuel, dépendances, lancement |
| [Architecture](architecture.md) | Vue d'ensemble, organisation des dossiers, flux de données |
| [Utilisation](utilisation.md) | Guide de l'interface, chargement des données, indicateurs, stratégies |
| [Indicateurs](indicateurs.md) | Indicateurs intégrés et création d'indicateurs personnalisés |
| [Stratégies](strategies.md) | Moteur de stratégies, API `BaseStrategy`, création de stratégies perso |
| [Stratégie Price Action](strategie-price-action.md) | Fonctionnement détaillé de la stratégie générale |
| [Analyse IA](analyse-ia.md) | Analyse des signaux avec Ollama : installation, fenêtre, prompt |
| [Référence API](api-reference.md) | Classes, fonctions et signatures principales |
| [Dépannage](depannage.md) | Problèmes fréquents et solutions |

## En bref

Trading Matrix repose sur trois briques :

1. **PySide6** pour l'interface desktop native (fenêtres, docks, widgets)
2. **pyqtgraph** pour le rendu performant des chandeliers, volumes et indicateurs
3. **OpenBB / yfinance** pour le chargement des données OHLCV

Le projet est conçu pour être **extensible** :

- `user_indicators/` : ajoute tes propres indicateurs en Python
- `strategies/user_strategies/` : ajoute tes propres stratégies de trading

Aucune base de données ni serveur n'est nécessaire : tout tourne localement.

## Démarrage rapide

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Puis, dans l'application :

1. Saisis un symbole (`AAPL`, `MSFT`, `BTC-USD`...)
2. Clique sur **Charger**
3. Ouvre l'onglet **Stratégies** → **Analyser le graphique**

Les signaux détectés s'affichent sur le graphique et dans le tableau en bas.
