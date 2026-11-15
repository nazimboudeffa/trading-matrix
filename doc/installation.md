# Installation

## Prérequis

| Élément | Version conseillée |
| --- | --- |
| Python | 3.11 ou supérieur (3.12 recommandé) |
| Système | Windows, Linux ou macOS |
| Connexion internet | Nécessaire pour OpenBB/yfinance (sinon données de démo) |
| Ollama (optionnel) | Analyse IA locale des signaux — voir [Analyse IA](analyse-ia.md) |

> Le projet a été développé et testé sous Windows avec Python 3.12.

## 1. Récupérer le projet

```bash
git clone <url-du-repo> trading-matrix
cd trading-matrix
```

Ou simplement se placer dans le dossier existant :

```bash
cd C:\Users\<utilisateur>\Documents\GitHub\trading-matrix
```

## 2. Créer un environnement virtuel

```powershell
# Windows
python -m venv .venv
.\.venv\Scripts\activate
```

```bash
# Linux / macOS
python -m venv .venv
source .venv/bin/activate
```

## 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

Contenu principal de `requirements.txt` :

| Paquet | Rôle |
| --- | --- |
| `PySide6` | Interface graphique Qt |
| `pyqtgraph` | Rendu des graphiques |
| `openbb` | Plateforme de données financières (API 4.x et 5.x supportées) |
| `openbb-yfinance` | Provider de données yfinance (branches 1.x et 2.x supportées) |
| `pandas` | Manipulation des données OHLCV |
| `lxml` | Parsing des tableaux HTML (listes de marchés) |
| `numpy` | Calculs numériques |
| `ta` | Indicateurs techniques (fallback si `ta-lib` absent) |
| `requests` | Client HTTP pour l'API locale Ollama |
| `pyinstaller` | Génération d'exécutable (optionnel) |

> `ta-lib` n'est pas obligatoire : le projet utilise `ta` et des implémentations
> locales en repli.

## 4. Lancer l'application

```bash
python main.py
```

Au premier démarrage, OpenBB peut afficher un message concernant l'installation
d'extensions (`Extensions to add: ...`). C'est normal.

> Le client est compatible **OpenBB 4.x et 5.x** : aucune mise à jour manuelle
> n'est nécessaire, que `pip` ait installé l'une ou l'autre. Pour vérifier la
> version en place : `pip show openbb`.
>
> Au premier chargement du panneau **Marchés**, un cache est créé dans
> `cache/markets.json` (ignoré par git) puis réutilisé pendant 7 jours.

## Comportement en cas d'absence de données

Le chargement suit trois tentatives :

1. **OpenBB** via le provider `yfinance` (API 5.x `obb.yfinance.equity.price`,
   puis API 4.x `obb.equity.price` en repli)
2. **yfinance** directement (si OpenBB échoue)
3. **Données de démonstration** générées localement

Dans le dernier cas, la barre d'état indique `DEMO` et un graphique synthétique
est affiché : l'interface reste entièrement utilisable.

## Analyse IA locale (optionnel)

L'analyse IA des signaux s'appuie sur **Ollama**, qui n'est pas un paquet
Python et n'est donc pas dans `requirements.txt`.

1. Installer Ollama : <https://ollama.com/download>
2. Vérifier le service : `ollama serve`
3. Télécharger un modèle : `ollama pull llama3.1`

L'application détecte automatiquement le binaire et l'API locale. Aucune
configuration supplémentaire n'est nécessaire. Voir
[Analyse IA](analyse-ia.md) pour l'usage et le dépannage.

## Créer un exécutable (optionnel)

```bash
pyinstaller --noconfirm --windowed --name TradingMatrix main.py
```

L'exécutable est généré dans `dist/TradingMatrix/`. Les dossiers
`user_indicators/` et `user_strategies/` doivent être placés à côté
de l'exécutable pour être détectés.

## Désinstallation

```bash
deactivate
rm -rf .venv        # Windows : Remove-Item -Recurse -Force .venv
```
