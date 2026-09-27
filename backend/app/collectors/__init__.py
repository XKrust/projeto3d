"""Registro de todos os coletores disponiveis.

Cada modulo de coletor (google_trends, youtube, reddit, sketchfab, cults3d,
printables, ...) acrescenta a propria classe a `ALL_COLLECTORS`.
"""

from app.collectors.base import Collector
from app.collectors.thingiverse import ThingiverseCollector
from app.collectors.etsy import EtsyCollector
from app.collectors.artstation import ArtStationCollector
from app.collectors.booth import BoothCollector
from app.collectors.cults3d import Cults3DCollector
from app.collectors.google_trends import GoogleTrendsCollector
from app.collectors.printables import PrintablesCollector
from app.collectors.reddit import RedditCollector
from app.collectors.sketchfab import SketchfabCollector
from app.collectors.youtube import YouTubeCollector

ALL_COLLECTORS: list[type[Collector]] = [
    GoogleTrendsCollector,
    YouTubeCollector,
    RedditCollector,
    SketchfabCollector,
    Cults3DCollector,
    PrintablesCollector,
    BoothCollector,
    ArtStationCollector,
    EtsyCollector,
    ThingiverseCollector,
]
