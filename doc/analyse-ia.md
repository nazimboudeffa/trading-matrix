# Analyse IA des signaux (Ollama)

Chaque signal du tableau **Signaux détectés**, confirmé ou **En attente**,
possède une colonne **IA** avec un bouton **Analyser IA**. Il ouvre une fenêtre
séparée dans laquelle un modèle local (via [Ollama](https://ollama.com)) analyse
le signal : structure de marché, confluence, risques, invalidation et gestion du
risque.

| Heure | Sens | Statut | Setup | Entrée | SL | TP1 | TP2 | R:R | Conf. | Raisons | IA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ... | LONG | Confirmé | ... | ... | .. | ... | ... | 1.5 | 63 % | ... | [Analyser IA] |
| ... | SHORT | En attente | ... | ... | .. | ... | ... | 2.0 | 55 % | ... | [Analyser IA] |

## 1. Prérequis : Ollama

L'analyse IA utilise **Ollama**, un serveur de modèles local. Aucune clé API ni
compte n'est nécessaire et les données ne quittent pas la machine.

1. Télécharger Ollama : <https://ollama.com/download>
2. L'installer, puis vérifier que le service tourne :

   ```bash
   ollama serve
   ```

   Sous Windows/macOS, l'application Ollama démarre généralement le service
   automatiquement.
3. Télécharger au moins un modèle :

   ```bash
   ollama pull llama3.1
   # ou un modèle plus léger :
   ollama pull llama3.2:3b
   ```

4. Vérifier que l'application détecte le modèle :

   ```bash
   ollama list
   ```

L'application interroge `http://127.0.0.1:11434/api/tags` pour lister les
modèles. Pour utiliser un serveur distant, définir la variable
d'environnement `OLLAMA_HOST` (par exemple `http://192.168.1.20:11434`).

## 2. Utilisation

1. Charger des données et lancer une stratégie (**Analyser le graphique**).
2. Dans le tableau des signaux, cliquer sur **Analyser IA** sur la ligne voulue
   (y compris une ligne dont le statut est **En attente**).
3. L'application vérifie Ollama :
   - **Ollama n'est pas installé** → une fenêtre indique qu'Ollama est absent et
     donne les étapes d'installation.
   - **Ollama est installé mais arrêté** → une fenêtre demande de lancer
     `ollama serve`.
   - **Aucun modèle installé** → une fenêtre indique la commande
     `ollama pull ...`.
4. Si tout est prêt, la fenêtre d'analyse s'ouvre. Lors de la **première**
   utilisation, choisissez le modèle dans la liste puis cliquez sur
   **Analyser avec l'IA**. Le modèle choisi est mémorisé : les fois suivantes,
   l'analyse démarre automatiquement avec celui-ci.

Dans la fenêtre d'analyse :

| Élément | Rôle |
| --- | --- |
| **Modèle Ollama** | Choix du modèle ; le dernier choix est mémorisé pour les analyses suivantes |
| **Rafraîchir** | Rescanne les modèles installés (après un `ollama pull`) |
| **Contexte envoyé à l'IA** | Texte exact transmis au modèle (signal, bougies, indicateurs) |
| **Analyse de l'IA** | Réponse diffusée en direct, puis rendue en Markdown |
| **Raisonnement du modèle** | Affiché si le modèle expose un raisonnement (*thinking*) |
| **Analyser avec l'IA / Relancer** | Relance l'analyse avec le modèle sélectionné |
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

Les données sont envoyées uniquement au serveur Ollama configuré (localhost par
défaut). Le prompt complet est toujours visible dans la fenêtre avant/après
l'analyse.

## 4. Personnalisation du prompt

Le prompt est construit dans `core/signal_context.py` :

- `SYSTEM_PROMPT` : rôle, règles et format de réponse ;
- `build_signal_prompt(...)` : contexte de marché et travail demandé ;
- paramètre `candles` (40 par défaut) : nombre de bougies incluses.

Pour un prompt plus court (modèles avec petite fenêtre de contexte), réduire
`candles` ou adapter `SYSTEM_PROMPT`.

Le client Ollama (`core/ollama_client.py`) expose :

```python
from core import ollama_client

status = ollama_client.get_status()
status.installed, status.running, status.models

for kind, text in ollama_client.chat_stream("llama3.1", messages):
    print(kind, text)   # kind = "content" ou "thinking"
```

## 5. Dépannage

| Symptôme | Cause probable | Solution |
| --- | --- | --- |
| « Ollama introuvable » | Binaire absent du `PATH` | Installer Ollama, redémarrer l'application |
| « Ollama n'est pas démarré » | Service arrêté | Lancer `ollama serve` (ou l'application Ollama) |
| « Aucun modèle Ollama » | Aucun modèle téléchargé | `ollama pull llama3.1` puis **Rafraîchir** |
| `Erreur Ollama (404) : model ... not found` | Modèle supprimé entre-temps | Rafraîchir et choisir un modèle existant |
| Analyse très lente | Modèle volumineux / machine limitée | Choisir un modèle plus petit (`llama3.2:3b`, `qwen2.5:3b`) |
| Réponse vide | Modèle en échec ou contexte trop grand | Relancer avec un autre modèle, réduire `candles` |
| Caractères bizarres dans la console | Encodage du terminal | Sans impact sur l'interface (UTF-8 utilisé dans l'UI) |

Le raisonnement complet et les erreurs HTTP sont affichés dans la fenêtre
d'analyse ; les erreurs non interceptées apparaissent dans le terminal qui a
lancé `python app.py`.

> [!WARNING]
> L'analyse IA est **éducative**. Un modèle de langage peut se tromper, inventer
> une justification ou ignorer un risque. Elle ne constitue pas un conseil en
> investissement et ne remplace ni votre jugement ni votre gestion du risque.
