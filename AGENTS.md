# Consignes pour les assistants

## Objectif : économiser le contexte

Travailler avec des lectures ciblées, adaptées aux quotas des modèles utilisés
dans OpenCode. Ce fichier guide le travail ; il ne configure ni la fenêtre de
contexte du modèle ni la compaction de la conversation.

- Commencer par `git status --short --branch` pour préserver le travail local.
- Localiser les fichiers avec `rg --files`, puis les symboles avec
  `rg -n 'motif' chemin`. Limiter la recherche au dossier pertinent.
- Lire d'abord la fonction concernée avec ses imports et les types nécessaires.
  Utiliser `rg -n -C 15 'motif' chemin` ou une plage de lignes ; élargir si
  l'extrait ne suffit pas à comprendre le comportement et ses dépendances.
- Éviter de charger un fichier entier ou plusieurs modules par habitude.
  Une lecture complète reste appropriée pour un fichier court ou une modification
  transversale. Ne pas tronquer arbitrairement au risque de manquer une dépendance.
- Réutiliser les extraits déjà présents dans la conversation tant que les fichiers
  concernés n'ont pas changé. Après une modification, relire la zone ou le diff.
- Exclure `.venv/`, `.git/`, `cache/`, les caches Python et les fichiers générés
  des recherches de code, sauf si la tâche les concerne explicitement.
- Consulter seulement la section de documentation utile ; ne pas charger tout
  `doc/` ni tout le README à chaque tâche.
- Appliquer des patchs ciblés. Éviter de réécrire ou reformater un fichier entier
  pour une petite correction, et de recopier de gros extraits dans les réponses.
- Garder les sorties de commandes courtes : chemins, symboles, diff pertinent et
  résumé des vérifications. En cas d'échec, lire les détails nécessaires.
- Pour une reprise après compaction, conserver un résumé bref : objectif,
  branche, fichiers/fonctions touchés, décisions, vérifications et prochaine étape.
  Ne pas promettre qu'un résumé efface l'historique ou réduit à lui seul le quota.

## Repères du projet

Application desktop Python : PySide6, pyqtgraph, données OpenBB/yfinance.

| Besoin | Point d'entrée |
| --- | --- |
| Stratégie Price Action, orchestration et signaux | `user_strategies/price_action_general.py` |
| Signaux en attente | Méthode `_pending_setups` dans ce même fichier |
| Construction d'un setup | Méthode `_try_setup` dans ce même fichier |
| Swings, tendance, BOS/CHOCH | `trading_matrix/strategies/price_action/structure.py` |
| Order Blocks et mitigation des zones | `trading_matrix/strategies/price_action/zones.py` |
| Réactions des bougies | `trading_matrix/strategies/price_action/patterns.py` |
| ATR et fonctions de bougies | `trading_matrix/strategies/utils.py` |
| Contrats `Signal`, `StrategyContext`, `BaseStrategy` | `trading_matrix/strategies/base.py` |
| Exécution et filtres des stratégies | `trading_matrix/strategies/engine.py` |
| Découverte des stratégies | `trading_matrix/strategies/registry.py` |
| Indicateurs fournis et personnels | `user_indicators/` |
| Chargement et contrats des indicateurs | `trading_matrix/indicators/` |
| Graphiques et marqueurs de signaux | `trading_matrix/ui/chart_widget.py`, `trading_matrix/charts/markers.py` |
| Interface utilisateur | `trading_matrix/ui/` |
| Données, marchés et recherche de symboles | `trading_matrix/data/` |
| Contexte des signaux et analyse Ollama | `trading_matrix/core/signal_context.py`, `trading_matrix/core/ollama_client.py` |

La stratégie générale est désormais dans `user_strategies/price_action_general.py`,
et non dans l'ancien `trading_matrix/strategies/price_action/general.py`.
Pour une correction Price Action, commencer par le symbole concerné ; ne lire
`structure.py`, `zones.py`, `base.py` ou `utils.py` que si la modification en dépend.
Actualiser ces repères si un fichier ou une responsabilité est déplacé.

## Modifications et vérification

- Respecter les conventions existantes et limiter la modification à la demande.
  Éviter les refontes, déplacements et nouvelles dépendances non nécessaires.
- Préserver les indicateurs et stratégies personnels, y compris les fichiers
  ignorés par Git ; ne pas les supprimer lors d'un nettoyage.
- Examiner `git diff --check` et le diff des fichiers modifiés.
- Pour du code, lancer les tests pertinents et ajouter un test de régression
  lorsqu'il vérifie réellement le comportement corrigé. Ne pas inventer de tests
  qui ne font que reproduire l'implémentation.
- Sous PowerShell : `.\.venv\Scripts\python.exe -m pytest -q` ; cibler un fichier
  de `tests/` si adapté. Les tests actuels couvrent les marchés et la recherche
  de symboles ; leur réussite ne valide pas à elle seule le Price Action ou l'UI.
- Pour une modification documentaire seule, vérifier le contenu et le diff suffit.
- Rapporter brièvement ce qui a changé, les vérifications réalisées et leurs limites.
