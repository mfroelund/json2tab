"""Module with OpenStreetMap wind turbine location data fetcher."""

import contextlib
import json
import os
import re

try:
    import requests
except ImportError:
    requests = None
from typing import Optional

import pandas as pd

from ..io.readers import read_locationdata_as_dataframe
from ..io.writers import save_dataframe
from ..logs import logger
from ..Turbine import Turbine
from ..utils import power_to_kw
from .cleanup_short_distance_turbines import cleanup_short_distance_turbines


def osm_data_fetcher(
    output_filename: str, input_filename: Optional[str] = None
) -> pd.DataFrame:
    """OpenStreetMap wind turbine location data fetcher.

    Args:
        output_filename (str): Filename to write the processed OSM wind turbine data to
        input_filename (str):  (Optional) Filename of overpass_output.json to bypass
                               OverpassAPI call (i.e. use local/cached OSM data)

    Returns:
        pandas.DataFrame with windturbine location data
    """
    print(
        f"OSM (windturbine location) Data Fetcher ({input_filename} -> {output_filename})"
    )

    logger.debug(f"input filename: {input_filename}")
    logger.debug(f"output filename: {output_filename}")

    output_filename_base = os.path.splitext(output_filename)[0]
    overpass_dump_file = f"{output_filename_base}.overpass_output.json"

    if requests is not None:
        if not os.path.exists(output_filename):
            data = None

            if input_filename is not None and os.path.exists(input_filename):
                logger.debug(
                    f"Process inputfile '{input_filename}' as Overpass API results"
                )
                with open(input_filename, "r") as input_file:
                    data = json.load(input_file)

            if data is None and os.path.exists(overpass_dump_file):
                logger.debug(
                    f"Process dumpfile '{overpass_dump_file}' as Overpass API results"
                )
                with open(overpass_dump_file, "r") as input_file:
                    data = json.load(input_file)

            if not data:
                # Overpass API URL
                overpass_url = "http://overpass-api.de/api/interpreter"
                logger.debug(f"Using overpass API url: '{overpass_url}'")

                # Overpass QL query for wind turbines
                overpass_query = """
                [out:json];
                nwr["power"="generator"]["generator:source"="wind"];
                /* get also the turbines marked as way (i.e. a list of grouped nodes) */
                (._;>;);
                out body;
                """
                logger.debug(f"Using overpass query: '{overpass_query}'")

                print("Executing request to fetch OSM data...")

                response = requests.get(overpass_url, params={"data": overpass_query})
                data = response.json()

                # Dump overpass api response data to file
                with open(overpass_dump_file, "w") as dump_file:
                    json.dump(data, dump_file, indent=2)
                    logger.debug(
                        f"Dumped overpass query output to '{overpass_dump_file}'"
                    )

                print("... got response for query")

            if not data:
                logger.error("No data to process, reading aborted.")
                return None

            # Initialize a list to hold the data
            turbines = []

            logger.info(f"Received {len(data['elements'])} elements for wind turbines")

            skipped_nodes = []

            # Process each element
            for element in data["elements"]:
                # Extract the latitude, longitude, and any available name

                if element.get("tags") is None:
                    # This is an auxiliary element to properly interpret ways
                    # Don't interpret this element as singleton item
                    if element["type"] == "node":
                        skipped_nodes.append(element)
                    continue

                # Basic WFP information
                osm_name = f"{element['type']}-{element['id']}"
                turbine_name = element["tags"].get("name")
                lat = element.get("lat")
                lon = element.get("lon")

                if lat is None or lon is None:
                    # Fix lat/lon location

                    if element["type"] == "way":
                        # Fix lat/lon of way
                        # by taking the average of the lat/lons of its nodes
                        nodes = [
                            node
                            for node in skipped_nodes
                            if node["id"] in set(element["nodes"])
                        ]

                        if len(nodes) != len(set(element["nodes"])):
                            # Failed to get all nodes from the skipped_nodes,
                            # lets select them from all nodes
                            nodes = [
                                node
                                for node in data["elements"]
                                if node["type"] == "node"
                                and node["id"] in set(element["nodes"])
                            ]

                        lat = sum([node["lat"] for node in nodes]) / len(nodes)
                        lon = sum([node["lon"] for node in nodes]) / len(nodes)

                        logger.debug(
                            f"Defined lat/lon coordinates for {osm_name} "
                            f"based on {len(nodes)} nodes; lat={lat}, lon={lon}"
                        )
                    elif element["type"] == "relation":
                        logger.debug(
                            f"Ignore processing of relations; so skip {osm_name}"
                        )
                        continue

                # Parse manufacturer and turbine type model
                manufacturer = element["tags"].get("manufacturer")
                model_type = element["tags"].get("model")

                if model_type in [None, ""]:
                    # Note manufacturer:type is deprecated
                    model_type = element["tags"].get("manufacturer:type")

                if model_type in [None, ""]:
                    model_type = element["tags"].get("generator:model")

                # Parse wind turbine specs
                hub_height = parse_length(element["tags"].get("height:hub"))
                if hub_height in [None, "", 0]:
                    # est_hub:height is estimated hub:height
                    hub_height = parse_length(element["tags"].get("est_height:hub"))

                if hub_height in [None, "", 0]:
                    # Use height as fallback to get hub height information of turbine
                    hub_height = parse_length(element["tags"].get("height"))

                rotor_diameter = parse_length(element["tags"].get("rotor:diameter"))
                rated_power = parse_power_to_kw(
                    element["tags"].get("generator:output:electricity")
                )

                if isinstance(rotor_diameter, str):
                    logger.warning(
                        f"Failed to parse rotor_diameter='{rotor_diameter}' as "
                        f"valid diameter for {osm_name}"
                    )
                    rotor_diameter = None

                # Parse some additional optional information
                operator = element["tags"].get("operator")
                start_date = element["tags"].get("start_date")
                site = element["tags"].get("site")
                is_offshore = element["tags"].get("offshore")

                if (
                    element["tags"].get("power") == "generator"
                    and element["tags"].get("generator:source") == "wind"
                ):
                    turbine = Turbine(
                        turbine_id=osm_name,
                        name=turbine_name,
                        latitude=lat,
                        longitude=lon,
                        manufacturer=manufacturer,
                        type=model_type,
                        hub_height=hub_height,
                        radius=float(rotor_diameter) / 2
                        if rotor_diameter is not None
                        else None,
                        diameter=rotor_diameter,
                        power_rating=rated_power,
                        operator=operator,
                        start_date=start_date,
                        wind_farm=site,
                        is_offshore=is_offshore,
                        source="OSM",
                    )

                    # Append to the list
                    turbines.append(turbine)

            # Create a DataFrame
            data = pd.DataFrame(turbines)
            logger.info(f"Generated dataframe with {len(data.index)} turbines")

            data, min_dist, duplicate_data = cleanup_short_distance_turbines(data)
            logger.info(
                f"Filtered dataframe to {len(data.index)} turbines with "
                f"at least ~{int(111 * 1000 * min_dist)} meter "
                f"(i.e. {min_dist} degree) distance."
            )

            save_dataframe(data, output_filename)

        else:
            data = read_locationdata_as_dataframe(output_filename)

        return data

    print(
        "Python package 'requests' not found, "
        "please load this optional package to run OsmDataFetcher."
    )
    print("Please run")
    print("    poetry install --with osmrequest")
    print("to install the necessary packages for OsmDataFetcher")

    return None


def parse_length(length_str: str):
    """Try to convert length string to distance in meter."""
    if length_str is None:
        return None

    # Try kW match
    match = re.search(
        r"(?P<length>\d+(\.\d+)?)\s*(m)?", length_str.replace(",", "."), re.IGNORECASE
    )
    if match:
        with contextlib.suppress(Exception):
            length = float(match.group("length"))
            return length

    if length_str not in ["yes", "yes [m]", "m"]:
        return length_str

    return None


def parse_power_to_kw(power_str: str, diameter: Optional[float] = None):
    """Try to convert power string to power in kW."""
    if power_str is None:
        return None

    # Try to match power and unit
    match = re.search(
        r"(?P<power>\d+(\.\d+)?)\s*(?P<unit>(kW)|(MW))?",
        power_str.replace(",", "."),
        re.IGNORECASE,
    )
    if match:
        try:
            power = float(match.group("power"))
        except (ValueError, KeyError, TypeError):
            power = None

        try:
            unit = float(match.group("unit"))
        except (ValueError, KeyError, TypeError):
            unit = None

        return power_to_kw(power, unit, diameter)

    if power_str not in ["yes", "no", "*", "yes/kW", "no/kW"]:
        return power_str

    return None
