# Analyse IA des signaux (Llama App)

Chaque signal du tableau **Signaux détectés**, confirmé ou **En attente**,
possède une colonne **IA** avec un bouton **Analyser IA**. Il ouvre une fenêtre
séparée dans laquelle un modèle local (via [Llama App](https://llama.app))
analyse le signal : structure de marché, confluence, risques, invalidation et
gestion du risque.

| Heure | Sens | Statut | Setup | Entrée | SL | TP1 | TP2 | R:R | Conf. | Raisons | IA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ... | LONG | Confirmé | ... | ... | .. | ... | ... | 1.5 | 63 % | ... | [Analyser IA] |
| ... | SHORT | En attente | ... | ... | .. | ... | ... | 2.0 | 55 % | ... | [Analyser IA] |

## 1. Prérequis : Llama App

L'analyse IA utilise **Llama App**, un serveur local basé sur llama.cpp. Aucune
clé API ni compte n'est nécessaire et les données ne quittent pas la machine.

1. Télécharger Llama App : <https://llama.app/download>
2. L'installer, puis vérifier que le serveur tourne :

   ```bash
   llama serve
   ```

   Sous Windows/macOS, l'application Llama démarre généralement le serveur
   automatiquement (barre des tâches / menu).
3. Télécharger au moins un modèle, depuis l'application ou en le servant
   directement :

   ```bash
   llama serve -hf ggml-org/gemma-4-e4b-it-GGUF:Q4_0
   ```

4. Vérifier que l'application détecte le modèle :

   ```bash
   curl http://127.0.0.1:9931/v1/models
   ```

L'application interroge `http://127.0.0.1:9931/v1/models` pour lister les
modèles. Pour utiliser un serveur distant, définir la variable d'environnement
`LLAMA_HOST` (par exemple `http://192.168.1.20:9931`). Si le serveur a été
lancé avec `--api-key`, définir aussi `LLAMA_API_KEY`.

## 2. Utilisation

1. Charger des données et lancer une stratégie (**Analyser le graphique**).
2. Dans le tableau des signaux, cliquer sur **Analyser IA** sur la ligne voulue
   (y compris une ligne dont le statut est **En attente**).
3. L'application vérifie Llama App :
   - **Llama App introuvable** → une fenêtre indique que l'application est
     absente et donne les étapes d'installation.
   - **Serveur Llama non démarré** → une fenêtre demande de lancer
     `llama serve`.
   - **Aucun modèle Llama** → une fenêtre indique comment installer un modèle
     depuis l'application ou avec `llama serve -hf ...`.
4. Si tout est prêt, la fenêtre d'analyse s'ouvre. Le modèle choisi est
   mémorisé, mais **aucune analyse ne démarre automatiquement** : cliquez sur
   **Analyser avec l'IA** (puis **Relancer l'analyse** pour une nouvelle
   génération).

Dans la fenêtre d'analyse :

| Élément | Rôle |
| --- | --- |
| **Modèle Llama** | Choix du modèle ; le dernier choix est mémorisé pour les analyses suivantes |
| **Inclure les dernières actualités (OpenBB)** | Ajoute au prompt les actualités les plus récentes de l'actif. Le choix est mémorisé ; le chargement se fait en arrière-plan (repli `yfinance` si OpenBB ne répond pas) |
| **Rafraîchir** | Rescanne les modèles disponibles (après installation d'un modèle) |
| **Contexte envoyé à l'IA** | Texte exact transmis au modèle (signal, bougies, indicateurs) |
| **Analyse de l'IA** | Réponse diffusée en direct, puis rendue en Markdown |
| **Raisonnement du modèle** | Affiché si le modèle expose un raisonnement (*thinking*) |
| **Analyser avec l'IA / Relancer** | Démarre l'analyse avec le modèle sélectionné (aucun lancement automatique) |
| **Arrêter** | Interrompt la génération en cours |
| **Copier l'analyse** | Copie la réponse dans le presse-papiers |
| **Fermer** | Ferme la fenêtre (interrompt la génération si nécessaire) |

La fenêtre est indépendante : elle peut rester ouverte pendant que l'on continue
à naviguer dans le graphique. Plusieurs analyses peuvent être ouvertes en
parallèle.

### Signaux à venir

Un setup **En attente** est un plan conditionnel : la bougie de réaction n'a pas
encore eu lieu. La fenêtre l'indique dans son sous-titre (`EN ATTENTE`) et
affiche un bandeau **Setup conditionnel — ...** rappelant la condition exacte à
remplir. Le prompt demande alors au modèle d'évaluer la probabilité que le prix
atteigne la zone d'entrée, puis de reformuler la condition de déclenchement, au
lieu de juger une entrée déjà acquise (voir section 3).

## 3. Ce qui est envoyé au modèle

Le prompt contient :

- l'identité du signal : symbole, unité de temps, date, sens, setup, stratégie ;
- le **statut** (`Confirmé` ou `EN ATTENTE`) et, pour un setup à venir, la
  condition de déclenchement, le mode d'entrée et la distance au prix ;
- les niveaux : entrée, stop loss, TP1/TP2, distance en %, R:R, zone Order Block ;
- les raisons calculées par la stratégie et son score de confluence ;
- les **40 dernières bougies** (OHLCV) **jusqu'à la dernière bougie disponible**
  (ou jusqu'à la bougie du signal pour un signal confirmé) ;
- si la case **Inclure les dernières actualités (OpenBB)** est cochée, les
  **5 actualités les plus récentes** de l'actif (titre, source, date UTC et
  extrait court), récupérées via OpenBB puis, en repli, via `yfinance` ;
- des indicateurs de contexte : ATR(14), SMA(20/50/200), plus haut/bas des
  20 dernières bougies, tendance de structure (swings 3/3), anatomie de la
  bougie de référence ;
- une consigne de travail structurée (verdict, structure, confluence, risques,
  gestion, points d'attention). Pour un setup à venir, le travail demande en
  plus d'évaluer la probabilité d'atteinte de la zone et de reformuler la
  condition de déclenchement.

> [!IMPORTANT]
> Aucune bougie **postérieure** au signal (ou à la dernière bougie disponible)
> n'est transmise : le modèle ne peut pas « tricher » en connaissant la suite du
> graphique. Pour un setup **En attente**, il évalue une condition qui n'est pas
> encore réalisée.
>
> Les **actualités** sont optionnelles et correspondent aux articles les plus
> récents **au moment de l'analyse** : elles peuvent donc être postérieures à la
> bougie du signal. Le prompt le précise explicitement et demande au modèle de
> les traiter comme un contexte actuel, jamais comme une information connue au
> moment du signal.

Les données sont envoyées uniquement au serveur Llama configuré (localhost par
défaut). Les actualités sont, elles, récupérées auprès d'OpenBB / Yahoo Finance
uniquement lorsque la case est cochée. Le prompt complet est toujours visible
dans la fenêtre avant/après l'analyse.

## 4. Personnalisation du prompt

Le prompt est construit dans `trading_matrix/core/signal_context.py` :

- `SYSTEM_PROMPT` : rôle, règles et format de réponse ;
- `build_signal_prompt(...)` : contexte de marché et travail demandé ;
- paramètres `news` / `news_error` : actualités optionnelles (objets `NewsItem`)
  et message d'indisponibilité injectés dans le prompt ;
- paramètre `candles` (40 par défaut) : nombre de bougies incluses.

Pour un prompt plus court (modèles avec petite fenêtre de contexte), réduire
`candles` ou adapter `SYSTEM_PROMPT`.

Le client Llama (`trading_matrix/core/llama_client.py`) expose :

```python
from trading_matrix.core import llama_client

status = llama_client.get_status()
status.installed, status.running, status.models

model = "ggml-org/gemma-4-e4b-it-GGUF:Q4_0"
for kind, text in llama_client.chat_stream(model, messages):
    print(kind, text)   # kind = "content" ou "thinking"
```

## 5. Dépannage

| Symptôme | Cause probable | Solution |
| --- | --- | --- |
| « Llama App introuvable » | Binaire absent du `PATH` | Installer Llama App, redémarrer l'application |
| « Serveur Llama non démarré » | Serveur arrêté | Lancer `llama serve` (ou l'application Llama) |
| « Aucun modèle Llama » | Aucun modèle installé | Installer un modèle puis **Rafraîchir** |
| `Erreur Llama (404) : ...` | Modèle indisponible entre-temps | Rafraîchir et choisir un modèle existant |
| Analyse très lente | Modèle volumineux / machine limitée | Choisir un modèle plus petit (`LiquidAI/LFM3-Omni-2B-GGUF`) |
| Réponse vide | Modèle en échec ou contexte trop grand | Relancer avec un autre modèle, réduire `candles` |
| Caractères bizarres dans la console | Encodage du terminal | Sans impact sur l'interface (UTF-8 utilisé dans l'UI) |

Le raisonnement complet et les erreurs HTTP sont affichés dans la fenêtre
d'analyse ; les erreurs non interceptées apparaissent dans le terminal qui a
lancé `python main.py`.

> [!WARNING]
> L'analyse IA est **éducative**. Un modèle de langage peut se tromper, inventer
> une justification ou ignorer un risque. Elle ne constitue pas un conseil en
> investissement et ne remplace ni votre jugement ni votre gestion du risque.
