"""3D position of a detection: deproject its depth, keep the main cluster, map to the robot."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree
from wpimath.geometry import Rotation3d, Translation3d

from aether_vision.config import CameraMount
from aether_vision.types import Box, DepthGeometry, DepthImage, FloatArray, Vec3

ROI_SCALE = 0.7  # sample the central part of the box, where the object is
STRIDE = 2  # every Nth depth pixel, in both directions
DEPTH_RANGE_M = (0.15, 8.0)
MAX_POINTS = 3000
CLUSTER_RADIUS_M = 0.04  # points closer than this belong to the same object
MIN_CLUSTER_POINTS = 20


@dataclass(frozen=True, slots=True)
class PointCloud:
    """Depth points in the color camera's optical frame, with their color-image pixels."""

    points: FloatArray  # N x 3, meters (x right, y down, z forward)
    pixels: FloatArray  # N x 2, (u, v) in the color image


def point_cloud(depth: DepthImage, depth_scale_m: float, geometry: DepthGeometry) -> PointCloud:
    """Deproject every ``STRIDE``-th valid depth pixel and project it into the color image.

    This is what ``rs.align`` does, but only for the sampled pixels and without
    building an aligned image, so it costs a fraction of the time.
    """
    z = depth[::STRIDE, ::STRIDE].astype(np.float32) * np.float32(depth_scale_m)
    vs, us = np.nonzero((z >= DEPTH_RANGE_M[0]) & (z <= DEPTH_RANGE_M[1]))
    z = z[vs, us]
    d = geometry.depth
    in_depth = np.column_stack(
        ((us * STRIDE - d.cx) / d.fx * z, (vs * STRIDE - d.cy) / d.fy * z, z)
    ).astype(np.float32)
    points = in_depth @ geometry.rotation.T + geometry.translation
    c = geometry.color
    pixels = np.column_stack(
        (c.fx * points[:, 0] / points[:, 2] + c.cx, c.fy * points[:, 1] / points[:, 2] + c.cy)
    )
    return PointCloud(points, pixels.astype(np.float32))


def locate(box: Box, cloud: PointCloud, mount: CameraMount) -> tuple[Vec3, float] | None:
    """``(robot-frame position, distance from camera)`` of the object in ``box``, if found.

    Uses the points that land in the central ``ROI_SCALE`` of the box.
    """
    cx, cy = box.x + box.width / 2, box.y + box.height / 2
    half_w, half_h = box.width * ROI_SCALE / 2, box.height * ROI_SCALE / 2
    u, v = cloud.pixels[:, 0], cloud.pixels[:, 1]
    inside = (np.abs(u - cx) <= half_w) & (np.abs(v - cy) <= half_h)
    points = cloud.points[inside]
    if len(points) > MAX_POINTS:
        points = points[np.linspace(0, len(points) - 1, MAX_POINTS).astype(np.int64)]
    cluster = largest_cluster(points)
    if cluster is None:
        return None
    x, y, z = (float(v) for v in cluster.mean(axis=0))
    return camera_to_robot((x, y, z), mount), math.sqrt(x * x + y * y + z * z)


def largest_cluster(points: FloatArray) -> FloatArray | None:
    """The largest group of points linked within ``CLUSTER_RADIUS_M`` (single linkage).

    Points are first merged into voxels of half the radius and the voxel centers
    are linked: a dense depth surface gives each raw point ~100 neighbors, which
    makes linking raw points slow.
    """
    if len(points) < MIN_CLUSTER_POINTS:
        return None
    cells = np.floor(points / np.float32(CLUSTER_RADIUS_M / 2)).astype(np.int64)
    cells -= cells.min(axis=0)
    span = cells.max(axis=0) + 1
    keys = (cells[:, 0] * span[1] + cells[:, 1]) * span[2] + cells[:, 2]
    _, voxel_of_point = np.unique(keys, return_inverse=True)
    counts = np.bincount(voxel_of_point)
    centers = np.column_stack(
        [np.bincount(voxel_of_point, weights=points[:, axis]) / counts for axis in range(3)]
    )
    pairs = cKDTree(centers).query_pairs(CLUSTER_RADIUS_M, output_type="ndarray")
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), (len(counts),) * 2)
    _, voxel_labels = connected_components(graph, directed=False)
    labels = voxel_labels[voxel_of_point]
    sizes = np.bincount(labels)
    best = int(np.argmax(sizes))
    return points[labels == best] if sizes[best] >= MIN_CLUSTER_POINTS else None


def camera_to_robot(point: Vec3, mount: CameraMount) -> Vec3:
    """Optical-frame point -> robot frame (WPILib: x forward, y left, z up)."""
    x, y, z = point
    rotation = Rotation3d(
        math.radians(mount.roll_deg), math.radians(mount.pitch_deg), math.radians(mount.yaw_deg)
    )
    robot = Translation3d(z, -x, -y).rotateBy(rotation) + Translation3d(
        mount.x_m, mount.y_m, mount.z_m
    )
    return (robot.x, robot.y, robot.z)
