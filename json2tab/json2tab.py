"""JSON-2-TAB main function-call entry point."""

from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .logs import logger
from .WindTurbineLocationProcessorVisualizer import main


def json2tab(
    config_path: str = "config.yaml",
    turbine_databases: Optional[List[str]] = None,
    turbine_locations: Optional[str] = None,
    domain_file: Optional[str] = None,
    domain_dict: Optional[Dict[str, Any]] = None,
    situation_date: Optional[date] = None,
    output_dir: Optional[str] = None,
    location_file: Optional[str] = None,
    type_file_prefix: Optional[str] = None,
):
    """JSON-2-TAB; function call entry point.

    Wrapper around WindTurbineLocationProcessor(Visualizer) to inject custom paths.
    """
    # Load configuration
    logger.debug(f"config_path = {config_path}")
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path) as file:
        config = yaml.safe_load(file)

    logger.debug(f"config = {config}")

    # Override custom arguments
    if turbine_databases is not None:
        if isinstance(turbine_databases, str):
            turbine_databases = [turbine_databases]

        config["input"]["turbine_database"] = turbine_databases

    if turbine_locations is not None:
        config["input"]["turbine_locations"] = turbine_locations

    if domain_file is not None:
        config["subsetting"]["method"] = "domain"
        config["subsetting"]["domain"]["file"] = domain_file

    if domain_dict is not None:
        config["subsetting"]["method"] = "domain"
        config["subsetting"]["domain"] = domain_dict

    if situation_date is not None:
        config["subsetting"]["situation_date"] = situation_date

    if output_dir is not None:
        config["output"]["directory"] = output_dir

    if location_file is not None:
        config["output"]["files"]["location_tab"] = location_file

    if type_file_prefix is not None:
        config["output"]["files"]["type_tab_prefix"] = type_file_prefix

    # Dump the (modified) config to output_dir
    Path(config["output"]["directory"]).mkdir(parents=True, exist_ok=True)
    with open(f"{config['output']['directory']}/processed_config.yaml", "w") as outfile:
        yaml.dump(config, outfile, default_flow_style=False)

    logger.debug(
        f"Preprocessing done. "
        f"Calling WindTurbineLocationProcessorVisualizer with config={config}"
    )
    main(config)
