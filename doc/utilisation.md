# Utilisation

## Interface

L'application s'ouvre sur une fenêtre organisée autour de trois zones : le
graphique au centre, les docks **Indicateurs** et **Stratégies** à droite et le
tableau des signaux en bas. La liste des marchés s'ouvre dans une fenêtre
séparée via le bouton **Marchés** de la barre d'outils.

```text
┌───────────────────────────────────────────────────────────────┐
│ [Marchés] Symbole [AAPL]  Intervalle [1d]  Période [6mo]  [Charger] │  ← barre d'outils
├───────────────────────────────────────────────┬───────────────┤
│                                               │  Docks :      │
│              Graphique (bougies)              │  - Indicateurs│
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
| **Symbole** | Code du titre (`AAPL`, `MSFT`, `BTC-USD`...). Une liste de suggestions s'ouvre dès 2 caractères ; `Entrée` déclenche le chargement. |
| **Intervalle** | `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1wk`, `1mo` |
| **Période** | `1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `max` |
| **Charger** | Récupère les données et met à jour le graphique |
| **Marchés** | Ouvre la fenêtre des marchés (indices et forex) |
| **Statut** | Indique l'état de la source (`OpenBB/yfinance: OK` ou `DEMO`) |

> La disponibilité réelle des combinaisons intervalle/période dépend du provider.
> Par exemple, les données intraday sont souvent limitées à quelques jours.

### Autocomplétion du symbole

Dès **2 caractères** saisis, une liste de suggestions apparaît sous le champ
après un court délai (300 ms). Chaque ligne affiche le symbole, le nom et la
place de cotation (`AIR.PA   Airbus SE (Paris)`). Seul le **symbole** est inséré
dans le champ ; le nom n'est qu'indicatif.

| Action | Effet |
| --- | --- |
| Saisie (2 caractères minimum) | Recherche réseau après 300 ms |
| `↑` / `↓` | Navigue dans les suggestions |
| `Entrée` | Insère le symbole et charge le graphique |
| `Tab` | Insère le symbole sans charger |
| `Échap` | Ferme la liste |
| Clic simple | Insère le symbole sans charger |
| Double-clic | Insère le symbole et charge |

La recherche passe par `yfinance` et privilégie les places principales (Paris,
XETRA, Londres, Milan, Amsterdam, NYSE, Nasdaq, Suisse) devant les cotations
secondaires et le marché de gré à gré. Hors ligne, l'application se rabat sur les
listes de marchés embarquées.

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

Les panneaux **Indicateurs** et **Stratégies** sont empilés en onglets à droite.
Ils peuvent être détachés, déplacés ou redimensionnés (comportement Qt standard).

### Fenêtre « Marchés »

Le bouton **Marchés** de la barre d'outils ouvre une fenêtre séparée **non
modale** contenant les listes d'instruments, réparties en deux familles séparées
dans le combo : les **indices** et le **forex**. Le graphique reste visible : un
double-clic dans la liste le met à jour directement.

| Groupe | Contenu | Source |
| --- | --- | --- |
| **Indices** | CAC 40, DAX 40, FTSE MIB, FTSE 100, Euro Stoxx 50, S&P 500, Nasdaq 100 | Wikipédia |
| **Forex · Majeures** | EUR/USD, USD/JPY, GBP/USD, USD/CHF, USD/CAD, AUD/USD, NZD/USD | Liste embarquée |
| **Forex · Mineures** | Croisements sans dollar (EUR/GBP, GBP/JPY, AUD/NZD…) | Liste embarquée |
| **Forex · Exotiques** | Paires avec devises émergentes (USD/TRY, EUR/ZAR…) | Liste embarquée |

- **Combo** en haut : choisit le marché ; un séparateur distingue les indices du
  forex.
- **Filtre** : recherche locale sur le symbole, le nom, le secteur ou la place.
- **Tableau** triable (Symbole, Nom, Secteur, Place) : un clic sur un en-tête
  trie, un clic sélectionne une ligne.
- **Sélectionner** : charge l'actif sélectionné dans le graphique avec
  l'intervalle et la période courants. Un **double-clic** sur une ligne produit
  le même effet.
- **Actualiser** : force la récupération depuis Wikipédia (le cache frais est
  ignoré). Sans effet sur le forex, dont les listes sont embarquées.
- **Statut** en bas : provenance (`Réseau`, `Cache`, `Hors ligne`, `Intégré`),
  nombre de titres et âge du cache.

Les paires forex suivent la convention yfinance (`EURUSD=X`) : un double-clic
charge directement la paire correspondante. Elles apparaissent aussi dans
l'autocomplétion du champ Symbole, même hors ligne.

Fermer la fenêtre ne fait que la masquer : le bouton **Marchés** la réaffiche
dans son état précédent.

Les listes sont mises en cache **7 jours** dans `cache/markets.json` (ignoré par
git). Si le réseau échoue, l'application utilise le cache périmé, puis
l'instantané embarqué (`trading_matrix/data/market_seeds.json`). Le chargement
s'effectue en arrière-plan : l'interface ne gèle pas.

### Onglet « Indicateurs »

Ce panneau unique liste **tous** les indicateurs de `user_indicators/` :
les indicateurs livrés par défaut (SMA, EMA, Bandes de Bollinger, RSI, MACD)
et ceux que tu ajoutes. Coche un ou plusieurs indicateurs, règle leurs
paramètres, puis clique sur **Appliquer**.

| Indicateur | Type | Paramètres |
| --- | --- | --- |
| SMA | Superposé au prix | Période, couleur |
| EMA | Superposé au prix | Période, couleur |
| Bandes de Bollinger | Superposé au prix | Période, écart-type |
| RSI | Sous-graphique | Période |
| MACD | Sous-graphique | Fast, Slow, Signal |

Les widgets de paramètres sont générés automatiquement à partir du
dictionnaire `PARAMS` de chaque fichier : voir
[Indicateurs](indicateurs.md).

- **Appliquer** affiche les indicateurs cochés (remplace les précédents)
- **Effacer tout** retire tous les indicateurs du graphique
- **Rafraîchir** rescanne `user_indicators/`
- **Nouveau...** ouvre un éditeur de code intégré
- **Ouvrir le dossier** ouvre `user_indicators/` dans l'explorateur

Les signaux de stratégie ne sont pas affectés.

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
| TP1 / TP2 / TP3 | Objectifs de prise de profit |
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
| TP3 | Ligne pointillée vert pâle |

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
- **Marchés hors ligne** : si Wikipédia est injoignable, le panneau utilise le
  cache local puis les listes embarquées ; le statut indique `Cache` ou
  `Hors ligne`.
- **Stratégie sans données chargées** : une boîte de dialogue demande de charger
  des données d'abord.
- **Persistance** : aucune sauvegarde automatique entre deux sessions
  (symbole, indicateurs, signaux). Voir [Dépannage](depannage.md) pour les
  évolutions possibles.

## Raccourcis utiles

| Raccourci | Action |
| --- | --- |
| `Entrée` dans le champ symbole | Charger |
| `↑` / `↓` dans les suggestions | Naviguer dans la liste |
| `Tab` dans les suggestions | Insérer le symbole sans charger |
| `Échap` dans les suggestions | Fermer la liste |
| Double-clic sur un signal | Centrer le graphique |
| Double-clic sur un titre (Marchés) | Charger le graphique |
| Clic sur un en-tête de colonne | Trier le tableau |
| Clic sur **Analyser IA** | Analyser le signal avec Ollama |
