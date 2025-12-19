"""Module to select or remove wind turbines from a specific country (or countries)."""

import shutil
from typing import List

import pandas as pd

from ..io.readers import read_locationdata_as_dataframe
from ..io.writers import save_dataframe
from ..location_converters.country_offshore_flag_fixer import country_offshore_flag_fixer
from ..logs import logger


def fix_country_offshore(input_filenames: List[str], output_filename: str):
    """Fixer for country and is_offshore flag.

    Args:
        input_filenames (list[str]): Input files used in country_offshore_flag_fixer
        output_filename (str):       Output csv/geojson-file with fixed turbine data
    """
    eez_files = [filename for filename in input_filenames if "eez" in filename.lower()]

    country_border_files = [
        filename for filename in input_filenames if "country_border" in filename.lower()
    ]

    eez_file = eez_files[0] if len(eez_files) > 0 else None
    land_file = country_border_files[0] if len(country_border_files) > 0 else None

    input_files = list(set(input_filenames) - {eez_file, land_file})

    country_offshore_flag_fixer(
        input_files,
        eez_file=eez_file,
        land_file=land_file,
        output_filename=output_filename,
    )


def select_from_countries(
    input_filename: str, output_filename: str, countries: str | List[str]
) -> pd.DataFrame:
    """Converter to select wind turbines from windturbine location file in a country.

    Args:
        input_filename (str):        Input csv/geojson-file with turbine location data
        output_filename (str):       Output csv/geojson-file with selected turbine data
        countries (str | list[str]): Country or countries from which the windturbines
                                     need to be selected

    Returns:
        pandas.DataFrame with wind turbines that are locted in the given country
    """
    if not isinstance(countries, list):
        countries = [countries]

    data = read_locationdata_as_dataframe(input_filename)

    selector = data["country"].isin(countries)

    data_filtered = data[selector]
    logger.info(
        f"Selected {len(data_filtered.index)} turbines "
        f"in {', '.join(map(str, countries))}"
    )

    if output_filename is None:
        backup_input_filename = f"{input_filename}.orig"

        shutil.copyfile(input_filename, backup_input_filename)
        logger.info(
            f"Copied original input-file {input_filename} to {backup_input_filename}, "
            f"set output-file to {input_filename}"
        )
        output_filename = input_filename

    save_dataframe(data_filtered, output_filename)

    return data_filtered


def remove_from_countries(
    input_filename: str, output_filename: str, countries: str | List[str]
) -> pd.DataFrame:
    """Converter to remove wind turbines from windturbine location file from a country.

    Args:
        input_filename (str):        Input csv/geojson-file with turbine location data
        output_filename (str):       Output csv/geojson-file with selected turbine data
        countries (str | list[str]): Country or countries from which the windturbines
                                     need to be removed

    Returns:
        pandas.DataFrame with wind turbines that are locted in the given country
    """
    if not isinstance(countries, list):
        countries = [countries]

    data = read_locationdata_as_dataframe(input_filename)

    selector = data["country"].isin(countries)

    data_filtered = data[~selector]
    logger.info(
        f"Selected {len(data_filtered.index)} turbines "
        f"not in {', '.join(map(str, countries))}"
    )

    if output_filename is None:
        backup_input_filename = f"{input_filename}.orig"

        shutil.copyfile(input_filename, backup_input_filename)
        logger.info(
            f"Copied original input-file {input_filename} to {backup_input_filename}, "
            f"set output-file to {input_filename}"
        )
        output_filename = input_filename

    save_dataframe(data_filtered, output_filename)
    return data_filtered
