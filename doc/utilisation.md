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
| **Indices · Cotations** | CAC 40 (`^FCHI`), DAX (`^GDAXI`), S&P 500 (`^GSPC`), Nikkei (`^N225`)… | Liste embarquée |
| **Indices** | Constituants du CAC 40, DAX 40, FTSE MIB, FTSE 100, Euro Stoxx 50, S&P 500, Nasdaq 100 | Wikipédia |
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
  ignoré). Sans effet sur les cotations d'indices et le forex, dont les listes
  sont embarquées.
- **Statut** en bas : provenance (`Réseau`, `Cache`, `Hors ligne`, `Intégré`),
  nombre de titres et âge du cache.

Les indices cotés suivent les symboles yfinance (`^FCHI`, `^GSPC`…) : un
double-clic charge directement le graphique de l'indice, et non celui de ses
constituants. Les paires forex suivent la convention `EURUSD=X`. Ces
instruments apparaissent aussi dans l'autocomplétion du champ Symbole, même
hors ligne.

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

### Profil daytrading (avec les paramètres existants)

Il n'existe pas de case « daytrading » dans l'interface. Le principe est de
demander des données **intraday**, puis de régler la stratégie et les filtres
pour ne garder que des signaux courts et peu nombreux. Tout se fait avec les
contrôles déjà présents, sans modifier le code ni l'interface.

> L'application n'a pas de notion de séance : elle ne connaît ni les horaires
> d'ouverture/clôture, ni la clôture forcée avant la fin de journée. Le
> « daytrading » est donc un **profil de réglage**, pas une règle de gestion
> d'ordre : la décision de sortir avant la clôture reste manuelle.

#### 1. Données (barre d'outils)

| Contrôle | Réglage suggéré | Remarque |
| --- | --- | --- |
| **Intervalle** | `1m`, `5m` ou `15m` (`30m` / `1h` pour moins de bruit) | Éviter `4h` et plus : au-delà, un signal peut couvrir plusieurs jours. |
| **Période** | `1d` ou `5d` (`1mo` au plus) | Les historiques intraday sont limités par le provider ; une période trop longue peut être tronquée ou échouer. |

Clique sur **Charger** avant de lancer l'analyse.

#### 2. Paramètres de la stratégie

**Price Action Général (`pa_general`)** — points de départ :

| Paramètre (libellé de l'interface) | Réglage suggéré | Effet recherché |
| --- | --- | --- |
| **Tendance requise** | Cocher | Écarte les setups contraires à la structure. |
| **Signaux à venir** | Décocher, ou **Max signaux à venir** = 1 et **Distance max (×ATR)** = 1–2 | Un plan conditionnel peut rester en attente d'un jour à l'autre. |
| **Cooldown (bougies)** | 5–10 sur du 5m (soit 25–50 min) | Limite le nombre de signaux et le sur-trading. |
| **Confiance min.** | 60–70 | Garde les confluences les plus fortes. |
| **R:R minimum** | 1,2–1,5 | Évite des cibles trop proches du bruit intraday. |
| **Swings gauche** / **Swings droite** | 2–3 | Structure plus réactive sur une unité de temps courte. |
| **Lookback zones** | 30–60 | Order Blocks plus récents. |
| **Recalcul structure (bougies)** | 3–5 | Suit plus vite les changements de structure. |
| **Accepter les mèches au-delà de la zone** | Décocher | Zones de réaction plus strictes. |
| **Marge du stop (×ATR)** / **Tolérance de zone (×ATR)** | Valeurs basses (0,15–0,25 / 0,25–0,5) | Stop plus serré et réaction exigée plus près de la zone, donc des signaux plus exigeants. |

**SMA / EMA crossover** — si tu préfères un suivi de tendance plus simple :

- **SMA/EMA rapide** 9–12 et **lente** 21–26 ;
- **Filtre de tendance** coché (il est décoché par défaut) ;
- **Stop (×ATR)** 1,0–1,5 et **TP1 (×ATR)** 1,5–2,5 au lieu de 3,0, pour des
  objectifs plus proches ;
- **Cooldown (bougies)** 5–10 et **Fenêtre de pente** 3–5.

#### 3. Filtres d'affichage (communs à toutes les stratégies)

| Filtre | Réglage suggéré | Remarque |
| --- | --- | --- |
| **Sens** | `LONG` ou `SHORT` selon le biais de la séance | `Toutes` laisse les deux sens. |
| **Confiance min. (%)** | 60–70 | S'ajoute au **Confiance min.** de la stratégie : les deux seuils sont appliqués. |
| **R:R min.** | 1,2–1,5 | Cumulatif avec le **R:R minimum** de la stratégie. |
| **Max signaux** | 5–10 | `Illimité` (0) peut donner trop de décisions sur 1m/5m. |

Clique ensuite sur **Analyser le graphique** et vérifie la colonne **Heure** du
tableau : elle indique la bougie de référence du signal.

#### 4. Points de vigilance

- **Aucun filtre horaire** : l'application ne vérifie pas « 9h30–16h00 » ni les
  horaires des autres places.
- **Fuseaux horaires** : `openbb_client.py` convertit les dates avec
  `pd.to_datetime` sans fuseau explicite. L'heure affichée peut donc être locale
  ou UTC selon la source ; vérifie-la sur un symbole connu avant de raisonner en
  heure de séance.
- Un setup **En attente** ou un TP peut rester pertinent sur plusieurs séances :
  ce profil ne clôture rien automatiquement.
- **Pas de backtest intégré** : ces valeurs sont des points de départ, pas un
  réglage validé statistiquement. Ajuste-les après observation.
- **Aucune persistance** : les réglages sont à refaire après un redémarrage.

#### Revenir à un profil swing

Repasser en `1h` / `4h` et `1mo` / `3mo`, réactiver **Signaux à venir**, augmenter
**Lookback zones** (60–120) et **Cooldown**, puis relâcher les filtres
(**Confiance min.** 50, **Max signaux** `Illimité`).

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
