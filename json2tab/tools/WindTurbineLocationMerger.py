#!/usr/bin/env python3
"""Wind Turbine Location Merger with Enhanced Parallel Processing.

This script processes and merges wind turbine location data from multiple sources:
- Belgian offshore wind farms
- Bulgarian wind farms
- Netherlands/KNMI data
- WF101 database
- OpenStreetMap data

The script uses advanced parallel processing techniques to handle large datasets efficiently,
including parallel data loading, KD-tree based distance calculations, and tile-based clustering.

Author: I. Schicker, GeoSphere Austria
Date: November 2024
Updates:
      - December 2024
      - February 2024

License: created within the on-demand extremes DT, contract DE330
"""

import numpy as np
import pandas as pd

try:
    import folium
except:
    # Loading optional package folium failed
    folium = None
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import psutil
from scipy.spatial import cKDTree

from ..io.writers import save_dataframe_as_geojson
from ..logs import logger

# # Set up logging
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on Earth
    using the haversine formula.

    Args:
        lat1: Latitude of first point in degrees
        lon1: Longitude of first point in degrees
        lat2: Latitude of second point in degrees
        lon2: Longitude of second point in degrees

    Returns:
        Distance between points in kilometers

    Reference:
        https://en.wikipedia.org/wiki/Haversine_formula
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    c = 2 * np.arcsin(np.sqrt(a))

    # Radius of Earth in kilometers
    r = 6371

    return c * r


@dataclass
class PerformanceMetrics:
    """Store and track performance metrics for different operations."""

    start_time: float
    operation_times: Dict[str, float]
    memory_usage: Dict[str, float]

    @classmethod
    def initialize(cls) -> "PerformanceMetrics":
        """Initialize a new performance metrics tracker."""
        return cls(start_time=time.time(), operation_times={}, memory_usage={})

    def start_operation(self, operation_name: str) -> None:
        """Start timing an operation."""
        self.operation_times[f"{operation_name}_start"] = time.time()
        self.memory_usage[f"{operation_name}_start"] = (
            psutil.Process().memory_info().rss / 1024 / 1024
        )

    def end_operation(self, operation_name: str) -> Tuple[float, float]:
        """End timing an operation and return duration and memory usage.

        Args:
            operation_name: Name of operation

        Returns:
            Tuple[float, float]: (duration in seconds, memory usage in MB)
        """
        end_time = time.time()
        end_memory = psutil.Process().memory_info().rss / 1024 / 1024

        start_time = self.operation_times[f"{operation_name}_start"]
        start_memory = self.memory_usage[f"{operation_name}_start"]

        duration = end_time - start_time
        memory_diff = end_memory - start_memory

        self.operation_times[operation_name] = duration
        self.memory_usage[operation_name] = memory_diff

        return duration, memory_diff

    def get_total_time(self) -> float:
        """Get total elapsed time."""
        return time.time() - self.start_time

    def print_summary(self) -> None:
        """Print performance summary."""
        logger.info("\nPerformance Summary:")
        logger.info("-" * 50)
        logger.info("Operation Times:")
        for op, duration in self.operation_times.items():
            if not op.endswith("_start"):
                logger.info(f"{op:30s}: {duration:8.2f} seconds")

        logger.info("\nMemory Usage (MB):")
        for op, usage in self.memory_usage.items():
            if not op.endswith("_start"):
                logger.info(f"{op:30s}: {usage:8.2f} MB")

        logger.info(f"\nTotal Execution Time: {self.get_total_time():.2f} seconds")


