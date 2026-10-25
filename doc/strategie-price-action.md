# Stratégie Price Action Général

Implémentation : `strategies/price_action/general.py`
Classe : `PriceActionGeneral` (`id = "pa_general"`)

Cette stratégie est le socle fourni par défaut. Elle combine **structure de
marché**, **Order Blocks** et **confirmation price action** pour produire des
signaux avec stop loss et objectifs.

## Paramètres

| Paramètre | Type | Défaut | Plage | Description |
| --- | --- | --- | --- | --- |
| `swing_left` | int | 3 | 1-10 | Bougies à gauche pour valider un swing |
| `swing_right` | int | 3 | 1-10 | Bougies à droite pour valider un swing |
| `lookback_zones` | int | 60 | 20-300 | Fenêtre de recherche des Order Blocks |
| `min_rr` | float | 1.2 | 0.5-5.0 | Ratio risque/rendement minimal |
| `min_confidence` | int | 50 | 0-100 | Score de confluence minimal |
| `require_trend` | bool | True | — | Exiger une structure non opposée |
| `cooldown` | int | 5 | 0-50 | Bougies minimales entre deux signaux |
| `show_pending` | bool | True | — | Afficher les setups conditionnels à venir |
| `pending_max` | int | 2 | 0-10 | Nombre maximal de signaux à venir |
| `pending_max_distance_atr` | float | 4.0 | 0-20 | Distance maximale au prix en ×ATR (0 = pas de limite) |

## Pipeline

```mermaid
flowchart TD
    A[DataFrame OHLCV] --> B[ATR 14]
    A --> C{Toutes les 5 bougies}
    C --> D[Find swings sur df[:i+1]]
    D --> E[Tendance: BULLISH / BEARISH / RANGE]
    D --> F[Order Blocks dans la fenêtre]
    F --> G[Supprimer les zones déjà touchées avant i]
    A --> H[Réaction PA sur la bougie i]
    H --> I{Engulfing ou Pinbar ?}
    I -- non --> C
    I -- oui --> J{Zone compatible + tendance OK}
    J -- non --> C
    J -- oui --> K[Calcul SL / TP1 / TP2]
    K --> L[Score de confluence]
    L --> M{R:R >= min_rr et confiance >= min_conf}
    M -- non --> C
    M -- oui --> N[Signal confirmé]
    N --> O[Setups à venir sur zones non testées]
```

## 1. Structure de marché

### Détection des swings

`find_swings(df, left, right)` identifie un **swing high** si le plus haut de la
bougie est supérieur ou égal aux `left` bougies précédentes **et** aux `right`
bougies suivantes. Symétrique pour les **swing lows**.

Les swings ne sont calculés que sur `df.iloc[:i+1]` (fenêtre tronquée), ce qui
évite d'utiliser des bougies futures.

### Tendance

`get_trend(swings)` examine les 3 derniers highs et les 3 derniers lows :

| Condition | Tendance |
| --- | --- |
| Highs croissants **et** lows croissants | `BULLISH` |
| Highs décroissants **et** lows décroissants | `BEARISH` |
| Sinon (ou moins de 4 swings) | `RANGE` |

### BOS / CHOCH

`detect_bos_choch(df, swings)` est disponible dans `structure.py` (cassure du
dernier swing structurel) mais **n'est pas encore utilisé** par la stratégie
générale. C'est une brique prête pour de futures stratégies.

## 2. Order Blocks

`find_order_blocks(df, lookback)` implémente une version simplifiée :

### Order Block haussier (`OB_BULL`)

- bougie `i` **baissière** (`Close < Open`)
- bougie `i+1` **haussière** qui **clôture au-dessus du high de `i`**
- déplacement suffisant : amplitude de `i+1` ≥ `0.6 × amplitude moyenne` (50 bougies)

Zone : de `Low[i]` (bas) à `max(Open[i], Close[i])` (haut).

### Order Block baissier (`OB_BEAR`)

- bougie `i` **haussière**
- bougie `i+1` **baissière** qui **clôture sous le low de `i`**
- déplacement suffisant (même règle)

Zone : de `min(Open[i], Close[i])` (bas) à `High[i]` (haut).

### Mitigation

Une zone est considérée comme **consommée** si le prix l'a déjà traversée entre
sa création et la bougie courante. Les zones mitigées sont écartées.

Le test est vectorisé : `min(Low[j..i]) <= top` **et**
`max(High[j..i]) >= bottom`.

