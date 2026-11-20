"""Point-cloud clustering used to separate an object from background inside a detection box."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Annotated, Final, Literal

import numpy as np
import numpy.typing as npt
from pydantic import Field
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from aether_vision.config.base import ConfigModel
from aether_vision.core.types import FloatArray

# The 13 "forward" neighbours of a voxel in a 26-neighbourhood; their mirror
# images are covered by symmetry when building an undirected graph.
_FORWARD_OFFSETS: Final = np.array(
    [
        (dx, dy, dz)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dz in (-1, 0, 1)
        if (dx, dy, dz) > (0, 0, 0)
    ],
    dtype=np.int64,
)


@dataclass(frozen=True, slots=True)
class Cluster:
    points: FloatArray  # (N, 3)
    centroid: FloatArray  # (3,)
    extent: FloatArray  # (3,) axis-aligned size

    @property
    def size(self) -> int:
        return int(self.points.shape[0])

    @property
    def distance(self) -> float:
        return float(np.linalg.norm(self.centroid))

    @staticmethod
    def from_points(points: FloatArray) -> Cluster:
        centroid = points.mean(axis=0).astype(np.float32)
        extent = (points.max(axis=0) - points.min(axis=0)).astype(np.float32)
        return Cluster(points, centroid, extent)


class PointCloudClusterer(ABC):
    @abstractmethod
    def labels(self, points: FloatArray) -> npt.NDArray[np.int64]:
        """Return a cluster label per point (``-1`` for noise)."""

    def __init__(self, min_points: int) -> None:
        self._min_points = min_points

    def cluster(self, points: FloatArray) -> list[Cluster]:
        """Clusters with at least ``min_points`` points, largest first."""
        if points.shape[0] < self._min_points:
            return []
        labels = self.labels(points)
        clusters: list[Cluster] = []
        valid = labels[labels >= 0]
        if valid.size == 0:
            return []
        counts = np.bincount(valid)
        for label in np.argsort(-counts):
            if counts[label] < self._min_points:
                break
            clusters.append(Cluster.from_points(points[labels == label]))
        return clusters


class VoxelClusterer(PointCloudClusterer):
    """Connected components over a sparse voxel grid (26-connectivity).

    Memory scales with the number of occupied voxels, not with the bounding
    volume, so stray far-away points do not blow up the cost.
    """

    def __init__(self, voxel_size_m: float, min_points: int) -> None:
        super().__init__(min_points)
        if voxel_size_m <= 0.0:
            raise ValueError("voxel_size_m must be positive")
        self._voxel_size = voxel_size_m

    def labels(self, points: FloatArray) -> npt.NDArray[np.int64]:
        voxels = np.floor(points / self._voxel_size).astype(np.int64)
        voxels -= voxels.min(axis=0)
        dims = voxels.max(axis=0) + 3  # +margin so neighbour offsets never wrap
        voxels += 1

        def encode(v: npt.NDArray[np.int64]) -> npt.NDArray[np.int64]:
            key: npt.NDArray[np.int64] = (v[:, 0] * dims[1] + v[:, 1]) * dims[2] + v[:, 2]
            return key

        keys, point_to_voxel = np.unique(encode(voxels), return_inverse=True)
        voxel_coords = voxels[np.unique(point_to_voxel, return_index=True)[1]]
        rows: list[npt.NDArray[np.int64]] = []
        cols: list[npt.NDArray[np.int64]] = []
        for offset in _FORWARD_OFFSETS:
            neighbour_keys = encode(voxel_coords + offset)
            positions = np.searchsorted(keys, neighbour_keys)
            positions = np.minimum(positions, keys.size - 1)
            hit = keys[positions] == neighbour_keys
            rows.append(np.nonzero(hit)[0])
            cols.append(positions[hit])
        row = np.concatenate(rows)
        col = np.concatenate(cols)
        graph = coo_matrix(
            (np.ones(row.size, dtype=np.int8), (row, col)), shape=(keys.size, keys.size)
        )
        _, voxel_labels = connected_components(graph, directed=False)
        point_labels: npt.NDArray[np.int64] = voxel_labels.astype(np.int64)[
            point_to_voxel.reshape(-1)
        ]
        return point_labels


class EuclideanClusterer(PointCloudClusterer):
    """Points closer than ``radius_m`` belong to the same cluster (single linkage)."""

    def __init__(self, radius_m: float, min_points: int) -> None:
        super().__init__(min_points)
        if radius_m <= 0.0:
            raise ValueError("radius_m must be positive")
        self._radius = radius_m

    def labels(self, points: FloatArray) -> npt.NDArray[np.int64]:
        tree = cKDTree(points)
        pairs = tree.query_pairs(self._radius, output_type="ndarray")
        n = points.shape[0]
        graph = coo_matrix(
            (np.ones(pairs.shape[0], dtype=np.int8), (pairs[:, 0], pairs[:, 1])), shape=(n, n)
        )
        _, raw_labels = connected_components(graph, directed=False)
        labels: npt.NDArray[np.int64] = np.asarray(raw_labels, dtype=np.int64)
        return labels


class VoxelClustererConfig(ConfigModel):
    kind: Literal["voxel"] = "voxel"
    voxel_size_m: float = Field(0.03, gt=0.001, le=1.0)
    min_points: int = Field(20, ge=1)


class EuclideanClustererConfig(ConfigModel):
    kind: Literal["euclidean"] = "euclidean"
    radius_m: float = Field(0.04, gt=0.001, le=1.0)
    min_points: int = Field(20, ge=1)


ClustererConfig = Annotated[
    VoxelClustererConfig | EuclideanClustererConfig, Field(discriminator="kind")
]


def create_clusterer(config: ClustererConfig) -> PointCloudClusterer:
    if isinstance(config, VoxelClustererConfig):
        return VoxelClusterer(config.voxel_size_m, config.min_points)
    if isinstance(config, EuclideanClustererConfig):
        return EuclideanClusterer(config.radius_m, config.min_points)
    raise TypeError(f"Unknown clusterer config {type(config).__name__}")
