# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # DREAMS Quickstart
#
# DREAMS stands for:
# Distribution System Energy Analysis and Mapping Suite.
#
# Dreams was designed to facilitate analyzing 
# distribution feeders and running QSTS 'stepped hosting capacity' simulations.
#
# Additionally, DREAMS allows the export of geospatial feeder data
# that can aid in the understanding of models and issues.
#
# This notebook demonstrates how to load an OpenDSS feeder into DREAMS,
# do some light feeder analysis, plotting, and export geopackages.
#

# %% [markdown]
# # Load a Feeder
# After installation, the `dreams` package is imported using standard methods.
#
# The `pathlib` Path class is used to allow for multi-platform 
# compatibility when defining paths.

# %%
import sys
print(sys.executable)

try:
    import spyder_kernels
    print("spyder-kernels:", spyder_kernels.__version__)
except ImportError:
    print("spyder-kernels NOT INSTALLED")

# %%
# %connect_info

# %%
import dreams

from pathlib import Path
import os

# %% [markdown]
# The demo model is a modified synthetic bay area model located in the 
# `models/sfo_p1udt1469` folder.
#
# An output directory is defined here so that examples of
# exporting data and plots can be demonstrated.

# %%
model_dir = Path(r'models') / r'sfo_p1udt1469'

output_dir = model_dir / 'temp_outputs'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# %%
print(Path.cwd())

# %% [markdown]
# The `Feeder` class only requires the path to the `Main.dss` file, but 
# a name is also provided here that will be used in plots and export names.

# %%
feeder = dreams.Feeder(model_dir/'Main.dss', name='sfo_p1udt1469')

# %% [markdown]
# # Feeder Statistics
# Upon initialization, the `Feeder` class solves the system and collects
# a variety of standard statistics.
#
# Some of this data is collected in the `stats` dictionary

# %%
feeder.stats

# %% [markdown]
# The `Feeder` class also has various methods that will be useful later.
#
#
# Below, the `id_violations` method is called to report any bus
# voltages outside of the standard ANSI operating range of 0.95 and 
# 1.05 VPU and any elements that have capacity over 100% nameplate rating.
#
# As the demo model does not have any such operation violations, the
# retrun is empty.

# %%
feeder.id_violations()

# %% [markdown]
# # Feeder DataFrames
# Currently, during itialization all information about each feeder element
# is collected into a dataframe of the feeder object.
#
# For instance, the `loads` DataFrame is shown below.

# %%
feeder.loads.head()

# %% [markdown]
# These attributes describing the system are Pandas DataFrame objects and 
# can be used in the same way one would normally use DataFrames.
#
#
# The ability to sort and export as csv is shown below.

# %%
feeder.loads.sort_values('kw', ascending=False)  # basic sorting

# %%
capacitor_output_path = output_dir / 'capacitors.csv'
feeder.capacitors.to_csv(capacitor_output_path)  # exporting as csv

# %% [markdown]
# The Feeder class currently has DataFrames for most all of the OpenDSS
# circuit objects aswell as other useful information like element capacity
# and bus voltage. 

# %%
feeder.bus_voltages

# %%
feeder.capacity

# %% [markdown]
# # Basic Plotting
# Various ploting options are also built into the `Feeder` class.
#
# Examples below are of voltage profile, voltage box whisker plots, and a
# generic topological plot.
#
# Most plotting functions return a standard matplotlib figure and axis class that can be useful for modifiying the plot appearance.

# %%
fig, ax = feeder.plot()

# %%
fig, ax = feeder.plot(kind='box')

# %%
feeder.plot(kind='topo')

# %% [markdown]
# # Exporting Feeder GIS
# The code below demonstrates how all feeder data could be exported as 
# geopackage files.
#
# Note: The expected input and output CRS is the standard 4326 lat/long.
#
# But this can be altered using the input parameters `input_crs` and `output_crs`.
#

# %%
dreams.gis.export_feeder_gpkg(
    feeder,
    output_path=output_dir
)

# %% [markdown]
# While the above will export all types of GIs data,
#  single types of data can also be exported one at a time, or,
# (as shown below) not exported, and the resulting GeoDataFrame can be
# further utilized Python work flows.

# %%
bus_gdf = dreams.gis.export_bus_gis(feeder, export_gpkg=False)
bus_gdf.head()

# %% [markdown]
# Again, the GeoDataFrames are created using EPSG:4326 as a default CRS, but any
# CRS can be passed into `Feeder` class during intialization, or passed into the gis_export function will be
# used instead.

# %%
bus_gdf.crs

# %% [markdown]
# Again, full functaionly of GeoDataFrames is possible.

# %%
ax = bus_gdf.plot(
    column="ave_v",
    scheme="quantiles",
    k=3,
    cmap="viridis",
    legend=True,
    legend_kwds={'loc': 'upper right'},
    )
ax.set_title('Average Bus Voltage')

# %% [markdown]
# This concludes the introduction to DREAMS showing how to:
#
# load a feeder,
# look at some feeder statistics and dataframes,
# basic plotting, and GIS export functionality.
