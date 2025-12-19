"""Handles visualization of wind turbine locations with multiple styles."""

from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt

from .DomainConfig import DomainConfig


class TurbineVisualizer:
    """Handles visualization of wind turbine locations with multiple styles."""

    def __init__(self, config):
        """Initialize visualizer with configuration.

        Args:
            config (dict): Configuration dictionary
        """
        self.config = config
        self.viz_config = config["visualization"]
        self.bounds = self._get_bounds()

    def _get_bounds(self):
        """Get domain bounds from config."""
        if self.config["subsetting"]["method"] == "bbox":
            return tuple(self.config["subsetting"]["bbox"])

        # Get bounds from domain config
        domain = DomainConfig.from_config(self.config["subsetting"]["domain"])
        return domain.get_bounds()

    def create_regional_plot(self, data, output_path):
        """Create regional style plot with rivers and broader context."""
        fig, ax = plt.subplots(
            figsize=(
                self.viz_config["figure"]["width"],
                self.viz_config["figure"]["height"],
            ),
            subplot_kw={"projection": ccrs.PlateCarree()},
        )

        min_lon, min_lat, max_lon, max_lat = self.bounds
        ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())

        # Add features
        regional_config = self.viz_config["regional"]
        ax.add_feature(cfeature.LAND, facecolor=regional_config["land_color"])
        ax.add_feature(cfeature.COASTLINE, edgecolor=regional_config["coastline_color"])
        ax.add_feature(
            cfeature.BORDERS,
            linestyle=regional_config["border_style"],
            edgecolor=regional_config["border_color"],
        )

        if regional_config["show_rivers"]:
            ax.add_feature(cfeature.RIVERS, edgecolor=regional_config["rivers_color"])

        # Plot turbines
        for feature in data["features"]:
            lon, lat = feature["geometry"]["coordinates"]
            ax.plot(
                lon,
                lat,
                "o",
                color=regional_config["turbine_color"],
                markersize=regional_config["turbine_size"],
                transform=ccrs.PlateCarree(),
                label="Turbine"
                if "Turbine" not in ax.get_legend_handles_labels()[1]
                else "",
            )

        ax.set_title("Turbine Locations in Region of Interest")
        ax.legend()

        plt.savefig(
            output_path, bbox_inches="tight", dpi=self.viz_config["figure"]["dpi"]
        )
        plt.close()

    def create_domain_plot(self, data, output_path):
        """Create domain-focused style plot."""
        fig, ax = plt.subplots(
            figsize=(
                self.viz_config["figure"]["width"],
                self.viz_config["figure"]["height"],
            ),
            subplot_kw={"projection": ccrs.PlateCarree()},
        )

        min_lon, min_lat, max_lon, max_lat = self.bounds
        ax.set_extent([min_lon, max_lon, min_lat, max_lat], crs=ccrs.PlateCarree())

        # Add features
        domain_config = self.viz_config["domain"]
        ax.add_feature(cfeature.LAND, facecolor=domain_config["land_color"])
        ax.add_feature(cfeature.OCEAN, facecolor=domain_config["ocean_color"])
        ax.add_feature(cfeature.COASTLINE, edgecolor=domain_config["coastline_color"])

        # Plot turbines
        for feature in data["features"]:
            lon, lat = feature["geometry"]["coordinates"]
            ax.plot(
                lon,
                lat,
                "o",
                color=domain_config["turbine_color"],
                markersize=domain_config["turbine_size"],
                transform=ccrs.PlateCarree(),
                label="Turbine"
                if "Turbine" not in ax.get_legend_handles_labels()[1]
                else "",
            )

        if domain_config["show_dotted_bounds"]:
            # Add dotted boundary lines if configured
            ax.plot(
                [min_lon, max_lon, max_lon, min_lon, min_lon],
                [min_lat, min_lat, max_lat, max_lat, min_lat],
                ":",
                color="black",
                transform=ccrs.PlateCarree(),
            )

        ax.set_title("Wind Turbine Locations - Domain-based")
        ax.legend()

        plt.savefig(
            output_path, bbox_inches="tight", dpi=self.viz_config["figure"]["dpi"]
        )
        plt.close()

    def visualize(self, data):
        """Create visualizations based on configuration."""
        output_dir = Path(self.config["output"]["directory"])
        output_dir.mkdir(parents=True, exist_ok=True)

        style = self.viz_config["style"]

        if style in ["regional", "both"]:
            regional_path = output_dir / self.config["output"]["files"]["regional_plot"]
            self.create_regional_plot(data, regional_path)

        if style in ["domain", "both"]:
            domain_path = output_dir / self.config["output"]["files"]["domain_plot"]
            self.create_domain_plot(data, domain_path)
