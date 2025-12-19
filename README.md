# JSON-2-TAB

The JSON-2-TAB converter is a command line tool and library to crop global JSON windturbine database to domain specific TAB-file.

Optionally this tool can generate plots to visualize results, therefore only some additional optional python packages need to be installed. These are grouped in the `plotting` group in the poetry project configuration

## Installation
To install the core of the JSON-2-TAB converter just call
```shell
poetry install
```

To install the JSON-2-TAB converter including the plotting functionality one can use the following install option
```shell
poetry install --with plotting
```


## Usage
After installation of `json2tab` one can use the commandline interface using options as listed by

```shell
json2tab --help
```

See for more details of usage and configuration: [Wind Turbine Location Processor and Visualizer](json2tab/README.md)