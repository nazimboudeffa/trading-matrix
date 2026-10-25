# Utilisation

## Interface

L'application s'ouvre sur une fenêtre unique organisée autour de trois zones :

```text
┌───────────────────────────────────────────────────────────────┐
│ Symbole [AAPL]  Intervalle [1d]  Période [6mo]  [Charger]     │  ← barre d'outils
├───────────────────────────────────────────────┬───────────────┤
│                                               │  Docks :      │
│              Graphique (bougies)              │  - Indicateurs│
│                                               │  - Mes ind.   │
│                                               │  - Stratégies │
├───────────────────────────────────────────────┤               │
│              Volume                           │               │
├───────────────────────────────────────────────┤               │
│   (sous-graphiques : RSI, MACD, indicateurs)  │               │
├───────────────────────────────────────────────┴───────────────┤
│  Signaux détectés (tableau)                                    │
├───────────────────────────────────────────────────────────────┤
│  Barre d'état                                                  │
└───────────────────────────────────────────────────────────────┘
```

## Barre d'outils

| Élément | Description |
| --- | --- |
| **Symbole** | Code du titre (`AAPL`, `MSFT`, `BTC-USD`...). `Entrée` déclenche le chargement. |
| **Intervalle** | `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1wk`, `1mo` |
| **Période** | `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `max` |
| **Charger** | Récupère les données et met à jour le graphique |
| **Statut** | Indique l'état de la source (`OpenBB/yfinance: OK` ou `DEMO`) |

> La disponibilité réelle des combinaisons intervalle/période dépend du provider.
> Par exemple, les données intraday sont souvent limitées à quelques jours.

## Graphique

### Navigation

| Action | Effet |
| --- | --- |
| Molette | Zoom horizontal et vertical |
| Clic gauche + glisser | Déplacement (pan) |
| Clic droit + glisser | Zoom sur une zone |
| Survol | Crosshair + OHLCV de la bougie sous le curseur |

Le volume et les sous-graphiques sont **synchronisés** horizontalement avec le
graphique principal : un zoom sur l'un s'applique aux autres.

### Affichage

- Bougies **vertes** : clôture ≥ ouverture
- Bougies **rouges** : clôture < ouverture
- Le panneau de volume utilise des couleurs atténuées
- Le label de survol affiche : date, Open, High, Low, Close, Volume

## Panneaux (docks)

Les trois panneaux sont empilés en onglets à droite et peuvent être détachés,
déplacés ou redimensionnés (comportement Qt standard).

### Onglet « Indicateurs »

Indicateurs intégrés, configurables puis appliqués avec **Appliquer**.

| Indicateur | Type | Paramètres |
| --- | --- | --- |
| SMA | Superposé au prix | Période |
| EMA | Superposé au prix | Période |
| Bandes de Bollinger | Superposé au prix | Période, écart-type |
| RSI | Sous-graphique | Période |
| MACD | Sous-graphique | Fast, Slow, Signal |

**Effacer tout** retire tous les indicateurs (intégrés et personnalisés) du
graphique. Les signaux de stratégie ne sont pas affectés.

### Onglet « Mes indicateurs »

Voir [Indicateurs personnalisés](indicateurs.md).

- **Nouveau...** ouvre un éditeur de code intégré
- **Rafraîchir** rescanne `user_indicators/`
- **Appliquer à la vue** exécute l'indicateur sélectionné
- **Effacer indicateurs perso** nettoie la vue

### Onglet « Stratégies »

Voir [Stratégies](strategies.md).

- Sélection de la stratégie
- Paramètres générés automatiquement
- Filtres d'affichage : sens, confiance minimale, R:R minimal, nombre max
- **Analyser le graphique**, **Effacer les signaux**, **Rafraîchir stratégies**

## Tableau des signaux

Chaque ligne correspond à un `Signal` :

| Colonne | Signification |
| --- | --- |
| Heure | Date/heure de la bougie de référence (dernière bougie pour un setup à venir) |
| Sens | `LONG` ou `SHORT` (coloré) |
| Statut | `Confirmé` ou **`En attente`** (setup conditionnel) |
| Setup | Identifiant du type de setup |
| Entrée | Prix d'entrée proposé |
| SL | Stop Loss |
| TP1 / TP2 | Objectifs de prise de profit |
| R:R | Ratio risque/rendement calculé |
| Conf. | Score de confluence (0-100) |
| Raisons | Détails lisibles (structure, zone, pattern...) |
| IA | Bouton **Analyser IA** : analyse le signal avec un modèle Ollama local |

Le tableau est **triable** en cliquant sur les en-têtes.

**Double-clic** sur une ligne : le graphique se recentre sur la bougie du signal
(environ 80 bougies autour). Pour un setup **En attente**, le recentrage se fait
sur la dernière bougie disponible, avec la projection à droite.

### Signaux à venir (statut « En attente »)

La stratégie Price Action peut afficher des **setups conditionnels** sur des
Order Blocks encore non testés (paramètre **Signaux à venir**). Ils ne sont pas
déclenchés : la ligne indique la zone, une entrée prévue (limite ou indicative),
le SL/TP et la condition de déclenchement dans les raisons.

- Sur le graphique : diamant creux ambre et zone pointillée projetés à droite
  de la dernière bougie.
- Dans le tableau : statut **En attente** (ambre), confiance plus basse qu'un
  signal confirmé.
- Le bouton **Analyser IA** fonctionne aussi : le prompt précise que le setup
  n'est pas déclenché et demande au modèle d'évaluer la condition.

Un setup peut ne jamais se déclencher, être invalidé si le prix traverse la zone
sans réaction, ou disparaître au prochain calcul. Voir
[Stratégie Price Action](strategie-price-action.md).

### Analyse IA d'un signal

Le bouton **Analyser IA** de chaque ligne ouvre une fenêtre séparée dans
laquelle un modèle Ollama analyse le signal (structure, confluence, risques,
gestion). L'application vérifie d'abord qu'Ollama est installé et démarré ; un
message explicite s'affiche sinon. Le modèle se choisit dans la fenêtre et est
mémorisé pour la prochaine analyse.

Le contexte exact envoyé au modèle est visible, et l'analyse est diffusée en
direct. Voir [Analyse IA](analyse-ia.md) pour l'installation et le détail du
prompt.

## Représentation des signaux sur le graphique

| Élément | Rendu |
| --- | --- |
| Signal LONG | Flèche verte vers le haut + label `L <confiance>%` |
| Signal SHORT | Flèche rouge vers le bas + label `S <confiance>%` |
| Signal à venir | Diamant creux ambre + label `L/S <confiance>% · à venir`, projeté à droite de la dernière bougie |
| Zone (Order Block) | Bande rectangulaire semi-transparente (pointillée pour un setup à venir) |
| SL | Ligne pointillée rouge |
| TP1 | Ligne pointillée verte |
| TP2 | Ligne pointillée vert clair |

## Barre d'état

Affiche :

- l'état de chargement (`Chargement AAPL 1d/6mo...`)
- le résumé après chargement (`AAPL | 126 bougies | 1d | 6mo`)
- le nombre de signaux détectés
- les messages d'action (signaux effacés, etc.)

## Comportements notables

- **Changement de données** : les signaux précédents sont effacés, les
  indicateurs actifs sont réappliqués automatiquement.
- **Aucune donnée réseau** : bascule silencieuse sur les données de démo.
- **Stratégie sans données chargées** : une boîte de dialogue demande de charger
  des données d'abord.
- **Persistance** : aucune sauvegarde automatique entre deux sessions
  (symbole, indicateurs, signaux). Voir [Dépannage](depannage.md) pour les
  évolutions possibles.

## Raccourcis utiles

| Raccourci | Action |
| --- | --- |
| `Entrée` dans le champ symbole | Charger |
| Double-clic sur un signal | Centrer le graphique |
| Clic sur un en-tête de colonne | Trier le tableau |
| Clic sur **Analyser IA** | Analyser le signal avec Ollama |