## 3. Confirmation Price Action

`detect_reaction(df, i)` teste quatre patterns sur la bougie `i` :

| Pattern | Condition |
| --- | --- |
| **Bullish Engulfing** | bougie précédente baissière, bougie courante haussière qui englobe le corps précédent |
| **Bearish Engulfing** | symétrique |
| **Pinbar haussier** | mèche basse ≥ 2 × corps **et** > moitié de l'amplitude |
| **Pinbar baissier** | mèche haute ≥ 2 × corps **et** > moitié de l'amplitude |

Un signal LONG nécessite une réaction haussière, un signal SHORT une réaction
baissière.

## 4. Conditions de setup

### LONG

1. réaction haussière sur la bougie `i`
2. si `require_trend` : tendance ≠ `BEARISH`
3. au moins un `OB_BULL` tel que `bottom ≤ Low[i] ≤ top + 0.5 × ATR`
4. la zone la plus récente est retenue
5. la zone n'a pas déjà produit un signal (`used_zones`)

### SHORT

Symétrique avec `OB_BEAR` et la condition
`bottom - 0.5 × ATR ≤ High[i] ≤ top`.

### Cooldown

Un signal n'est autorisé que si `i - dernier_index_signal ≥ cooldown`.

## 5. Stop Loss et Take Profit

### LONG

```text
SL  = min(zone.bottom, Low[i]) - 0.25 × ATR
TP1 = plus proche swing high au-dessus de l'entrée
      (sinon entrée + 2 × risque)
TP2 = plus proche swing high au-dessus de TP1
      (sinon entrée + 3 × risque)
```

### SHORT

```text
SL  = max(zone.top, High[i]) + 0.25 × ATR
TP1 = plus proche swing low sous l'entrée
      (sinon entrée - 2 × risque)
TP2 = plus proche swing low sous TP1
      (sinon entrée - 3 × risque)
```

Le R:R est calculé sur `TP1` :

```text
risque  = |entrée - SL|
reward  = |TP1 - entrée|
R:R     = reward / risque
```

Le signal est rejeté si `R:R < min_rr`.

## 6. Score de confluence

| Critère | Points |
| --- | --- |
| Base | 40 |
| Structure alignée avec le sens | +20 |
| Marché en range | +5 |
| Réaction sur un Order Block | +15 |
| Nombre de patterns détectés | +3 par pattern (max +10) |
| R:R ≥ 1.5 | +10 |

Score final borné à **100**. Le signal est rejeté si
`score < min_confidence`.

## 7. Signaux à venir (setups conditionnels)

En plus des signaux confirmés, la stratégie peut proposer des **setups à venir**
(paramètre `show_pending`, actif par défaut). Ce ne sont **pas des prédictions** :
ils décrivent un plan conditionnel sur un Order Block encore non testé, à
proximité du prix courant.

### Sélection

- zone `OB_BULL` ou `OB_BEAR` non touchée entre `zone.index + 2` et
  l'avant-dernière bougie ;
- la **dernière bougie** peut être dans la zone : le setup est alors « en cours
  de test » et attend une bougie de réaction ;
- prix du bon côté de la zone (au-dessus du bas pour un OB haussier, sous le haut
  pour un OB baissier) ;
- tendance non opposée si `require_trend` ;
- distance au prix ≤ `pending_max_distance_atr × ATR(14)` (0 = pas de limite) ;
- `R:R ≥ min_rr` et score ≥ `min_confidence` ;
- zone non déjà utilisée par un signal confirmé ;
- tri par distance au prix puis par score, limité à `pending_max`.

### Plan conditionnel

| Situation | Entrée | Stop loss |
| --- | --- | --- |
| LONG, prix au-dessus de l'OB | limite au haut de la zone (`zone.top`) | `zone.bottom - 0.25 × ATR` |
| LONG, prix dans l'OB | close courant (indicatif, en attendant la réaction) | `zone.bottom - 0.25 × ATR` |
| SHORT, prix sous l'OB | limite au bas de la zone (`zone.bottom`) | `zone.top + 0.25 × ATR` |
| SHORT, prix dans l'OB | close courant (indicatif, en attendant la réaction) | `zone.top + 0.25 × ATR` |

Les objectifs TP1 / TP2 utilisent les swings opposés disponibles, sinon
`entrée ± 2 × risque` et `entrée ± 3 × risque`.

