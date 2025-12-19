"""Module with utils for wind turbine location data convertion."""

from typing import List, Optional, Tuple

import pandas as pd
from scipy.spatial import KDTree

from ..location_converters.get_lat_lon_matrix import get_lat_lon_matrix


def cleanup_short_distance_turbines(
    data: pd.DataFrame, dist: Optional[float] = None
) -> Tuple[pd.DataFrame, float, List[Tuple[int, int]]]:
    """Remove turbines with a short distance to each orther.

    Args:
        data: DataFrame containing wind turbine data
        dist: Minimal distance between turbines (in degrees); default: 1e-3 ~ 100m

    Returns:
        filtered_data:     Filtered data with only the turbines with distance >= dist
        min_dist:          Minimal distance between turbines in filtered data set
        duplicate_data:   List of duplicate rows in dataset

    """
    if dist is None:
        dist = 1.5e-3  # ~150m threshold

    tree = KDTree(get_lat_lon_matrix(data))

    distances, idx = tree.query(
        get_lat_lon_matrix(data),
        k=2,
        # distance_upper_bound=dist
    )

    duplicate_pairs = {
        tuple(sorted(idx))
        for (idx, pair_dist) in zip(idx, distances[:, 1])
        if pair_dist < dist
    }
    duplicate_data = [
        (data.iloc[idx1], data.iloc[idx2]) for (idx1, idx2) in duplicate_pairs
    ]

    # Get rid of self-match
    idx = idx[:, 1]
    distances = distances[:, 1]

    selector = distances >= dist

    if selector.any():
        mindist = min(distances[selector])
        return data[selector], mindist, duplicate_data

    return data, None, duplicate_data
