from __future__ import annotations

import numpy as np
import pytest

from aether_vision.core.types import BoundingBox
from aether_vision.vision.clustering import ClusteringConfig, euclidean_clusters
from aether_vision.vision.deprojection import roi_point_cloud
from aether_vision.vision.transforms import CameraExtrinsics, CameraToRobot
from tests.fakes import INTRINSICS


def test_roi_point_cloud_deprojects_pinhole() -> None:
    depth = np.zeros((48, 64), dtype=np.uint16)
    depth[24, 32] = 2000  # principal point -> straight ahead
    depth[0, 0] = 2000  # top-left corner
    cloud = roi_point_cloud(depth, 0.001, INTRINSICS, BoundingBox(0, 0, 64, 48))
    expected_corner = [-32 / 50 * 2.0, -24 / 50 * 2.0, 2.0]
    np.testing.assert_allclose(sorted(cloud.tolist()), sorted([expected_corner, [0.0, 0.0, 2.0]]))


def test_roi_point_cloud_filters_invalid_depth() -> None:
    depth = np.full((48, 64), 2000, dtype=np.uint16)
    depth[:, :32] = 0  # invalid left half
    cloud = roi_point_cloud(depth, 0.001, INTRINSICS, BoundingBox(0, 0, 64, 48), stride=1)
    assert cloud.shape == (32 * 48, 3)
    assert np.all(cloud[:, 0] >= 0.0)
    np.testing.assert_allclose(cloud[:, 2], 2.0)
    strided = roi_point_cloud(depth, 0.001, INTRINSICS, BoundingBox(0, 0, 64, 48), stride=4)
    assert strided.shape[0] == (32 // 4) * (48 // 4)


def test_roi_outside_image_is_empty() -> None:
    depth = np.full((48, 64), 2000, dtype=np.uint16)
    assert roi_point_cloud(depth, 0.001, INTRINSICS, BoundingBox(100, 100, 5, 5)).shape == (0, 3)


def _two_blobs() -> np.ndarray:
    rng = np.random.default_rng(0)
    near = rng.normal([0.0, 0.0, 1.0], 0.01, size=(300, 3))
    far = rng.normal([0.0, 0.0, 3.0], 0.01, size=(100, 3))
    noise = np.array([[5.0, 5.0, 9.0]])
    return np.vstack([near, far, noise]).astype(np.float32)


def test_clustering_separates_objects() -> None:
    clusters = euclidean_clusters(_two_blobs(), ClusteringConfig(radius_m=0.05, min_points=10))
    assert [c.size for c in clusters] == [300, 100]
    assert clusters[0].centroid[2] == pytest.approx(1.0, abs=0.01)
    assert clusters[1].distance == pytest.approx(3.0, abs=0.01)


def test_camera_to_robot_axes() -> None:
    transform = CameraToRobot(CameraExtrinsics(x_m=0.1, y_m=0.0, z_m=0.5))
    forward = transform.apply(np.array([0.0, 0.0, 2.0], dtype=np.float32))
    np.testing.assert_allclose(forward, [2.1, 0.0, 0.5], atol=1e-6)
    right = transform.apply(np.array([1.0, 0.0, 0.0], dtype=np.float32))
    np.testing.assert_allclose(right, [0.1, -1.0, 0.5], atol=1e-6)
    down = transform.apply(np.array([0.0, 1.0, 0.0], dtype=np.float32))
    np.testing.assert_allclose(down, [0.1, 0.0, -0.5], atol=1e-6)


def test_camera_pitch_down() -> None:
    transform = CameraToRobot(CameraExtrinsics(z_m=1.0, pitch_deg=90.0))
    # Looking straight down: optical forward maps to robot -z.
    point = transform.apply(np.array([0.0, 0.0, 1.0], dtype=np.float32))
    np.testing.assert_allclose(point, [0.0, 0.0, 0.0], atol=1e-6)
