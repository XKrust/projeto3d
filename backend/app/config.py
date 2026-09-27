"""Configuracao de caminhos e banco de dados."""

import os
from pathlib import Path

# Raiz do repositorio: backend/app/config.py -> app -> backend -> raiz
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = Path(os.environ.get("RADAR_DATA_DIR") or (REPO_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_URL = f"sqlite:///{DATA_DIR / 'radar.db'}"
