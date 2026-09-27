"""Registro de todos os coletores disponiveis.

Cada modulo de coletor (google_trends, youtube, reddit, sketchfab, cults3d,
printables, ...) acrescenta a propria classe a `ALL_COLLECTORS`.
"""

from app.collectors.base import Collector
from app.collectors.google_trends import GoogleTrendsCollector
from app.collectors.youtube import YouTubeCollector

ALL_COLLECTORS: list[type[Collector]] = [
    GoogleTrendsCollector,
    YouTubeCollector,
]
