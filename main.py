"""Point d'entrée de Trading Matrix.

Lance l'application depuis la racine du projet :

    python main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garantit que la racine du projet est importable, quel que soit le dossier
# depuis lequel le script est lancé.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trading_matrix.app import main  # noqa: E402

if __name__ == "__main__":
    main()
