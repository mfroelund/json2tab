"""Module containing the windturbine location file converter from csv to csv."""

from typing import Optional

import pandas as pd

from ..io.readers import read_locationdata_from_csv_as_dataframe
from ..io.writers import generate_output_filename, save_dataframe
from ..location_converters.LocationMerger import datarow_to_turbine
from ..logs import logger
from ..Turbine import Turbine


def csv_to_csv(
    input_filename: str,
    output_filename: Optional[str] = None,
) -> pd.DataFrame:
    """Converter to convert windturbine location file from csv-format to csv-format.

    Args:
        input_filename:  csv-filename to windturbine location data from
        output_filename: (Optional) csv-filename to write windturbine location data

    Returns:
        pandas.DataFrame with the written csv-file
    """
    if output_filename is None:
        output_filename = generate_output_filename(input_filename, "csv")

    try:
        data = read_locationdata_from_csv_as_dataframe(input_filename)

        # Convert read data rows to interpret the rows as standarized Turbines
        data = convert_dataframe(data)

        save_dataframe(data, output_filename)
        return data
    except Exception as e:
        logger.exception(
            f"Failed to convert {input_filename} -> {output_filename}: {e!s}"
        )


def convert_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Performs the actual convertion to turbine csv dataframe.

    Args:
        data (pandas.DataFrame): The dataframe containing turbine information

    Returns:
        pandas.DataFrame with standarized turbine information
    """
    turbine_keys = set(Turbine().to_dict().keys())

    if data is not None and len(set(data.columns) - turbine_keys) > 0:
        # Convert data rows to interpret the rows as standarized Turbine
        logger.debug(
            f"Converting info for {len(data.index)} turbines to "
            "standarized turbine data."
        )

        turbines = []
        for _, row in data.iterrows():
            turbines.append(datarow_to_turbine(row))

        data = pd.DataFrame(turbines)
    return data
