"""Registro de todos os coletores disponiveis.

Cada modulo de coletor (google_trends, youtube, reddit, sketchfab, cults3d,
printables, ...) acrescenta a propria classe a `ALL_COLLECTORS` nas tarefas
seguintes. Comeca vazia nesta tarefa.
"""

from app.collectors.base import Collector

ALL_COLLECTORS: list[type[Collector]] = []
