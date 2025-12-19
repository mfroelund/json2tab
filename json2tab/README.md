# Wind Turbine Location Processor and Visualizer

This repository provides tools to process wind turbine location data, match turbines to known specifications, and generate standardized output formats for numerical weather prediction (NWP) models like **HARMONIE-AROME**.

---

## 📦 Main Features

- ✅ Process wind turbine locations from **GeoJSON** data
- ✅ Subset turbines based on **bounding boxes** (manual coordinates) or **domain files** (TOML format)
- ✅ Match turbines against a **specification database** (JSON or CSV)
- ✅ Generate **standardized `.tab` files** for model input
- ✅ Produce **map visualizations** of turbine locations
- ✅ Handle missing data with **intelligent default fallbacks**
- ✅ Follow **HARMONIE-AROME** conventions for turbine modeling

---

## ⚙️ Structure

- **TurbineFilterer**: The main pipeline
- **DimensionLocationMapper** Derives turbine type from turbine locations
- **TurbineMatcher**: Matches turbine type to technical specifications
- **TabFileWriter**: Creates `.tab` files
- **SimpleVisualizer**: Plots turbine maps
- **DefaultTurbineSelector**: Provides fallback specs based on location

---

## ⚙️ Configuration

The tool uses a YAML configuration file (example: `config.yaml`) to control all settings.

You can choose to subset turbines either by:
- providing a **bounding box** (manual coordinates) or
- specifying a **domain** file (`.toml` format).

Example:
```yaml
input:
  turbine_locations: "wind_turbines_012025.geojson"
  turbine_database: "turbine_database+gened_ct_curves.json"
  turbine_specs: "merged_turbine_specifications.csv"

subsetting:
  method: "domain"  # or "box"
  domain:
    file: "NETHERLANDS_750m.toml"

output:
  directory: "output"
  prefix: "windturbines"
  files:
    filtered_geojson: "filtered_turbines.geojson"
    regional_plot: "turbine_locations_regional.png"
    domain_plot: "turbine_locations_domain.png"
    location_tab: "turbine_locations.tab"
    type_tab_prefix: "wind_turbine_"
```

For bounding box selection instead of domain:
```yaml
subsetting:
  method: "box"
  box:
    min_lon: 3.0
    max_lon: 7.5
    min_lat: 50.5
    max_lat: 53.5
```

---

## 🌍 Domain Definition

Domains are provided via `.toml` files. Example:

```toml
[domain]
name = "NETHERLANDS_750m"
nimax = 1489
njmax = 1489
tstep = 20
xdx = 750.0
xdy = 750.0
xlat0 = 52.5
xlatcen = 51.967
xlon0 = 0.0
xloncen = 4.9
```

---

## 🗌 Visualization Example

Example output for turbine distributions using the domain version:

![Turbine .toml Example](./turbine_map.png)

and for the bbox version:
![Turbine BBOX Example](./turbine_map_bbox.png)
---

## 📋 How to Run

1. Prepare your configuration:
   ```bash
   cp config.yaml.template config.yaml
   nano config.yaml
   ```

2. Run the turbine processor:
   ```bash
   python Json-2-tab.py
   ```

3. Outputs will appear under the specified output directory:
   - `.tab` files for model input
   - GeoJSON subset of turbines
   - Map visualizations

---

## 📚 Dependencies

- `numpy`
- `pandas`
- `matplotlib`
- `cartopy`
- `pyproj`
- `geopandas`
- `shapely`
- `PyYAML`
- `toml`
- `scipy`

Install all dependencies via:
```bash
pip install -r requirements.txt
```

---

## 📁 requirements.txt

```txt
numpy
pandas
matplotlib
cartopy
pyproj
geopandas
shapely
PyYAML
toml
scipy
```

---

## 📁 environment.yml

```yaml
name: turbine-processor
channels:
  - conda-forge
dependencies:
  - python=3.10
  - numpy
  - pandas
  - matplotlib
  - cartopy
  - pyproj
  - geopandas
  - shapely
  - pyyaml
  - toml
  - scipy
```

---

## ✨ Special Features

- Auto-detection of missing turbine data
- Smart fallbacks using region-specific defaults
- High-quality plotting with rivers, coastlines, and domain bounds
- Enhanced turbine specification matching using weights (hub height, diameter, location, etc.)

---

## 🧑‍💻 Authors

- Irene Schicker (GeoSphere Austria)
- Dieter van den Bleeken (RMI)

---



