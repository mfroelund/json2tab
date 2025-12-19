"""Probabilistic Selector for turbine type based on turbine_type, lat, lon, diameter."""

import hashlib

from .logs import logger


class ProbabilisticMapper:
    """ProbabilisticMapper for turbine type based on turbine_type, lat, lon, diameter."""

    def __init__(self):
        """Initialize probabilistic turbine mapper."""
        self.common_models = self._get_common_models()

    def _get_common_models(self):
        # Common turbine models to distribute among
        common_models = [
            # Vestas models (very common throughout Europe)
            "V52",
            "V80",
            "V90",
            "V100",
            "V112",
            "V117",
            "V126",
            "V136",
            "V150",
            # Enercon models (very common in Germany)
            "E40",
            "E48",
            "E70",
            "E82",
            "E92",
            "E101",
            "E115",
            "E126",
            "E138",
            # Siemens/Siemens-Gamesa models
            "SWT-107",
            "SWT-120",
            "SWT-130",
            "SWT-154",
            "SG-114",
            "SG-132",
            "SG-145",
            # Nordex models
            "N90",
            "N100",
            "N117",
            "N131",
            "N149",
            "N155",
            # REpower/Senvion models
            "MM82",
            "MM92",
            "MM100",
            "Senvion-3M",
            "Senvion-5M",
            "Senvion-6M",
            # GE models
            "GE-1.5",
            "GE-2.5",
            "GE-3.8",
            "GE-4.8",
            # Older models for older IDs
            "Tacke",
            "NEG-Micon",
            "Bonus",
            "AN-Bonus",
            "Nordtank",
        ]

        return common_models

    def map(self, turbine_type, lat, lon, diameter=None):
        """Maps turbine types to model designations using a probabilistic approach.

        Probabilistic approach is based on geographic location and
        numeric patterns in the type ID.

        Args:
            turbine_type: The original turbine type ID
            lat: Latitude of the turbine
            lon: Longitude of the turbine
            diameter: Diameter of turbine

        Returns:
            A model designation string
        """
        # Use a probabilistic approach based on:
        # 1. The numeric value itself (for consistency)
        # 2. The lat/lon coordinates (for geographic distribution)
        # 3. A diverse set of common turbine models

        # Create pseudo-random hash (deterministic) from turbine_type and rough location
        # (We round the location to avoid too much sensitivity to exact coordinates)
        rounded_lat = round(lat, 1)  # Round to 0.1 degree (about 11 km)
        rounded_lon = round(lon, 1)  # Round to 0.1 degree (about 7-11 km)

        # Create a hash string from the combined inputs
        hash_input = f"{turbine_type}_{rounded_lat}_{rounded_lon}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        # Use the hash to select a model
        model_index = hash_value % len(self.common_models)
        base_model = self.common_models[model_index]

        # Add some variation based on the exact numeric ID
        # If type is 4 or 5 digits, parse first 2 or 3 digits (eg indicates diameter)
        if turbine_type and len(turbine_type) in [4, 5]:
            try:
                first_part = int(turbine_type[0:-2])
                # If it looks like a diameter value (~40-150m), use it to guide the model
                if 40 <= first_part <= 150:
                    diameter = first_part
            except (ValueError, IndexError):
                pass

        if diameter is not None:
            for tol in [0, 1, 3, 5, 15]:
                # Find models with similar diameter
                diameter_models = []
                for model in self.common_models:
                    # Extract diameter from model if possible
                    model_diameter = 0
                    if model[1:].isdigit() and model.startswith(("V", "E", "N")):
                        model_diameter = int(model[1:])
                    elif model.split("-")[-1].isdigit() and (
                        "SWT-" in model or "SG-" in model
                    ):
                        model_diameter = int(model.split("-")[-1])

                    # If we found a diameter and it's close to the ID's diameter
                    if model_diameter > 0 and abs(model_diameter - diameter) <= tol:
                        diameter_models.append(model)

                # If we found models with similar diameter, select one
                if diameter_models:
                    # Use the same hash but mod by the length of diameter_models
                    diameter_index = hash_value % len(diameter_models)
                    model_designbation = diameter_models[diameter_index]
                    logger.debug(
                        f"Used diameter={diameter} to get hash-based diameter model with "
                        f"model_designbation={model_designbation}"
                    )
                    return model_designbation

        # Handle location-based preferences
        # Different manufacturers are more common in different regions
        is_northern_europe = lat > 52 and 0 < lon < 20  # Nordics, Baltics
        is_central_europe = 47 < lat < 52 and 5 < lon < 20  # Germany, Poland, etc.
        is_western_europe = 47 < lat < 52 and -5 < lon < 5  # France, Benelux
        is_uk_ireland = 50 < lat < 60 and -10 < lon < 2  # UK and Ireland
        is_southern_europe = 36 < lat < 47 and -10 < lon < 20  # Spain, Italy, etc.
        is_offshore = False  # Simple check for known offshore areas

        # Offshore detection based on common offshore areas
        offshore_areas = [
            # North Sea
            ((-5, 12), (51, 60)),
            # Baltic Sea
            ((10, 30), (54, 66)),
            # Mediterranean offshore areas
            ((0, 20), (36, 45)),
        ]

        for lon_range, lat_range in offshore_areas:
            if (
                lon_range[0] <= lon <= lon_range[1]
                and lat_range[0] <= lat <= lat_range[1]
            ) and (
                # Additional check - this just identifies the general region
                # We'd need more detailed coastline data for precision
                (lon > 3 and lat > 53)  # North Sea
                or (lon > 12 and lat > 54)  # Baltic
                or (lon > 0 and lat < 43)  # Mediterranean
            ):
                is_offshore = True
                break

        # Create regional model lists with appropriate weighting
        regional_models = []

        # Offshore models (larger, more powerful)
        if is_offshore:
            offshore_models = [
                "V164",
                "V174",
                "SWT-154",
                "SG-D8",
                "Senvion-6M",
                "Siemens-D7",
            ]
            # Weight heavily toward offshore models
            regional_models.extend(offshore_models * 3)
            # Also add some large onshore models that might be used nearshore
            regional_models.extend(["V150", "E126", "SWT-130", "N149"])
            logger.debug(f"Location is_offshore, add regional_models = {regional_models}")
        # Northern Europe (lots of Vestas, many larger models)
        elif is_northern_europe:
            regional_models.extend(["V90", "V100", "V112", "V117", "V126", "V136"] * 2)
            regional_models.extend(["N131", "N149", "E101", "E115", "E126"])
            logger.debug(
                f"Location is_northern_europe, add regional_models = {regional_models}"
            )
        # Central Europe (Enercon territory)
        elif is_central_europe:
            regional_models.extend(["E82", "E101", "E115", "E126", "E138"] * 2)
            regional_models.extend(["V90", "V112", "N131", "SG-132"])
            logger.debug(
                f"Location is_central_europe, add regional_models = {regional_models}"
            )
        # Western Europe (mixed, more Vestas and GE)
        elif is_western_europe:
            regional_models.extend(["V90", "V100", "V112"] * 2)
            regional_models.extend(["GE-1.5", "GE-2.5", "E82", "E101", "MM100"])
            logger.debug(
                f"Location is_western_europe, add regional_models = {regional_models}"
            )
        # UK and Ireland (strong Vestas presence)
        elif is_uk_ireland:
            regional_models.extend(["V80", "V90", "V100", "V112"] * 2)
            regional_models.extend(["SWT-107", "SWT-120", "E82", "N90"])
            logger.debug(
                f"Location is_uk_ireland, add regional_models = {regional_models}"
            )
        # Southern Europe (more older models in mountainous areas)
        elif is_southern_europe:
            regional_models.extend(["V90", "G58", "G80", "GE-1.5", "MM82"])
            regional_models.extend(["SG-114", "V100", "E82"])
            logger.debug(
                f"Location is_southern_europe, add regional_models = {regional_models}"
            )
        # Fallback - if region not identified
        else:
            # Just use the base model from earlier
            logger.debug(f"No location match, use base_model = {base_model}")
            return base_model

        # Use hash to select from the regional models
        if regional_models:
            regional_index = hash_value % len(regional_models)
            model_designbation = regional_models[regional_index]
            logger.debug(
                f"Pick a hash-based model from the regional models: "
                f"model_designbation = {model_designbation}"
            )
            return model_designbation

        # Final fallback
        logger.debug(f"Final fallback, use base_model = {base_model}")
        return base_model