Chaque setup porte `meta["pending"] = True` et `meta["condition"]`, qui décrit
précisément la bougie de réaction attendue. **Un setup n'est pas un ordre** :
tant que la condition n'est pas remplie, il ne doit pas être exécuté. Si le prix
traverse la zone sans réaction, le setup est invalidé.

### Score des setups à venir

| Critère | Points |
| --- | --- |
| Base | 50 |
| Structure alignée avec le sens | +10 |
| Marché en range | +3 |
| Entrée par ordre limite (prix hors zone) | +2 |
| R:R ≥ 1.5 | +5 |

Score borné à **70** pour rester distinct des signaux confirmés (généralement
60-100).

## 8. Rendu dans l'application

Pour chaque signal confirmé :

- flèche verte (LONG) ou rouge (SHORT) sur la bougie
- label `L <score>%` / `S <score>%`
- bande semi-transparente représentant la zone (12 bougies avant, 18 après)
- lignes pointillées SL / TP1 / TP2 sur ~25 bougies
- ligne dans le tableau **Signaux détectés** avec le statut `Confirmé`

Pour chaque setup à venir :

- diamant creux ambre projeté dans une marge à droite de la dernière bougie
- label `L <score>% · à venir` / `S <score>% · à venir`
- bande pointillée prolongée dans la marge future
- lignes SL / TP1 / TP2 pointillées
- ligne dans le tableau avec le statut **`En attente`** (texte ambre)

Le tableau possède une colonne **Statut** (`Confirmé` / `En attente`) et le
bouton **Analyser IA** fonctionne aussi sur les setups conditionnels : le prompt
précise alors qu'ils ne sont pas déclenchés et demande au modèle d'évaluer la
condition.

## 9. Exemple de signal

```text
2026-05-12  SHORT  entrée 85.04
  SL  89.74   (zone OB + 0.25 ATR)
  TP1 77.07   (swing low)
  TP2 71.50
  confiance 73
  raisons : Réaction baissière | Structure baissière |
            OB baissier (84.10-86.90) | PA: BEAR_ENGULFING | R:R >= 1.5
```

Exemple illustratif de setup à venir (aucune bougie de réaction encore) :

```text
2026-06-02  LONG  EN ATTENTE  OB_PENDING_BULL
  entrée limite 82.59 | SL 79.96 | TP1 86.22 | TP2 88.50
  confiance 55 — distance 13.0 % (4.0 × ATR)
  condition : attendre une bougie de réaction haussière (engulfing ou pinbar)
              dans la zone 80.12-82.59
```

## 10. Limites connues

- **Un seul timeframe** analysé à la fois : pas de confluence HTF.
- **Structure recalculée tous les 5 bougies** : un swing peut être pris en
  compte avec un léger retard.
- **Order Blocks simplifiés** : pas de Fair Value Gaps, pas de zones de
  liquidité (equal highs/lows), pas de breaker blocks.
- **Entrée au close** de la bougie de confirmation pour les signaux confirmés :
  pas de gestion d'ordre limite, de spread ni de slippage.
- **Les signaux à venir ne sont pas des prédictions** : ce sont des plans
  conditionnels. Ils peuvent ne jamais se déclencher, être invalidés par une
  traversée de zone, ou être trop éloignés du prix (filtre de distance).
  L'entrée indiquée quand le prix est déjà dans la zone est **indicative** :
  elle ne doit être utilisée qu'après la bougie de réaction.
- **Pas de suivi en temps réel** : les setups à venir sont recalculés à chaque
  exécution de la stratégie sur les données chargées ; ils ne se mettent pas à
  jour automatiquement à l'arrivée de nouvelles bougies.
- **TP basés sur les swings disponibles** dans la fenêtre analysée : sur un
  historique court, les objectifs peuvent être éloignés ou repliés sur les
  valeurs par défaut (2R / 3R).
- **Pas de backtest** : les signaux ne sont pas évalués a posteriori
  (winrate, espérance, drawdown).
- **Une seule position par zone** : une zone consommée ne régénère pas de
  signal confirmé.

## 11. Pistes d'amélioration

1. Ajouter les **zones de liquidité** (égalités de hauts/bas) comme cibles.
2. Filtrer par **biais HTF** (ex : tendance daily pour des setups 1h).
3. Détecter les **FVG / imbalances** et les utiliser comme zones.
4. Implémenter un **backtest** simple (TP/SL touché, R multiple, equity curve).
5. Ajouter un **scoring pondéré configurable** plutôt que des points fixes.
