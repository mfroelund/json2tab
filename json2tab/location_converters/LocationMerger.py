"""Module for advanched wind turbine location merger."""

import contextlib
import math
import os
import time
from enum import Enum
from typing import List, Optional, Tuple

import pandas as pd
from scipy.spatial import KDTree

from ..io.writers import save_dataframe
from ..location_converters.get_lat_lon_matrix import get_lat_lon_matrix
from ..logs import logger, logging
from ..Turbine import Turbine
from ..utils import (
    get_height,
    get_installed_power,
    get_radius,
    get_rated_power_kw,
    get_value_from_dict,
    power_to_kw,
)


class MergeStrategy(Enum):
    """Merge strategy used in the advanched location merger."""

    """ Combine data from both sources. """
    Combine = 0

    """ Use locations from first source and enrich it with data from second source. """
    EnrichSet1 = 1

    """ Use locations from second source and enrich it with data from first source. """
    EnrichSet2 = 2

    @staticmethod
    def from_string(value: str):
        """Converts a string to a MergeStrategy."""
        if value.upper() in ["COMBINE", "UNION"]:
            return MergeStrategy.Combine

        if value.upper() in [
            "ENRICHSET1",
            "ENRICH_SET_1",
            "ENRICH_1",
            "ENRICH_FIRST",
            "ENRICH1",
            "UNION_WITH_INTERSECTION_2",
        ]:
            return MergeStrategy.EnrichSet1

        if value.upper() in [
            "ENRICHSET2",
            "ENRICH_SET_2",
            "ENRICH_2",
            "ENRICH_SECOND",
            "ENRICH2",
            "UNION_WITH_INTERSECTION_1",
        ]:
            return MergeStrategy.EnrichSet2

        return None


def location_merger(
    file1: str,
    file2: str,
    output_file: str,
    merge_mode: Optional[MergeStrategy | str] = MergeStrategy.Combine,
    label_source1: Optional[str] = None,
    label_source2: Optional[str] = None,
    dump_temp_files: Optional[bool] = None,
    unique_file1=None,
    unique_file2=None,
    common_file1=None,
    common_file2=None,
    merged_file=None,
):
    """The advanched wind turbine location merger."""
    if dump_temp_files is None:
        dump_temp_files = logger.getEffectiveLevel() <= logging.DEBUG

    if dump_temp_files:
        base_output = os.path.splitext(output_file)[0]
        if merged_file is None:
            merged_file = f"{base_output}.merged.csv"

        if unique_file1 is None:
            unique_file1 = f"{base_output}.unique_file1.csv"

        if unique_file2 is None:
            unique_file2 = f"{base_output}.unique_file2.csv"

        if common_file1 is None:
            common_file1 = f"{base_output}.common_file1.csv"

        if common_file2 is None:
            common_file2 = f"{base_output}.common_file2.csv"

    if isinstance(merge_mode, str):
        merge_mode = MergeStrategy.from_string(merge_mode)

    if merge_mode is None:
        merge_mode = MergeStrategy.Combine

    print(
        f"Windturbine location merger; "
        f"{file1} + {file2} -> {output_file} (merge_mode = {merge_mode})"
    )
    if unique_file1 is not None:
        print(f"Unique turbines in {file1} are written to {unique_file1}")
    if unique_file2 is not None:
        print(f"Unique turbines in {file2} are written to {unique_file2}")
    if common_file1 is not None:
        print(f"Common turbines in {file1} are written to {common_file1}")
    if common_file2 is not None:
        print(f"Common turbines in {file2} are written to {common_file2}")
    if merged_file is not None:
        print(f"Merged turbines are written to {merged_file}")

    df_file1 = pd.read_csv(file1)
    df_file2 = pd.read_csv(file2)

    if "source" not in df_file1.columns:
        if label_source1 is None:
            _, label_source1 = os.path.split(file1)
        df_file1["source"] = label_source1
        logger.info(f"Set source-field for {file1} to '{label_source1}'")

    if "source" not in df_file2.columns:
        if label_source2 is None:
            _, label_source2 = os.path.split(file2)
        df_file2["source"] = label_source2
        logger.info(f"Set source-field for {file2} to '{label_source2}'")

    logger.info(f"Loaded {len(df_file1)} turbines from {file1}")
    logger.info(f"Loaded {len(df_file2)} turbines from {file2}")

    (
        merged_turbines,
        df_file1_unique,
        df_file2_unique,
        df_file1_duplicate,
        df_file2_duplicate,
    ) = merge_dataframes(df_file1, df_file2)

    if merged_file is not None:
        pd.DataFrame(merged_turbines).to_csv(merged_file, index=False)

    if unique_file1 is not None and df_file1_unique is not None:
        df_file1_unique.to_csv(unique_file1, index=False)

    if unique_file2 is not None and df_file2_unique is not None:
        df_file2_unique.to_csv(unique_file2, index=False)

    if common_file1 is not None and df_file1_duplicate is not None:
        df_file1_duplicate.to_csv(common_file1, index=False)

    if common_file2 is not None and df_file2_duplicate is not None:
        df_file2_duplicate.to_csv(common_file2, index=False)

    # Write combined data
    file1_unique = []
    file2_unique = []

    turbine_keys = set(Turbine().to_dict().keys())

    if (
        df_file1_unique is not None
        and len(set(df_file1_unique.columns) - turbine_keys) > 0
    ):
        file1_unique = df_file1_unique.apply(datarow_to_turbine, axis=1).to_list()
        df_file1_unique = None

    if (
        df_file2_unique is not None
        and len(set(df_file2_unique.columns) - turbine_keys) > 0
    ):
        file2_unique = df_file2_unique.apply(datarow_to_turbine, axis=1).to_list()
        df_file2_unique = None

    unique1 = len(file1_unique) + (
        len(df_file1_unique.index) if df_file1_unique is not None else 0
    )
    unique2 = len(file2_unique) + (
        len(df_file2_unique.index) if df_file2_unique is not None else 0
    )
    logger.info(f"Collecting {unique1} unique turbines from {file1}")
    logger.info(f"Collecting {unique2} unique turbines from {file2}")
    logger.info(
        f"Collecting {len(merged_turbines)} merged turbines from {file1} and {file2}"
    )

    if merge_mode == MergeStrategy.EnrichSet1:
        file2_unique = []
        df_file2_unique = None
    elif merge_mode == MergeStrategy.EnrichSet2:
        file1_unique = []
        df_file1_unique = None
    # else: keep all data and combine it

    combined_turbines = file1_unique + file2_unique + merged_turbines
    df_combined_turbines = pd.concat(
        [df_file1_unique, df_file2_unique, pd.DataFrame(combined_turbines)]
    )

    logger.info(f"Merged dataframe contains {len(df_combined_turbines.index)} turbines.")
    save_dataframe(df_combined_turbines, output_file)


