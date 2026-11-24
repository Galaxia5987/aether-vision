"""Point-cloud clustering used to separate an object from background inside a detection box."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import Field
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from aether_vision.config.base import ConfigModel
from aether_vision.core.types import FloatArray


class ClusteringConfig(ConfigModel):
    radius_m: float = Field(
        0.04, gt=0.001, le=1.0, description="Points closer than this join the same cluster"
    )
    min_points: int = Field(20, ge=1, description="Smaller clusters are discarded as noise")


@dataclass(frozen=True, slots=True)
class Cluster:
    points: FloatArray  # (N, 3)

    @property
    def size(self) -> int:
        return int(self.points.shape[0])

    @property
    def centroid(self) -> FloatArray:
        return self.points.mean(axis=0)

    @property
    def extent(self) -> FloatArray:
        return np.ptp(self.points, axis=0)

    @property
    def distance(self) -> float:
        return float(np.linalg.norm(self.centroid))


def euclidean_clusters(points: FloatArray, config: ClusteringConfig) -> list[Cluster]:
    """Single-linkage clustering: connected components of the ``radius_m`` neighbour graph.

    Returns clusters with at least ``min_points`` points, largest first.
    """
    count = points.shape[0]
    if count < config.min_points:
        return []
    pairs = cKDTree(points).query_pairs(config.radius_m, output_type="ndarray")
    graph = coo_matrix(
        (np.ones(pairs.shape[0], dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(count, count)
    )
    _, labels = connected_components(graph, directed=False)
    sizes = np.bincount(labels)
    return [
        Cluster(points[labels == label])
        for label in np.argsort(-sizes)
        if sizes[label] >= config.min_points
    ]
