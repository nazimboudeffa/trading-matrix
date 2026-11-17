# Plan du projet (feuille de route)

Ce document décrit **où en est Trading Matrix** et **où il va**. Il sert de
référence commune pour prioriser le travail : on y coche ce qui est fait et on y
ajoute les idées au fil de l'eau.

Légende :

| Symbole | Signification |
| --- | --- |
| ✅ | Fait et livré |
| 🔜 | Prochaine étape (priorité haute) |
| 💡 | Idée / à planifier |
| 🚫 | Explicitement **hors périmètre** |

---

## 1. Vision

Un **visualiseur de trading desktop local**, extensible et pédagogique :

- graphiques clairs (bougies, volume, indicateurs) sans dépendre d'un service web ;
- un **système de définitions ouvert** : tout indicateur vit dans
  `user_indicators/`, toute stratégie dans `user_strategies/` ;
- une **analyse assistée** (signaux + analyse IA locale) pour **explorer des
  idées**, jamais pour sécuriser du capital.

## 2. Principes directeurs

1. **Cœur sans définitions** : le package `trading_matrix/` ne contient *aucun*
   indicateur ni stratégie en dur — seulement les moteurs et l'interface.
2. **Local d'abord** : cache disque, instantanés embarqués, Ollama. Pas de
   serveur, pas de compte, pas de clé API obligatoire.
3. **Interface en français**, thème sombre proche de TradingView.
4. **Séparation UI / logique** : les calculs (indicateurs, stratégies) sont
   indépendants de Qt et testables sans interface.
5. **Tests hors ligne** : la suite `pytest` ne fait aucun appel réseau.
6. **Honnêteté** : l'outil est éducatif ; il ne donne pas de conseil en
   investissement.

## 3. État actuel (✅ livré)

| Domaine | Détail |
| --- | --- |
| Graphique | Chandeliers + volume, crosshair OHLCV, zoom / pan, sous-graphiques synchronisés |
| Données | OHLCV via OpenBB → yfinance → données de démo ; normalisation des colonnes |
| Barre d'outils | Symbole, intervalle, période, **Charger** |
| Autocomplétion | Suggestions dès 2 caractères, navigation clavier, repli hors ligne |
| Fenêtre Marchés | Indices (Wikipédia, cache 7 j, seeds) **+ forex** (Majeures / Mineures / Exotiques, listes embarquées), filtre, tri, bouton **Sélectionner** |
| Indicateurs | Tous dans `user_indicators/` (SMA, EMA, Bollinger, RSI, MACD + exemple), panneau unifié, paramètres auto-générés, éditeur intégré |
| Stratégies | Moteur + `user_strategies/` (`pa_general`, `example_ema_cross_atr`) |
| Signaux | SL / TP1 / TP2 / TP3, R:R, score de confluence, **setups en attente**, tableau, navigation |
| Analyse IA | Ollama local : statut, choix du modèle, fenêtre dédiée, streaming, **actualités OpenBB optionnelles** |
| Qualité | 34 tests `pytest`, documentation complète dans `doc/` |

## 4. Feuille de route

### Phase 1 — Confort d'usage 🔜

Objectif : rendre le quotidien plus fluide, sans nouvelle brique lourde.

- 🔜 **Export** du graphique en **PNG** et des signaux en **CSV**
- 🔜 **Sauvegarde / restauration de session** : symbole, indicateurs actifs,
  stratégie, disposition des docks
- 🔜 **Raccourcis clavier** : charger, rafraîchir, appliquer les indicateurs
- 🔜 Mémoriser le **dernier marché** sélectionné et la **géométrie** de la
  fenêtre Marchés
- 💡 Indicateur de **fraîcheur des données** (dernière bougie, source réelle)
- 💡 Barre d'état enrichie : latence, provenance (OpenBB / yfinance / démo)

### Phase 2 — Analyse & évaluation 🔜

Objectif : juger la qualité des signaux, pas seulement les afficher.

- 🔜 **Backtest simple** d'une stratégie : nombre de signaux, taux de réussite,
  **R multiple** moyen, courbe d'equity (sur l'historique chargé)
- 🔜 **Confluence multi-timeframe** : filtrer les signaux selon la tendance d'une
  unité de temps supérieure
- 🔜 **Zones de liquidité** (sommets / creux égaux) comme cibles de TP
- 💡 Métriques par signal : distance au SL/TP, volatilité (ATR), ancienneté
- 💡 **Comparaison de stratégies** côte à côte sur le même historique

### Phase 3 — Alertes & suivi 💡

Objectif : être prévenu, sans rester devant l'écran.

- 💡 **Alerte sur nouveau signal** (notification système, son optionnel)
- 💡 **Rafraîchissement automatique** périodique + détection de nouveauté
- 💡 **Watchlist** personnalisée (liste de symboles suivis)
- 💡 **Journal des signaux** : historique local (JSON/SQLite), filtrable

### Phase 4 — Extensions 💡

Objectif : élargir la couverture et les outils.

- 💡 Nouvelles familles d'actifs dans la fenêtre Marchés (crypto, matières
  premières, ETF) sur le même modèle que le forex (listes statiques)
- 💡 Indicateurs supplémentaires : VWAP, ATR, SuperTrend, Ichimoku, volume
  profile
- 💡 Stratégies supplémentaires : mean reversion, breakout de range,
  suivi de tendance
- 💡 **Multi-graphiques / multi-symboles** (grille)
- 💡 **Thème clair** (bascule dans les préférences)

### Phase 5 — Qualité & diffusion 💡

Objectif : fiabiliser et faciliter le partage.

- 💡 Tests d'interface (`pytest-qt`) sur les panneaux clés
- 💡 **Packaging** exécutable (PyInstaller) — le code gère déjà le mode `frozen`
- 💡 **CI** GitHub Actions : `compileall` + `pytest` à chaque push
- 💡 Internationalisation (l'interface est aujourd'hui en français en dur)

## 5. Backlog (idées en vrac)

- Comparer deux symboles sur un même graphique (corrélation, spread).
- Mode « replay » : avancer bougie par bougie pour étudier un setup.
- Annotations manuelles (lignes, rectangles) sauvegardées par symbole.
- Raccourci pour basculer rapidement entre plusieurs symboles récents.
- Indicateurs composites (un fichier qui en combine plusieurs).
- Score de qualité global d'un signal (structure + volume + volatilité + IA).

## 6. Hors périmètre 🚫

Pour rester clair sur la vocation du projet :

- 🚫 **Exécution d'ordres** / connexion à un broker (pas de trading automatique)
- 🚫 Conseils en investissement, gestion de portefeuille réel
- 🚫 Backend multi-utilisateurs, comptes, synchronisation cloud
- 🚫 Données temps réel payantes / flux tick par tick

> [!WARNING]
> Rappel : projet **strictement éducatif et expérimental**. Aucun élément de
> cette feuille de route ne transforme l'outil en conseil financier.

## 7. Suivi

- On coche 🔜 → ✅ quand c'est livré (et on ajuste la ligne « État actuel »).
- Toute nouvelle idée est ajoutée au backlog avant d'être planifiée.
- Un jalon important peut devenir une entrée dans le `CHANGELOG` (à créer) ou
  un lot de commits dédié.