def merge_dataframes(
    df_file1: pd.DataFrame,
    df_file2: pd.DataFrame,
    tol: Optional[float] = None,
    preferred_source_df: Optional[pd.DataFrame] = None,
    merged_source_name: Optional[str] = None,
) -> Tuple[List[Turbine], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Merge wind turbine locations from different pandas.DataFrames."""
    start_time = time.time()
    tree = KDTree(get_lat_lon_matrix(df_file1))

    # Set tolerance for distance between turbines
    if tol is None:
        tol = 1.5e-3  # ~150m threshold

    done = False
    while not done:
        distances, idx = tree.query(
            get_lat_lon_matrix(df_file2), k=1, distance_upper_bound=tol
        )

        overlapping = distances < tol
        if overlapping.any():
            if len(idx[overlapping]) != len(set(idx[overlapping])):
                # tol /= 10

                logger.warning(
                    "One (or more) wind turbines from dataset2 are mapped to "
                    "the multiple wind-turbines in dataset1, let's ignore it"
                )
                done = True
            else:
                done = True
        else:
            done = True

    logger.info(
        f"Compare wind turbine locations based on tol={tol} degree "
        f"(~<{int(111*1000 * tol)} meter)."
    )

    overlapping = distances < tol
    if overlapping.any():
        df_file1_duplicate = df_file1.iloc[idx[overlapping]]
        df_file2_duplicate = df_file2[overlapping]

        logger.info(f"Loaded {len(df_file1_duplicate)} duplicate turbines from dataset1")
        logger.info(f"Loaded {len(df_file2_duplicate)} duplicate turbines from dataset2")

        df_file1_unique = df_file1.drop(df_file1_duplicate.index.array)
        logger.info(f"Loaded {len(df_file1_unique)} unique turbines from dataset1")
    else:
        df_file1_duplicate = None
        df_file2_duplicate = None
        df_file1_unique = df_file1

    non_overlapping = distances >= tol
    if non_overlapping.any():
        df_file2_unique = df_file2[non_overlapping]
        logger.info(f"Loaded {len(df_file2_unique)} unique turbines from dataset2")
    else:
        df_file2_unique = df_file2

    merged_turbines = []

    if overlapping.any():
        # Merge common files
        merged_cols = [
            "geometry",
            "latitude",
            "longitude",
            "lat",
            "lon",
            "x",
            "y",
            "utm_x",
            "utm_y",
            "name",
            "naam",
            "turbine_nr",
            "manufacturer",
            "type",
            "wt_type",
            "wf101_type",
            "hubheight",
            "hub_height",
            "height",
            "ash",
            "radius",
            "radius (m)",
            "diameter",
            "diameter (m)",
            "rotor_diameter",
            "diam",
            "rated_power",
            "power",
            "power_rating",
            "kw",
            "source",
        ]

        for idx in range(len(df_file1_duplicate)):
            row1 = df_file1_duplicate.iloc[idx]
            row2 = df_file2_duplicate.iloc[idx]

            if preferred_source_df is None:
                if count_none_fields(row1, merged_cols) > count_none_fields(
                    row2, merged_cols
                ):
                    preferred_source, alternative_source = row2, row1
                else:
                    preferred_source, alternative_source = row1, row2
            elif preferred_source_df is df_file1:
                preferred_source, alternative_source = row1, row2
            elif preferred_source_df is df_file2:
                preferred_source, alternative_source = row2, row1

            if (
                alternative_source.get("manufacturer") is not None
                and alternative_source.get("type") is not None
                and preferred_source.get("manufacturer") is None
            ):
                # Swap perferred/alternative source if manufacturer+type seems richer
                preferred_source, alternative_source = (
                    alternative_source,
                    preferred_source,
                )

            merged_turbine = merge_turbine_data(
                preferred_source, alternative_source, merged_source_name
            )
            merged_turbines.append(merged_turbine)
    else:
        logger.info("No duplicates found")

    logger.info(f"Merging datasets took {time.time() - start_time} seconds")

    return (
        merged_turbines,
        df_file1_unique,
        df_file2_unique,
        df_file1_duplicate,
        df_file2_duplicate,
    )


def get_nearest_turbine(
    df_file1: pd.DataFrame, turbine: Turbine, tol: float, tree: Optional[KDTree] = None
):
    """Get wind turbine closest to a given turbine.

    Args:
        df_file1 (pd.DataFrame): Dataframe with wind turbine locations
        turbine (Turbine):       Turbine for which closest turbine should be found
        tol (float):             Distance upper bound for nearest turbine
        tree (KDTree):           (Optional) KDTree of [lat, lon] matrix of df_file1

    Returns:
        row:  Row of wind turbine with shortest distance (or None)
        dist: Distance between turbines
        tree: KDTree of [lat, lon] matrix of df_file1


    """
    if tree is None:
        tree = KDTree(get_lat_lon_matrix(df_file1))

    distances, idx = tree.query(
        [[turbine.latitude, turbine.longitude]], k=1, distance_upper_bound=tol
    )

    match = (distances < tol) & (distances == min(distances))

    if match.any():
        matched_turbine = df_file1.iloc[idx[match]]
        try:
            import geopy.distance

            lat_lon = get_lat_lon_matrix(matched_turbine)

            coords_1 = (turbine.latitude, turbine.longitude)
            coords_2 = (lat_lon[0][0], lat_lon[0][1])

            dist = geopy.distance.geodesic(coords_1, coords_2).m
        except Exception as e:
            logger.exception(
                f"Failed to compute distance between " f"requested point and match: {e!s}"
            )
            dist = None
        return df_file1.iloc[idx[match]], dist, tree

    return None, dist, tree


def datarow_to_turbine(row) -> Turbine:
    """Convert data row to Turbine."""
    return merge_turbine_data(row, None)


def merge_turbine_data(
    preferred_source, alternative_source, merged_source_name: Optional[str] = None
) -> Turbine:
    """Merge turbine data from two sources.

    Args:
        preferred_source:   Preferred source to provide turbine information
        alternative_source: Alternative source to provide turbine information
        merged_source_name: (Optional) Source name when data from two sources is used

    Returns:
        Merged turbine
    """
    alternative_used = False

    id_field, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["id", "ID", "GSRN", "Turbine identifier (GSRN)"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    name, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["name", "naam", "Turbine", "WFNAME", "nr_turbine", "Location"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    turbine_id, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            [
                "turbine_id",
                "turbine_nr",
                "nr_turbine",
                "turbine id",
                "Turbine identifier (GSRN)",
            ],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )

    lat_lon = get_lat_lon_matrix(
        preferred_source
        if isinstance(preferred_source, dict)
        else preferred_source.to_dict()
    )
    lat, lon = lat_lon[0, 0], lat_lon[0, 1]

    manufacturer, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["manufacturer", "Manufacture"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    model_type, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            [
                "type",
                "wt_type",
                "WTYPE",
                "turbine_type",
                "model",
                "Type designation",
                "Model wind turbine",
            ],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    if model_type is None:
        # Only use WF-101 type if we realy don't have any other type
        model_type, alternative_used = fetch_data(
            lambda source, default=None: get_value_from_dict(
                ["wf101_type"],
                source if isinstance(source, dict) else source.to_dict(),
                default,
            ),
            preferred_source,
            alternative_source,
            alternative_used,
        )

    hub_height, alternative_used = fetch_data(
        lambda source, default=None: get_height(source, default=default),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    radius, alternative_used = fetch_data(
        lambda source, default=None: get_radius(source, default=default),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    rated_power, alternative_used = fetch_data(
        lambda source, default=None: get_rated_power_kw(source, default=default),
        preferred_source,
        alternative_source,
        alternative_used,
    )

    is_offshore, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["is_offshore", "ondergrond", "Type of location"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    wind_farm, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            [
                "nicename",
                "windfarm",
                "wind_farm",
                "WFNAME",
                "site",
                "farm id",
                "name",
                "naam",
            ],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    n_turbines, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["n_turbines", "No. of wind turbines"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )

    if rated_power is None and n_turbines is not None:
        installed_power, alternative_used = fetch_data(
            lambda source, default=None: get_installed_power(source, default=default),
            preferred_source,
            alternative_source,
            alternative_used,
        )
        if installed_power is not None:
            if n_turbines == 0:
                n_turbines = 1
            rated_power = power_to_kw(installed_power / n_turbines, known_unit="MW")

    start_date, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            [
                "start_date",
                "commission_date",
                "commissioning",
                "Date of commission",
                "year",
                "Date of original connection to grid",
            ],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    end_date, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            [
                "end_date",
                "decommission_date",
                "decommissioning",
                "Date of decommissioning",
                "Date of decommissioning",
            ],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    country, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["country", "land"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )

    cut_in_speed, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["cut_in_speed", "v_in"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    cut_out_speed, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["cut_out_speed", "v_out"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    rated_speed, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["rated_speed", "v_rated"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )

    operator, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["operator"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )
    height_offset, alternative_used = fetch_data(
        lambda source, default=None: get_value_from_dict(
            ["height_offset"],
            source if isinstance(source, dict) else source.to_dict(),
            default,
        ),
        preferred_source,
        alternative_source,
        alternative_used,
    )

    # Parse is_offshore field
    if is_offshore in ["zee", "HAV"]:
        is_offshore = True
    elif is_offshore in ["land", "LAND"]:
        is_offshore = False
    else:
        with contextlib.suppress(ValueError):
            is_offshore = bool(is_offshore)

    diameter = 2 * radius if radius is not None else None

    rated_power = power_to_kw(rated_power, diameter=diameter)
    if (
        rated_power is not None
        and diameter is not None
        and rated_power < 20
        and diameter > 0
    ):
        rated_power_v2 = power_to_kw(rated_power, diameter=2 * diameter)
        if rated_power_v2 > 1000 and radius < hub_height:
            logger.info(
                "Rated power seems unlikely low; "
                "can be reinterpreted by assuming radius is specified as diameter."
            )
            rated_power = rated_power_v2
            radius = diameter
            diameter = 2 * radius

    # Determine source
    if alternative_used:
        source = (
            merged_source_name
            or f"{preferred_source.get('source')}+{alternative_source.get('source')}"
        )
    else:
        source = preferred_source["source"]

    if is_offshore and name == wind_farm:
        name = f"{wind_farm} {turbine_id}"

    return Turbine(
        id=id_field,
        name=name,
        turbine_id=turbine_id,
        latitude=lat,
        longitude=lon,
        manufacturer=manufacturer,
        type=model_type,
        hub_height=hub_height,
        radius=radius,
        diameter=diameter,
        power_rating=rated_power,
        is_offshore=is_offshore,
        wind_farm=wind_farm,
        source=source,
        start_date=start_date,
        end_date=end_date,
        n_turbines=n_turbines,
        country=country,
        cut_in_speed=cut_in_speed,
        cut_out_speed=cut_out_speed,
        rated_speed=rated_speed,
        height_offset=height_offset,
        operator=operator,
    )


def fetch_data(
    fetcher, preferred_source, alternative_source, alternative_used: bool = False
):
    """Fetch data from preferred or alternative source using fetcher."""
    ignored_values = [None, "", 0, "NaN"]

    output = fetcher(preferred_source)
    if (
        output in ignored_values or (isinstance(output, float) and math.isnan(output))
    ) and alternative_source is not None:
        output = fetcher(alternative_source, None)
        alternative_used = alternative_used or (output not in ignored_values)

    return output, alternative_used


def count_none_fields(row, fields_to_check):
    """Count number of none-fields in row."""
    ignored_values = [None, "", 0, "NaN"]

    if row is None:
        return len(fields_to_check) + 1

    nr_of_nones = 0
    for field in fields_to_check:
        if row.get(field) in ignored_values:
            nr_of_nones += 1

    return nr_of_nones
