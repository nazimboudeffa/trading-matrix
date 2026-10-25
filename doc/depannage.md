# Dépannage

## L'application ne démarre pas

### `ModuleNotFoundError: No module named 'PySide6'`

L'environnement virtuel n'est probablement pas activé, ou les dépendances ne
sont pas installées.

```powershell
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Vérifier l'interpréteur utilisé :

```powershell
python -c "import sys; print(sys.executable)"
```

### `ImportError: cannot import name 'XXX' from 'core.config'`

Une constante manque dans `core/config.py`. Les constantes utilisées par
l'interface (`APP_NAME`, `WINDOW_WIDTH`, `WINDOW_HEIGHT`) doivent être définies
**au niveau module**.

### `TypeError: addToolBar called with wrong argument types`

`QMainWindow.addToolBar()` attend un `QToolBar`, pas un widget quelconque.
La barre d'outils doit être encapsulée :

```python
tb = QToolBar("Toolbar", self)
tb.addWidget(self.toolbar)   # self.toolbar est un QWidget
self.addToolBar(tb)
```

### `qt.qpa.plugin: Could not load the Qt platform plugin "windows"`

Souvent causé par un mélange de versions Qt/PySide6 ou un `PATH` pollué.

```powershell
pip install --force-reinstall PySide6
```

En dernier recours, tester un autre backend :

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
```

### Erreur liée à `ta-lib` sous Windows

`ta-lib` n'est **pas requis**. Le projet utilise le paquet `ta` et des
implémentations locales en repli. Ne pas ajouter `ta-lib` à
`requirements.txt` si son installation échoue.

## Problèmes de données

### OpenBB affiche `Extensions to add: ...`

Message informatif au premier lancement. OpenBB installe/vérifie ses
extensions. Attendre la fin du message avant de conclure à une erreur.

### `'App' object has no attribute 'equity'`

L'API OpenBB varie selon les versions et extensions installées. Le client
contourne cela :

1. tentative OpenBB si `obb.equity.price` existe
2. sinon **yfinance** directement
3. sinon **données de démo**

Si tu vois ce message, l'application fonctionne quand même. Pour forcer
OpenBB, vérifier l'installation :

```powershell
pip install --upgrade openbb openbb-yfinance
python -c "from openbb import obb; print(obb)"
```

### Aucune donnée / graphique vide

- Vérifier la connexion réseau
- Essayer un symbole très liquide (`AAPL`, `MSFT`, `SPY`)
- Vérifier la combinaison intervalle/période (l'intraday est souvent limité)
- Observer la barre d'état : `DEMO` indique un repli sur données synthétiques

### Les dates/heures semblent identiques

Les données de démo utilisent une fréquence journalière ; l'heure est celle de
la génération. Ce n'est pas un bug.

## Problèmes d'affichage

### Le graphique est vide mais les données sont chargées

- Vérifier que `set_data()` a bien été appelé après le chargement
- Essayer `Ctrl+molette` / double-clic pour réinitialiser la vue
- En cas de doute, relancer avec des données de démo :

```python
from data.demo import generate_demo
df = generate_demo("TEST", days=200)
window.chart.set_data(df)
```

### Les sous-graphiques (RSI/MACD) ne s'affichent pas

Les sous-graphiques sont ajoutés au `QSplitter` vertical. Si la fenêtre est
trop petite, ils peuvent être compressés : agrandir la fenêtre ou réduire la
hauteur du graphique principal en déplaçant le séparateur.

### Les signaux ne s'affichent pas sur le graphique

- Vérifier que des données sont chargées **avant** l'analyse
- Vérifier que le tableau **Signaux détectés** contient des lignes
- Les filtres peuvent tout masquer : mettre `Confiance min. = 0` et
  `R:R min. = 0`, sens = `Toutes`
- Un signal dont le `time` n'existe pas dans l'index est ignoré au dessin

### Les couleurs / le thème ne s'appliquent pas

Le fichier `ui/styles.qss` est chargé au démarrage. Vérifier son encodage
UTF-8 et son chemin (`Path(__file__).parent / "styles.qss"`).

## Problèmes d'indicateurs personnalisés

### Mon indicateur n'apparaît pas dans la liste

| Cause | Solution |
| --- | --- |
| Fichier commence par `_` | Renommer sans underscore initial |
| Extension incorrecte | Utiliser `.py` |
| Erreur de syntaxe / import | Lire la console Python |
| Pas de `compute` | Ajouter la fonction `compute(df, **params)` |
| Liste non rafraîchie | Cliquer sur **Rafraîchir** |

### `TypeError: compute() doit retourner IndicatorResult ou dict`

Vérifier le type de retour. Les formats acceptés sont `IndicatorResult` ou un
`dict` avec au minimum `plots`.

### `KeyError` / colonne manquante

Le DataFrame contient `Open`, `High`, `Low`, `Close`, `Volume`. Utiliser
exactement ces noms (sensible à la casse).

### L'indicateur s'affiche mais rien n'est visible

- Vérifier que la série n'est pas entièrement `NaN`
- Vérifier l'alignement de l'index
- Pour un `subplot`, vérifier que `kind="subplot"` est bien défini

## Problèmes de stratégies

### Ma stratégie n'apparaît pas

- Fichier dans `strategies/user_strategies/`
- Classe héritant de `BaseStrategy` (pas de simple fonction)
- Attribut `id` unique
- Pas d'erreur d'import (console)
- Cliquer sur **Rafraîchir stratégies**

### Aucun signal détecté

- La stratégie est peut-être trop restrictive : baisser `min_confidence`,
  baisser `min_rr`, désactiver `require_trend`
- Le jeu de données est peut-être trop court : charger une période plus longue
- Vérifier les filtres d'affichage du panneau **Stratégies**
- Tester hors interface :

```python
from data.demo import generate_demo
from strategies.registry import StrategyRegistry
from strategies.engine import StrategyEngine

df = generate_demo("TEST", days=500)
registry = StrategyRegistry(); registry.discover()
engine = StrategyEngine(registry)
print(len(engine.run("pa_general", df, filters={})))
```

### L'analyse est lente

- Réduire la période chargée (ex : `1y` au lieu de `max`)
- Augmenter les paramètres `swing_left/right`, réduire `lookback_zones`
- La stratégie recalcule la structure tous les 5 bougies ; sur de très gros
  historiques, envisager un passage en thread de fond

### Erreur `KeyError: 'pa_general'`

Le registre n'a pas été découvert. Appeler `registry.discover()` avant
`engine.run(...)`, ou cliquer sur **Rafraîchir stratégies** dans l'interface.

## Problèmes de performance

| Symptôme | Piste |
| --- | --- |
| Interface saccadée au zoom | Réduire le nombre de bougies affichées |
| Analyse longue | Réduire `lookback_zones`, la période, ou le nombre de stratégies |
| Démarrage lent | OpenBB initialise ses extensions ; c'est normal au premier lancement |

## Réinitialiser complètement l'environnement

```powershell
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

## Obtenir plus d'informations

Les erreurs non interceptées s'affichent dans le terminal qui a lancé
`python app.py`. Les erreurs de chargement d'indicateurs/stratégies perso y
sont également imprimées (`[custom] ...`, `[strategies] ...`).

Pour un test rapide sans interface :

```python
from data.demo import generate_demo
from strategies.registry import StrategyRegistry
from strategies.engine import StrategyEngine

df = generate_demo("TEST", days=300)
registry = StrategyRegistry(); registry.discover()
print(list(registry.items))
engine = StrategyEngine(registry)
print(engine.run("pa_general", df))
```
