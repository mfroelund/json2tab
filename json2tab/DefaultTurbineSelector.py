"""Selector for default turbine type based on lat, lon."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RegionInfo:
    """Information about a geographical region and its typical turbine characteristics."""

    name: str
    default_onshore: str  # Default turbine type for onshore
    default_offshore: str  # Default turbine type for offshore
    default_forested: str  # Default turbine type for forested areas
    country_codes: list  # ISO country codes for this region


@dataclass
class RegionBounds:
    """Defines a rectangular region with its characteristics."""

    min_lon: float
    max_lon: float
    min_lat: float
    max_lat: float
    default_onshore: str
    default_offshore: str
    default_forested: str
    name: str


class DefaultTurbineSelector:
    """Selects appropriate default turbine types based on location."""

    def __init__(self):
        """Initialize with predefined regions."""
        # Define regions with their bounds and defaults
        self.regions = [
            # North Sea region
            RegionBounds(
                min_lon=-5.0,
                max_lon=10.0,
                min_lat=51.0,
                max_lat=60.0,
                default_onshore="V90",  # Common in UK, NL, DK
                default_offshore="V164",  # Common in North Sea
                default_forested="V112",  # Better for lower wind speeds
                name="North Sea Region",
            ),
            # Baltic region
            RegionBounds(
                min_lon=10.0,
                max_lon=30.0,
                min_lat=54.0,
                max_lat=66.0,
                default_onshore="N131",  # Common in Germany/Sweden
                default_offshore="SWT-154",  # Common in Baltic
                default_forested="N149",  # Better for forest conditions
                name="Baltic Region",
            ),
            # Central Europe
            RegionBounds(
                min_lon=5.0,
                max_lon=15.0,
                min_lat=47.0,
                max_lat=54.0,
                default_onshore="E101",  # Common in Germany
                default_offshore="Senvion-6M",  # Used in German parts of North Sea
                default_forested="E115",  # Used in forested areas
                name="Central Europe",
            ),
            # Western Europe
            RegionBounds(
                min_lon=-10.0,
                max_lon=5.0,
                min_lat=43.0,
                max_lat=51.0,
                default_onshore="V100",  # Common in France
                default_offshore="SWT-154",  # Used in French offshore projects
                default_forested="V112",  # Used in forested areas
                name="Western Europe",
            ),
            # Iberian Peninsula
            RegionBounds(
                min_lon=-10.0,
                max_lon=5.0,
                min_lat=36.0,
                max_lat=43.0,
                default_onshore="SG-114",  # Common in Spain/Portugal
                default_offshore="SWT-120",  # Used in Spanish projects
                default_forested="V90",  # Common in mountainous areas
                name="Iberian Peninsula",
            ),
            # Alpine Region
            RegionBounds(
                min_lon=5.0,
                max_lon=16.0,
                min_lat=43.0,
                max_lat=48.0,
                default_onshore="E82",  # Common in Alpine countries
                default_offshore="E101",  # Rarely offshore
                default_forested="E70",  # Used in lower elevations
                name="Alpine Region",
            ),
            # Eastern Europe
            RegionBounds(
                min_lon=15.0,
                max_lon=30.0,
                min_lat=45.0,
                max_lat=54.0,
                default_onshore="V90",  # Common in Poland/Romania
                default_offshore="V112",  # Black Sea projects
                default_forested="N131",  # Used in forested areas
                name="Eastern Europe",
            ),
            # UK/Ireland
            RegionBounds(
                min_lon=-11.0,
                max_lon=-1.0,
                min_lat=50.0,
                max_lat=59.0,
                default_onshore="V90",  # Very common in UK
                default_offshore="SWT-154",  # Used in UK offshore projects
                default_forested="V112",  # Used in Scottish highlands
                name="UK and Ireland",
            ),
            # Mediterranean
            RegionBounds(
                min_lon=5.0,
                max_lon=20.0,
                min_lat=36.0,
                max_lat=45.0,
                default_onshore="V100",  # Common in Italy/Greece
                default_offshore="V112",  # Mediterranean projects
                default_forested="E82",  # Used in forested areas
                name="Mediterranean",
            ),
        ]

        # Define sea areas as simple boxes for offshore detection
        self.sea_areas = [
            # North Sea
            ((-5.0, 10.0), (51.0, 60.0)),
            # Baltic Sea
            ((10.0, 30.0), (54.0, 66.0)),
            # Mediterranean Sea
            ((5.0, 20.0), (36.0, 45.0)),
            # Atlantic (Western Europe)
            ((-10.0, -1.0), (43.0, 51.0)),
            # Atlantic (UK/Ireland)
            ((-11.0, -1.0), (50.0, 59.0)),
            # Bay of Biscay
            ((-10.0, -1.0), (43.0, 48.0)),
            # Adriatic Sea
            ((12.0, 20.0), (40.0, 46.0)),
            # Black Sea
            ((28.0, 42.0), (41.0, 47.0)),
        ]

        # Define forested regions
        self.forested_areas = [
            # Nordic forests
            ((10.0, 30.0), (58.0, 66.0)),
            # German/Polish forests
            ((10.0, 20.0), (50.0, 54.0)),
            # Alpine forests
            ((5.0, 16.0), (45.0, 48.0)),
            # Carpathian forests
            ((18.0, 26.0), (45.0, 50.0)),
            # Scottish highlands
            ((-6.0, -2.0), (56.0, 59.0)),
            # Pyrenees
            ((-2.0, 3.0), (42.0, 43.5)),
        ]

        # Define sub-regions for more diverse defaults
        self.sub_regions = []

        # Break up major regions into smaller areas for more variety
        # UK/Ireland sub-regions
        self.sub_regions.extend(
            [
                # Scotland
                RegionBounds(
                    min_lon=-6.0,
                    max_lon=-1.5,
                    min_lat=55.0,
                    max_lat=59.0,
                    default_onshore="V112",
                    default_offshore="SWT-154",
                    default_forested="V90",
                    name="Scotland",
                ),
                # England
                RegionBounds(
                    min_lon=-3.0,
                    max_lon=2.0,
                    min_lat=50.0,
                    max_lat=55.0,
                    default_onshore="V90",
                    default_offshore="V164",
                    default_forested="E101",
                    name="England",
                ),
                # Ireland
                RegionBounds(
                    min_lon=-11.0,
                    max_lon=-6.0,
                    min_lat=51.0,
                    max_lat=56.0,
                    default_onshore="E82",
                    default_offshore="V112",
                    default_forested="V90",
                    name="Ireland",
                ),
            ]
        )

        # Germany sub-regions
        self.sub_regions.extend(
            [
                # Northern Germany
                RegionBounds(
                    min_lon=6.0,
                    max_lon=14.0,
                    min_lat=52.0,
                    max_lat=55.0,
                    default_onshore="E101",
                    default_offshore="Senvion-6M",
                    default_forested="E115",
                    name="Northern Germany",
                ),
                # Southern Germany
                RegionBounds(
                    min_lon=7.0,
                    max_lon=14.0,
                    min_lat=47.5,
                    max_lat=50.0,
                    default_onshore="E82",
                    default_offshore="N131",
                    default_forested="E70",
                    name="Southern Germany",
                ),
            ]
        )

        # France sub-regions
        self.sub_regions.extend(
            [
                # Northern France
                RegionBounds(
                    min_lon=-4.0,
                    max_lon=8.0,
                    min_lat=48.0,
                    max_lat=51.0,
                    default_onshore="V100",
                    default_offshore="SWT-120",
                    default_forested="V90",
                    name="Northern France",
                ),
                # Southern France
                RegionBounds(
                    min_lon=-4.0,
                    max_lon=8.0,
                    min_lat=43.0,
                    max_lat=47.0,
                    default_onshore="V112",
                    default_offshore="V164",
                    default_forested="N131",
                    name="Southern France",
                ),
            ]
        )

        # Add more random variety based on grid cells
        self.grid_cells = []

        # Create a grid of 2x2 degree cells across Europe with randomized defaults
        import random

        random.seed(42)  # For reproducibility

        models = [
            "V90",
            "V100",
            "V112",
            "V117",
            "V126",
            "E70",
            "E82",
            "E101",
            "E115",
            "E126",
            "N131",
            "SWT-120",
            "MM100",
            "SG-114",
        ]

        # Generate grid cells across Europe
        for lon in range(-10, 30, 2):
            for lat in range(36, 66, 2):
                # Randomly select models for this cell
                onshore = random.choice(models)
                offshore = random.choice(["V164", "SWT-154", "Senvion-6M", "V112"])
                forested = random.choice(models)

                self.grid_cells.append(
                    RegionBounds(
                        min_lon=lon,
                        max_lon=lon + 2,
                        min_lat=lat,
                        max_lat=lat + 2,
                        default_onshore=onshore,
                        default_offshore=offshore,
                        default_forested=forested,
                        name=f"Grid_{lon}_{lat}",
                    )
                )

    def _get_region(self, lat: float, lon: float) -> Optional[RegionBounds]:
        """Find the region containing the given coordinates."""
        # First check sub-regions for more specific matches
        for region in self.sub_regions:
            if (
                region.min_lon <= lon <= region.max_lon
                and region.min_lat <= lat <= region.max_lat
            ):
                return region

        # Then check main regions
        for region in self.regions:
            if (
                region.min_lon <= lon <= region.max_lon
                and region.min_lat <= lat <= region.max_lat
            ):
                return region

        # Finally check grid cells for maximum coverage
        for cell in self.grid_cells:
            if (
                cell.min_lon <= lon <= cell.max_lon
                and cell.min_lat <= lat <= cell.max_lat
            ):
                return cell

        return None

    def _is_forested(self, lat: float, lon: float) -> bool:
        """Determine if location is in a forested area."""
        for lon_bounds, lat_bounds in self.forested_areas:
            if (
                lon_bounds[0] <= lon <= lon_bounds[1]
                and lat_bounds[0] <= lat <= lat_bounds[1]
            ):
                return True
        return False

    def is_offshore(self, lat: float, lon: float) -> bool:
        """Determine if location is offshore using simple boxes."""
        for lon_bounds, lat_bounds in self.sea_areas:
            if (
                lon_bounds[0] <= lon <= lon_bounds[1]
                and lat_bounds[0] <= lat <= lat_bounds[1]
            ):
                return True
        return False

    def get_default_turbine(self, lat: float, lon: float) -> str:
        """Get default turbine type based on location with enhanced variety."""
        region = self._get_region(lat, lon)

        # Add some variety based on the exact coordinates
        # Use the decimal part of lat/lon to get variety
        lat_decimal = lat - int(lat)
        lon_decimal = lon - int(lon)
        variety_factor = (lat_decimal + lon_decimal) * 10 % 3  # 0, 1, or 2

        if region is None:
            # Default fallback if outside defined regions
            if variety_factor == 0:
                return "V90" if not self.is_offshore(lat, lon) else "V164"
            if variety_factor == 1:
                return "E101" if not self.is_offshore(lat, lon) else "SWT-154"

            return "N131" if not self.is_offshore(lat, lon) else "Senvion-6M"

        # Select based on terrain and add variety
        if self.is_offshore(lat, lon):
            if variety_factor == 0:
                return region.default_offshore
            if variety_factor == 1:
                return "V164" if region.default_offshore != "V164" else "SWT-154"

            return "Senvion-6M" if region.default_offshore != "Senvion-6M" else "V112"
        if self._is_forested(lat, lon):
            if variety_factor == 0:
                return region.default_forested
            if variety_factor == 1:
                return "E115" if region.default_forested != "E115" else "V126"
            return "N131" if region.default_forested != "N131" else "E101"

        if variety_factor == 0:
            return region.default_onshore
        if variety_factor == 1:
            return "V90" if region.default_onshore != "V90" else "E82"
        return "E101" if region.default_onshore != "E101" else "V100"

    def explain_selection(self, lat: float, lon: float) -> str:
        """Explain why a particular default turbine was selected."""
        region = self._get_region(lat, lon)
        is_offshore = self.is_offshore(lat, lon)
        is_forested = self._is_forested(lat, lon)

        explanation = []
        if region:
            explanation.append(f"Location is in {region.name}")
        else:
            explanation.append("Location is outside defined regions")

        if is_offshore:
            explanation.append("Location is offshore")
        elif is_forested:
            explanation.append("Location is in forested area")
        else:
            explanation.append("Location is onshore (non-forested)")

        selected_type = self.get_default_turbine(lat, lon)
        explanation.append(f"Selected default turbine type: {selected_type}")

        return " | ".join(explanation)