class ParallelDataLoader:
    """Parallel data loading and preprocessing for wind turbine data.

    This class handles the concurrent loading and initial processing of data
    from multiple sources, optimizing I/O operations through parallel processing.

    Attributes:
        n_processes (int): Number of parallel processes to use
        metrics (PerformanceMetrics): Performance tracking metrics
    """

    def __init__(self, n_processes: Optional[int] = None):
        """Initialize the parallel data loader.

        Args:
            n_processes: Number of processes to use. Defaults to CPU count - 1
        """
        self.n_processes = n_processes or max(mp.cpu_count() - 1, 1)
        self.metrics = PerformanceMetrics.initialize()

    def load_all_data(self, file_paths: Dict[str, str]) -> Dict[str, pd.DataFrame]:
        """Load all data sources in parallel using thread pools.

        Args:
            file_paths: Dictionary mapping data source names to file paths

        Returns:
            Dictionary containing DataFrames for each data source
        """
        self.metrics.start_operation("data_loading")

        with ThreadPoolExecutor(max_workers=self.n_processes) as executor:
            futures = {
                "belgian": executor.submit(
                    self._read_belgian_data, file_paths["belgian"]
                ),
                "netherlands": executor.submit(
                    self._read_knmi_data, file_paths["netherlands"]
                ),
                "wf101": executor.submit(self._read_wf101_data, file_paths["wf101"]),
                "osm": executor.submit(self._read_and_filter_osm, file_paths["osm"]),
                "bulgarian": executor.submit(
                    self._read_bulgarian_data, file_paths["bulgarian"]
                ),
            }

            results = {}
            for name, future in futures.items():
                try:
                    results[name] = future.result()
                    logger.info(
                        f"Successfully loaded {name} data: {len(results[name])} records"
                    )
                except Exception as e:
                    logger.error(f"Error loading {name} data: {e}")
                    results[name] = None

        duration, memory = self.metrics.end_operation("data_loading")
        logger.info(
            f"Data loading completed in {duration:.2f} seconds, using {memory:.2f} MB"
        )

        return results

    @staticmethod
    def _read_belgian_data(file_path: str) -> pd.DataFrame:
        """Read and process Belgian offshore wind farm data."""
        try:
            df = pd.read_csv(file_path)

            columns = {
                "lat_merge": "latitude",
                "lon_merge": "longitude",
                "turbine_type": "type",
                "Turbine": "turbine_id",
                "WFNAME": "wind_farm",
                "hub_height": "hub_height",
                "P_rated": "power_rating",
                "diameter": "diameter",
                "v_in": "cut_in_speed",
                "v_rated": "rated_speed",
                "v_out": "cut_out_speed",
            }

            df = df[columns.keys()].rename(columns=columns)
            df["source"] = "Belgian"
            df["metadata_source"] = "Belgian"

            return df

        except Exception as e:
            logger.error(f"Error reading Belgian data: {e}")
            raise

    @staticmethod
    def _read_knmi_data(file_path: str) -> pd.DataFrame:
        """Read and process KNMI/Netherlands wind turbine data.

        Args:
            file_path: Path to the KNMI data file

        Returns:
            DataFrame with standardized KNMI turbine data

        Raises:
            Exception: If file reading or processing fails
        """
        try:
            df = pd.read_csv(
                file_path,
                sep=r"\s+",
                comment="#",
                names=["longitude", "latitude", "type", "r", "z"],
            )

            # Standardize columns
            df = df.rename(columns={"z": "hub_height", "r": "radius"})
            df["diameter"] = df["radius"] * 2
            df["source"] = "Netherlands"
            df["metadata_source"] = "Netherlands"

            return df

        except Exception as e:
            logger.error(f"Error reading KNMI data: {e}")
            raise

    @staticmethod
    def _read_wf101_data(file_path: str) -> pd.DataFrame:
        """Read and process WF101 wind turbine data.

        Args:
            file_path: Path to the WF101 data file

        Returns:
            DataFrame with standardized WF101 turbine data

        Raises:
            Exception: If file reading or processing fails
        """
        try:
            df = pd.read_csv(
                file_path,
                sep=r"\s+",
                comment="#",
                names=[
                    "longitude",
                    "latitude",
                    "height_offset",
                    "hub_height",
                    "type",
                    "country",
                ],
            )

            df["source"] = "WF101"
            df["metadata_source"] = "WF101"

            return df

        except Exception as e:
            logger.error(f"Error reading WF101 data: {e}")
            raise

    def _read_and_filter_osm(self, file_path: str) -> pd.DataFrame:
        """Read and filter OpenStreetMap wind turbine data in parallel chunks.

        Args:
            file_path: Path to the OSM data file

        Returns:
            DataFrame with filtered OSM turbine data

        Raises:
            Exception: If file reading or processing fails
        """
        try:
            self.metrics.start_operation("osm_processing")

            # Get total number of rows
            total_rows = sum(1 for _ in open(file_path)) - 1
            chunk_size = max(total_rows // (self.n_processes * 4), 1000)

            logger.info(f"Processing {total_rows} OSM records in chunks of {chunk_size}")

            # Process chunks in parallel
            chunks = []
            with ProcessPoolExecutor(max_workers=self.n_processes) as executor:
                futures = []
                for start in range(0, total_rows, chunk_size):
                    future = executor.submit(
                        self._process_osm_chunk, file_path, start, chunk_size
                    )
                    futures.append(future)

                for i, future in enumerate(as_completed(futures)):
                    try:
                        chunk = future.result()
                        if chunk is not None:
                            chunks.append(chunk)
                        if (i + 1) % 10 == 0:
                            logger.info(f"Processed {i + 1}/{len(futures)} OSM chunks")
                    except Exception as e:
                        logger.error(f"Error processing OSM chunk: {e}")

            # Combine chunks
            result = pd.concat(chunks, ignore_index=True)

            duration, memory = self.metrics.end_operation("osm_processing")
            logger.info(
                f"OSM processing completed in {duration:.2f} seconds, using {memory:.2f} MB"
            )

            return result

        except Exception as e:
            logger.error(f"Error in OSM processing: {e}")
            raise

    @staticmethod
    def _process_osm_chunk(
        file_path: str, start: int, chunk_size: int
    ) -> Optional[pd.DataFrame]:
        """Process a chunk of OSM data with geographic filtering.

        Args:
            file_path: Path to the OSM data file
            start: Starting row for this chunk
            chunk_size: Number of rows to process

        Returns:
            Filtered DataFrame for this chunk or None if no valid data
        """
        try:
            chunk = pd.read_csv(file_path, skiprows=range(1, start + 1), nrows=chunk_size)

            # Filter to European bounds
            bounds = {"lat_min": 35.0, "lat_max": 72.0, "lon_min": -25.0, "lon_max": 40.0}

            # Apply geographic filter
            mask = (
                (chunk["Latitude"] >= bounds["lat_min"])
                & (chunk["Latitude"] <= bounds["lat_max"])
                & (chunk["Longitude"] >= bounds["lon_min"])
                & (chunk["Longitude"] <= bounds["lon_max"])
            )

            filtered = chunk[mask].copy()

            if len(filtered) > 0:
                # Standardize columns
                filtered = filtered.rename(
                    columns={
                        "Name": "name",
                        "Latitude": "latitude",
                        "Longitude": "longitude",
                    }
                )
                filtered["source"] = "OSM"
                filtered["metadata_source"] = "OSM"
                return filtered

            return None

        except Exception as e:
            logger.error(f"Error processing OSM chunk at row {start}: {e}")
            return None

    @staticmethod
    def _read_bulgarian_data(file_path: str) -> pd.DataFrame:
        """Read and process Bulgarian wind farm data.

        Args:
            file_path: Path to the Bulgarian data file

        Returns:
            DataFrame with standardized Bulgarian wind farm data

        Raises:
            Exception: If file reading or processing fails
        """
        try:
            df = pd.read_csv(file_path, sep=";")

            # Standardize columns
            df = df.rename(columns={"name": "wind_farm", "power_kw": "power_rating"})

            # Convert power to MW
            df["power_rating"] = df["power_rating"] / 1000.0
            df["source"] = "Bulgarian"
            df["metadata_source"] = "Bulgarian"

            return df

        except Exception as e:
            logger.error(f"Error reading Bulgarian data: {e}")
            raise


class VisualizationManager:
    """Manages the creation of interactive visualizations for wind turbine data.

    This class handles the creation of maps and statistical visualizations
    using folium and other visualization libraries.
    """

    def __init__(self):
        """Initialize the visualization manager."""
        self.metrics = PerformanceMetrics.initialize()

    def create_map(self, merged_df: pd.DataFrame, output_file: str) -> None:
        """Create an interactive map visualization of turbine locations.

        Args:
            merged_df: DataFrame containing merged turbine data
            output_file: Path to save the HTML map

        Raises:
            Exception: If file reading or processing fails

        """
        self.metrics.start_operation("map_creation")

        try:
            # Calculate map center
            center_lat = merged_df["latitude"].mean()
            center_lon = merged_df["longitude"].mean()

            # Create base map
            m = folium.Map(
                location=[center_lat, center_lon], zoom_start=6, tiles="OpenStreetMap"
            )

            # Define color scheme
            color_map = {
                "Belgian": "red",
                "Bulgarian": "orange",
                "Netherlands": "blue",
                "WF101": "green",
                "OSM": "purple",
            }

            # Add markers with clusters
            for _, row in merged_df.iterrows():
                color = color_map.get(row["source"], "gray")

                popup_content = self._create_popup_content(row)

                folium.CircleMarker(
                    location=[row["latitude"], row["longitude"]],
                    radius=5,
                    color=color,
                    fill=True,
                    popup=popup_content,
                ).add_to(m)

            # Add legend
            self._add_legend(m, color_map)

            # Save map
            m.save(output_file)

            duration, memory = self.metrics.end_operation("map_creation")
            logger.info(
                f"Map created in {duration:.2f} seconds, " f"using {memory:.2f} MB"
            )

        except Exception as e:
            logger.error(f"Error creating map: {e}")
            raise

    @staticmethod
    def _create_popup_content(row: pd.Series) -> str:
        """Create HTML content for marker popups."""
        return f"""
        <div style="font-family: Arial; font-size: 12px;">
            <b>ID:</b> {row.get('turbine_id', 'Unknown')}<br>
            <b>Type:</b> {row.get('type', 'Unknown')}<br>
            <b>Source:</b> {row['source']}<br>
            <b>Metadata:</b> {row['metadata_source']}<br>
            <b>Wind Farm:</b> {row.get('wind_farm', 'N/A')}<br>
            <b>Hub Height:</b> {f"{row['hub_height']} m" if pd.notnull(row.get('hub_height')) else 'N/A'}<br>
            <b>Power Rating:</b> {f"{row['power_rating']:.1f} MW" if pd.notnull(row.get('power_rating')) else 'N/A'}<br>
            <b>Diameter:</b> {f"{row['diameter']} m" if pd.notnull(row.get('diameter')) else 'N/A'}<br>
            <b>Region:</b> {row.get('region', 'Unknown')}<br>
            <b>Coordinates:</b> {row['latitude']:.4f}, {row['longitude']:.4f}
        </div>
        """

    @staticmethod
    def _add_legend(m, color_map: Dict[str, str]) -> None:
        """Add legend to the map."""
        legend_html = f"""
        <div style="position: fixed;
                    bottom: 50px; right: 50px;
                    border:2px solid grey; z-index:9999;
                    background-color:white;
                    padding: 10px;
                    font-size:14px;">
        {''.join(f'<p><i class="fa fa-circle" style="color:{color}"></i> {source}</p>'
                 for source, color in color_map.items())}
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))


class StatisticsManager:
    """Manages statistical analysis and reporting of wind turbine data.

    This class handles the calculation and presentation of various statistics
    about the merged turbine dataset, with robust handling of missing columns.
    """

    def __init__(self):
        """Initialize the statistics manager."""
        self.metrics = PerformanceMetrics.initialize()

    def generate_report(self, merged_df: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive statistics report with safe column access.

        Args:
            merged_df: DataFrame containing merged turbine data

        Returns:
            Dictionary containing various statistics
        """
        self.metrics.start_operation("statistics")

        try:
            # Ensure region column exists
            if "region" not in merged_df.columns:
                # Try to infer region from source and coordinates
                merged_df["region"] = self._infer_regions(merged_df)

            stats = {
                "total_turbines": len(merged_df),
                "by_source": merged_df["source"].value_counts().to_dict(),
                "by_metadata": merged_df["metadata_source"].value_counts().to_dict(),
                "by_region": merged_df["region"].value_counts().to_dict(),
                "power_stats": self._calculate_power_stats(merged_df),
                "height_stats": self._calculate_height_stats(merged_df),
                "matching_stats": self._calculate_matching_stats(merged_df),
            }

            duration, memory = self.metrics.end_operation("statistics")
            logger.info(
                f"Statistics generated in {duration:.2f} seconds, "
                f"using {memory:.2f} MB"
            )

            return stats

        except Exception as e:
            logger.error(f"Error generating statistics: {e!s}")
            return self._generate_fallback_stats(merged_df)

    def _infer_regions(self, df: pd.DataFrame) -> pd.Series:
        """Infer regions from source and coordinates.

        Args:
            df: DataFrame containing turbine data

        Returns:
            Series containing inferred regions
        """
        regions = pd.Series(index=df.index, data="Other")

        # Belgian region
        mask_belgian = df["source"] == "Belgian"
        regions[mask_belgian] = "Belgium"

        # Bulgarian region
        mask_bulgarian = (
            (df["latitude"] >= 41.2)
            & (df["latitude"] <= 44.2)
            & (df["longitude"] >= 22.3)
            & (df["longitude"] <= 28.6)
        )
        regions[mask_bulgarian] = "Bulgaria"

        # Netherlands region
        mask_netherlands = (
            (df["latitude"] >= 50.7)
            & (df["latitude"] <= 53.6)
            & (df["longitude"] >= 3.3)
            & (df["longitude"] <= 7.2)
        )
        regions[mask_netherlands] = "Netherlands"

        return regions

    def _generate_fallback_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate basic statistics when full statistics generation fails.

        Args:
            df: DataFrame containing turbine data

        Returns:
            Dictionary containing basic statistics
        """
        stats = {
            "total_turbines": len(df),
            "by_source": df["source"].value_counts().to_dict(),
        }

        # Try to add additional stats safely
        try:
            if "metadata_source" in df.columns:
                stats["by_metadata"] = df["metadata_source"].value_counts().to_dict()

            if "power_rating" in df.columns:
                stats["power_stats"] = {
                    "total_power_mw": df["power_rating"].sum(),
                    "mean_power_mw": df["power_rating"].mean(),
                }

            if "hub_height" in df.columns:
                stats["height_stats"] = {"mean_height": df["hub_height"].mean()}
        except Exception as e:
            logger.warning(f"Error generating fallback stats: {e!s}")

        return stats

    @staticmethod
    def _calculate_power_stats(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate power-related statistics safely."""
        stats = {}
        if "power_rating" in df.columns:
            power_data = df["power_rating"].dropna()
            stats.update(
                {
                    "total_power_mw": power_data.sum(),
                    "mean_power_mw": power_data.mean(),
                    "max_power_mw": power_data.max(),
                    "power_coverage": len(power_data) / len(df),
                }
            )
        return stats

    @staticmethod
    def _calculate_height_stats(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate height-related statistics safely."""
        stats = {}
        if "hub_height" in df.columns:
            height_data = df["hub_height"].dropna()
            stats.update(
                {
                    "mean_height": height_data.mean(),
                    "max_height": height_data.max(),
                    "height_coverage": len(height_data) / len(df),
                }
            )
        return stats

    @staticmethod
    def _calculate_matching_stats(df: pd.DataFrame) -> Dict[str, float]:
        """Calculate metadata matching statistics safely."""
        stats = {}
        if "metadata_source" in df.columns and "source" in df.columns:
            stats["metadata_success_rate"] = len(
                df[df["metadata_source"] != df["source"]]
            ) / len(df)

        required_columns = ["hub_height", "power_rating", "diameter"]
        if all(col in df.columns for col in required_columns):
            stats["complete_records"] = len(df.dropna(subset=required_columns)) / len(df)

        return stats

    def print_report(self, stats: Dict[str, Any]) -> None:
        """Print formatted statistics report.

        Args:
            stats: Dictionary containing calculated statistics
        """
        logger.info("\nWind Turbine Data Analysis Report")
        logger.info("=" * 50)

        # Overall statistics
        logger.info("\nOverall Statistics:")
        logger.info(f"Total turbines: {stats['total_turbines']:,}")

        # Source distribution
        logger.info("\nDistribution by Source:")
        for source, count in stats["by_source"].items():
            logger.info(
                f"{source:15s}: {count:,} turbines ({count/stats['total_turbines']*100:.1f}%)"
            )

        # Metadata sources
        logger.info("\nMetadata Sources:")
        for source, count in stats["by_metadata"].items():
            logger.info(
                f"{source:15s}: {count:,} turbines ({count/stats['total_turbines']*100:.1f}%)"
            )

        # Regional distribution
        logger.info("\nRegional Distribution:")
        for region, count in stats["by_region"].items():
            logger.info(
                f"{region:15s}: {count:,} turbines ({count/stats['total_turbines']*100:.1f}%)"
            )

        # Power statistics
        logger.info("\nPower Statistics:")
        logger.info(f"Total capacity: {stats['power_stats']['total_power_mw']:,.1f} MW")
        logger.info(
            f"Mean turbine capacity: {stats['power_stats']['mean_power_mw']:.1f} MW"
        )
        logger.info(
            f"Maximum turbine capacity: {stats['power_stats']['max_power_mw']:.1f} MW"
        )
        logger.info(
            f"Power data coverage: {stats['power_stats']['power_coverage']*100:.1f}%"
        )

        # Height statistics
        logger.info("\nHeight Statistics:")
        logger.info(f"Mean hub height: {stats['height_stats']['mean_height']:.1f} m")
        logger.info(f"Maximum hub height: {stats['height_stats']['max_height']:.1f} m")
        logger.info(
            f"Height data coverage: {stats['height_stats']['height_coverage']*100:.1f}%"
        )

        # Matching statistics
        logger.info("\nMatching Statistics:")
        logger.info(
            f"Metadata matching success rate: {stats['matching_stats']['metadata_success_rate']*100:.1f}%"
        )
        logger.info(
            f"Complete records: {stats['matching_stats']['complete_records']*100:.1f}%"
        )


def add_region_info(merged_data: pd.DataFrame) -> pd.DataFrame:
    """Add region information to merged data."""
    # Create region column if it doesn't exist
    if "region" not in merged_data.columns:
        merged_data["region"] = "Other"

    # Set regions based on source and coordinates
    merged_data.loc[merged_data["source"] == "Belgian", "region"] = "Belgium"

    # Bulgarian region
    bulgarian_mask = (
        (merged_data["latitude"] >= 41.2)
        & (merged_data["latitude"] <= 44.2)
        & (merged_data["longitude"] >= 22.3)
        & (merged_data["longitude"] <= 28.6)
    )
    merged_data.loc[bulgarian_mask, "region"] = "Bulgaria"

    # Netherlands region
    netherlands_mask = (
        (merged_data["latitude"] >= 50.7)
        & (merged_data["latitude"] <= 53.6)
        & (merged_data["longitude"] >= 3.3)
        & (merged_data["longitude"] <= 7.2)
    )
    merged_data.loc[netherlands_mask, "region"] = "Netherlands"

    return merged_data


def validate_data_sources(data_sources: Dict[str, pd.DataFrame]) -> bool:
    """Validate loaded data sources for required columns and data quality.

    Args:
        data_sources: Dictionary of data sources

    Returns:
        bool: True if validation passes, False otherwise
    """
    required_columns = {
        "belgian": ["latitude", "longitude", "type", "power_rating", "hub_height"],
        "netherlands": ["latitude", "longitude", "type", "hub_height"],
        "wf101": ["latitude", "longitude", "type", "hub_height"],
        "osm": ["latitude", "longitude"],
        "bulgarian": ["latitude", "longitude", "power_rating"],
    }

    for source, df in data_sources.items():
        if df is None:
            logger.warning(f"Missing data source: {source}")
            continue

        logger.info(f"\nValidating {source} data:")

        # Check required columns
        missing_cols = [col for col in required_columns[source] if col not in df.columns]
        if missing_cols:
            logger.error(f"Missing required columns in {source}: {missing_cols}")
            return False

        # Check for null values in coordinates
        null_coords = df[["latitude", "longitude"]].isnull().any(axis=1).sum()
        if null_coords > 0:
            logger.warning(f"Found {null_coords} rows with null coordinates in {source}")

        # Check coordinate ranges
        invalid_coords = df[(df["latitude"].abs() > 90) | (df["longitude"].abs() > 180)]
        if len(invalid_coords) > 0:
            logger.error(
                f"Found {len(invalid_coords)} rows with invalid coordinates in {source}"
            )
            return False

        logger.info(f"Data validation passed for {source}")
        logger.info(f"Shape: {df.shape}")
        logger.info(
            f"Coordinate ranges: lat [{df['latitude'].min():.4f}, {df['latitude'].max():.4f}], "
            f"lon [{df['longitude'].min():.4f}, {df['longitude'].max():.4f}]"
        )

        if "power_rating" in df.columns:
            logger.info(
                f"Power rating range: [{df['power_rating'].min():.1f}, "
                f"{df['power_rating'].max():.1f}] MW"
            )

    return True


def merge_data_hierarchically(belgian_df, wf101_df, knmi_df, osm_df, bulgarian_df):
    """Merge wind turbine data following the hierarchical strategy."""
    logger.info("\nStarting hierarchical data merging...")

    # Step 1: Merge WF101 and KNMI to create WFKN
    def create_wfkn():
        logger.info("Creating WFKN (WF101 + KNMI merged dataset)...")
        if wf101_df is None or knmi_df is None:
            return wf101_df if wf101_df is not None else knmi_df

        regional_data = []

        # Define regions with more precise boundaries
        regions = {
            "dutch_offshore": {
                "lat_min": 51.5,
                "lat_max": 54.5,
                "lon_min": 2.0,
                "lon_max": 7.2,
                "preferred": "Netherlands",
            },
            "uk_offshore": {
                "lat_min": 51.0,
                "lat_max": 56.0,
                "lon_min": -5.0,
                "lon_max": 2.0,
                "preferred": "KNMI",
            },
            "netherlands_onshore": {
                "lat_min": 50.7,
                "lat_max": 53.6,
                "lon_min": 3.3,
                "lon_max": 7.2,
                "preferred": "Netherlands",
            },
            "germany": {
                "lat_min": 47.0,
                "lat_max": 55.0,
                "lon_min": 5.0,
                "lon_max": 15.0,
                "preferred": "WF101",
            },
        }

        # Process each region
        for region_name, bounds in regions.items():
            logger.info(f"Processing {region_name}...")

            # Get points in this region from both datasets
            knmi_mask = (
                knmi_df["latitude"].between(bounds["lat_min"], bounds["lat_max"])
            ) & (knmi_df["longitude"].between(bounds["lon_min"], bounds["lon_max"]))
            wf101_mask = (
                wf101_df["latitude"].between(bounds["lat_min"], bounds["lat_max"])
            ) & (wf101_df["longitude"].between(bounds["lon_min"], bounds["lon_max"]))

            knmi_region = knmi_df[knmi_mask].copy()
            wf101_region = wf101_df[wf101_mask].copy()

            if bounds["preferred"] == "Netherlands" or bounds["preferred"] == "KNMI":
                # Use KNMI as primary source
                if len(knmi_region) > 0:
                    knmi_region["source"] = "Netherlands"
                    knmi_region["metadata_source"] = "Netherlands"
                    regional_data.append(knmi_region)

                    # Remove overlapping WF101 points
                    if len(wf101_region) > 0:
                        knmi_tree = cKDTree(knmi_region[["latitude", "longitude"]].values)
                        distances, _ = knmi_tree.query(
                            wf101_region[["latitude", "longitude"]].values,
                            k=1,
                            distance_upper_bound=0.001,  # 100m threshold
                        )
                        non_overlapping = distances >= 0.001
                        if non_overlapping.any():
                            wf101_unique = wf101_region[non_overlapping].copy()
                            wf101_unique["source"] = "WF101"
                            wf101_unique["metadata_source"] = "WF101"
                            regional_data.append(wf101_unique)

            elif bounds["preferred"] == "WF101":
                # Use WF101 as primary source
                if len(wf101_region) > 0:
                    wf101_region["source"] = "WF101"
                    wf101_region["metadata_source"] = "WF101"
                    regional_data.append(wf101_region)

                    # Add non-overlapping KNMI points
                    if len(knmi_region) > 0:
                        wf101_tree = cKDTree(
                            wf101_region[["latitude", "longitude"]].values
                        )
                        distances, _ = wf101_tree.query(
                            knmi_region[["latitude", "longitude"]].values,
                            k=1,
                            distance_upper_bound=0.001,
                        )
                        non_overlapping = distances >= 0.001
                        if non_overlapping.any():
                            knmi_unique = knmi_region[non_overlapping].copy()
                            knmi_unique["source"] = "Netherlands"
                            knmi_unique["metadata_source"] = "Netherlands"
                            regional_data.append(knmi_unique)

        # Combine all regional data
        if regional_data:
            wfkn = pd.concat(regional_data, ignore_index=True)
            logger.info(f"Created WFKN dataset with {len(wfkn)} records")

            # Log regional statistics
            for region_name in regions:
                mask = (
                    wfkn["latitude"].between(
                        regions[region_name]["lat_min"], regions[region_name]["lat_max"]
                    )
                ) & (
                    wfkn["longitude"].between(
                        regions[region_name]["lon_min"], regions[region_name]["lon_max"]
                    )
                )
                region_count = mask.sum()
                logger.info(f"{region_name}: {region_count} turbines")

            return wfkn
        else:
            logger.warning("No data to combine in WFKN")
            return pd.DataFrame()

    # Step 2: Create BEWFKN
    def create_bewfkn(wfkn_df):
        logger.info("Creating BEWFKN (Belgian + WFKN merged dataset)...")
        if belgian_df is None:
            return wfkn_df

        # Define Belgian offshore zone
        belgian_zone = {"lat_min": 51.0, "lat_max": 52.0, "lon_min": 2.0, "lon_max": 3.5}

        # Remove WFKN points in Belgian zone
        if wfkn_df is not None:
            zone_mask = ~(
                (
                    wfkn_df["latitude"].between(
                        belgian_zone["lat_min"], belgian_zone["lat_max"]
                    )
                )
                & (
                    wfkn_df["longitude"].between(
                        belgian_zone["lon_min"], belgian_zone["lon_max"]
                    )
                )
            )
            wfkn_filtered = wfkn_df[zone_mask].copy()
        else:
            wfkn_filtered = pd.DataFrame()

        return pd.concat([belgian_df, wfkn_filtered], ignore_index=True)

    # Step 3: Create BUSM (Bulgarian + OSM)
    def create_busm():
        """Create BUSM with WF101 taking precedence over OSM data."""
        logger.info("Creating BUSM (Bulgarian + OSM merged dataset)...")
        if osm_df is None:
            return None

        busm = osm_df.copy()

        # First, remove OSM points that are close to WF101 points
        if wf101_df is not None:
            logger.info("Applying WF101 priority over OSM data...")
            wf101_tree = cKDTree(wf101_df[["latitude", "longitude"]].values)

            # Find OSM points near WF101 points
            distances, _ = wf101_tree.query(
                busm[["latitude", "longitude"]].values,
                k=1,
                distance_upper_bound=0.005,  # 500m threshold
            )

            # Keep only OSM points that are not near WF101 points
            far_from_wf101 = distances >= 0.005
            busm = busm[far_from_wf101].copy()
            logger.info(
                f"Removed {(~far_from_wf101).sum()} OSM points that overlap with WF101 data"
            )

        # Then proceed with Bulgarian data integration
        if bulgarian_df is not None:
            # Define Bulgarian region
            bg_region = {
                "lat_min": 41.2,
                "lat_max": 44.2,
                "lon_min": 22.3,
                "lon_max": 28.6,
            }

            # Process Bulgarian region as before
            bg_mask = (
                busm["latitude"].between(bg_region["lat_min"], bg_region["lat_max"])
            ) & (busm["longitude"].between(bg_region["lon_min"], bg_region["lon_max"]))

            if bg_mask.any():
                bg_points = busm[bg_mask]
                bulgarian_tree = cKDTree(bulgarian_df[["latitude", "longitude"]].values)

                distances, indices = bulgarian_tree.query(
                    bg_points[["latitude", "longitude"]].values,
                    k=1,
                    distance_upper_bound=0.02,  # 2km threshold
                )

                matches = distances < 0.02
                if matches.any():
                    matched_indices = bg_points.index[matches]
                    for col in bulgarian_df.columns:
                        if col not in ["latitude", "longitude"]:
                            busm.loc[matched_indices, col] = bulgarian_df.iloc[
                                indices[matches]
                            ][col].values
                    busm.loc[matched_indices, "metadata_source"] = "Bulgarian"

        return busm

    @staticmethod
    def _point_in_hull(point, hull_points):
        """Check if a point is inside a convex hull using ray casting algorithm."""

        def is_left(p0, p1, p2):
            return (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])

        n = len(hull_points)
        inside = False

        j = n - 1
        for i in range(n):
            if ((hull_points[i][1] > point[1]) != (hull_points[j][1] > point[1])) and (
                point[0]
                < (hull_points[j][0] - hull_points[i][0])
                * (point[1] - hull_points[i][1])
                / (hull_points[j][1] - hull_points[i][1])
                + hull_points[i][0]
            ):
                inside = not inside
            j = i

        return inside

    # Step 4: Final merge with modified hierarchy
    def merge_final(bewfkn_df, busm_df):
        logger.info("Creating final merged dataset...")

        # Start with BEWFKN
        final_data = pd.DataFrame() if bewfkn_df is None else bewfkn_df.copy()

        # Add WF101 data that's not in BEWFKN
        if wf101_df is not None:
            if len(final_data) > 0:
                bewfkn_tree = cKDTree(final_data[["latitude", "longitude"]].values)
                distances, _ = bewfkn_tree.query(
                    wf101_df[["latitude", "longitude"]].values,
                    k=1,
                    distance_upper_bound=0.005,
                )
                unique_wf101 = distances >= 0.005
                if unique_wf101.any():
                    final_data = pd.concat(
                        [final_data, wf101_df[unique_wf101]], ignore_index=True
                    )
            else:
                final_data = wf101_df.copy()

        # Add remaining BUSM data
        if busm_df is not None and len(final_data) > 0:
            final_tree = cKDTree(final_data[["latitude", "longitude"]].values)
            distances, _ = final_tree.query(
                busm_df[["latitude", "longitude"]].values, k=1, distance_upper_bound=0.005
            )
            unique_busm = distances >= 0.005
            if unique_busm.any():
                final_data = pd.concat(
                    [final_data, busm_df[unique_busm]], ignore_index=True
                )
        elif busm_df is not None:
            final_data = busm_df.copy()

        return final_data

    # Execute merge pipeline
    wfkn = create_wfkn()
    bewfkn = create_bewfkn(wfkn)
    busm = create_busm()
    final_dataset = merge_final(bewfkn, busm)

    return final_dataset


def create_quick_plot(
    merged_df: pd.DataFrame, output_file: str = "wind_turbines_quick.png"
):
    """Create a simple static plot for quick visualization using matplotlib."""
    logger.info("Creating quick plot...")

    try:
        import matplotlib.pyplot as plt

        # Set figure size
        plt.figure(figsize=(15, 10))

        # Color scheme matching the interactive map
        colors = {
            "Belgian": "red",
            "Bulgarian": "orange",
            "Netherlands": "blue",
            "WF101": "green",
            "OSM": "purple",
        }

        # Plot each source
        plt.gca().set_facecolor("#f0f0f0")  # Light gray background
        for source, color in colors.items():
            mask = merged_df["source"] == source
            if mask.any():
                plt.scatter(
                    merged_df.loc[mask, "longitude"],
                    merged_df.loc[mask, "latitude"],
                    c=color,
                    alpha=0.6,
                    s=15,
                    label=f"{source} ({mask.sum():,})",
                )

        # Customize plot
        plt.xlabel("Longitude", fontsize=12)
        plt.ylabel("Latitude", fontsize=12)
        plt.title("Wind Turbine Locations by Source", fontsize=14, pad=20)
        plt.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
        plt.grid(True, alpha=0.3)

        # Set axis limits to focus on relevant area
        plt.xlim(-5, 30)
        plt.ylim(40, 56)

        # Add bounding boxes for key regions
        regions = {
            "Belgian Offshore": ([2.0, 3.5], [51.0, 52.0], "red"),
            "Dutch Offshore": ([2.0, 7.2], [51.5, 54.5], "blue"),
            "Bulgarian": ([22.3, 28.6], [41.2, 44.2], "orange"),
        }

        for name, (lon_bounds, lat_bounds, color) in regions.items():
            lon_min, lon_max = lon_bounds
            lat_min, lat_max = lat_bounds
            plt.plot(
                [lon_min, lon_max, lon_max, lon_min, lon_min],
                [lat_min, lat_min, lat_max, lat_max, lat_min],
                "--",
                color=color,
                alpha=0.7,
                linewidth=1,
                label=f"{name} Region",
            )

        # Adjust layout to prevent label cutoff
        plt.tight_layout()

        # Save plot
        plt.savefig(output_file, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Quick plot saved to {output_file}")

    except Exception as e:
        logger.error(f"Error creating quick plot: {e}")
        logger.exception("Detailed error information:")


def WindTurbineLocationMerger(stamp: Optional[str] = None):
    """Main execution function for the wind turbine location merger."""
    try:
        # Initialize performance tracking
        overall_metrics = PerformanceMetrics.initialize()
        overall_metrics.start_operation("total_execution")

        if stamp is None:
            stamp = "012025"

        # Initialize components
        logger.info("Initializing components...")
        n_processes = max(mp.cpu_count() - 1, 1)
        loader = ParallelDataLoader(n_processes=n_processes)
        stats_manager = StatisticsManager()

        # File paths
        file_paths = {
            "belgian": "gdrive_data/belgian_offshore_with_types.csv",
            "netherlands": "gdrive_data/wind_turbine_coordinates_NETHERLANDS_750m_2023.tab",
            "wf101": "gdrive_data/wf101.txt",
            "osm": "gdrive_data/wind_turbines_data_OSM.csv",
            "bulgarian": "gdrive_data/bulgarian_wind_farms_combined.csv",
        }

        if stamp != "012025":
            file_paths["osm"] = f"static_data/turbine_locations_osm_{stamp}.csv"

        # Validate file existence
        for source, path in file_paths.items():
            if not os.path.exists(path):
                raise FileNotFoundError(f"Input file for {source} not found: {path}")

        # Load data
        logger.info("\nLoading data from all sources...")
        data_sources = loader.load_all_data(file_paths)

        # Validate loaded data
        logger.info("\nValidating data sources...")
        if not validate_data_sources(data_sources):
            raise ValueError("Data validation failed")

        # Merge data using hierarchical approach
        logger.info("\nMerging data sources hierarchically...")
        merged_data = merge_data_hierarchically(
            data_sources["belgian"],
            data_sources["wf101"],
            data_sources["netherlands"],
            data_sources["osm"],
            data_sources["bulgarian"],
        )

        # Verify merged data
        logger.info("\nVerifying merged data...")
        required_columns = ["latitude", "longitude", "source", "metadata_source"]
        missing_cols = [col for col in required_columns if col not in merged_data.columns]
        if missing_cols:
            raise ValueError(f"Merged data missing required columns: {missing_cols}")

        # Save merged data
        output_file = f"wind_turbines_{stamp}.csv"
        logger.info(f"\nSaving merged data to {output_file}...")
        merged_data.to_csv(output_file, index=False)
        logger.info(f"Saved {len(merged_data)} records to {output_file}")

        # Save as GeoJSON
        output_geojson = f"wind_turbines_{stamp}.geojson"
        logger.info("\nSaving data as GeoJSON...")
        save_dataframe_as_geojson(merged_data, output_geojson)

        # Create quick plot first
        create_quick_plot(merged_data, f"wind_turbines_quick_{stamp}.png")

        # Optionally create interactive visualization with memory warning
        try:
            logger.info("\nCreating interactive visualization...")
            memory_available = psutil.virtual_memory().available / (1024 * 1024)  # MB
            if memory_available > 3000:  # Only create if >3GB available
                viz_manager = VisualizationManager()
                output_map = f"wind_turbines_map_{stamp}.html"
                viz_manager.create_map(merged_data, output_map)
                logger.info(f"Interactive map saved to {output_map}")
            else:
                logger.warning(
                    "Insufficient memory for interactive visualization. "
                    "Please use the quick plot for overview."
                )
        except Exception as e:
            logger.warning(f"Could not create interactive visualization: {e}")

        # Generate and print statistics
        logger.info("\nGenerating statistics...")
        stats = stats_manager.generate_report(merged_data)
        stats_manager.print_report(stats)

        # Print final performance metrics
        duration, memory = overall_metrics.end_operation("total_execution")
        logger.info(f"\nTotal execution completed in {duration:.2f} seconds")
        logger.info(f"Peak memory usage: {memory:.2f} MB")

        return merged_data

    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        logger.exception("Detailed error information:")
        raise


if __name__ == "__main__":
    try:
        WindTurbineLocationMerger()
    except KeyboardInterrupt:
        logger.info("\nProcess interrupted by user")
    except Exception as e:
        logger.error(f"\nFatal error: {e}")
        logger.exception("Detailed error information:")
    finally:
        logger.info("\nProcess completed")
