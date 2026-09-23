# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
#   kernelspec:
#     display_name: dreams_2026
#     language: python
#     name: python3
# ---

# %% [markdown]
# # DREAMS Nodal Hosting Capacity at Time
# This demo notebook will demonstrate how to to perform nodal hosting 
# capacity calculations using DREAMS at a specific time in the model.
#
# As mentioned in the previous notebook, the nodal hosting capaicty value
# calculated using the `NodalSnapshot` function is based on a single 
# snapshot in timme.
# However, there may be situations in which other known times are of interest.
# Specifically minimum and maximum demand times.
#
# To that end, this notebook demonstrates how to:
# * Load a model
# * Select a bus for testing
# * Identify locations from a time series to test
# * Run demand and generation hosting capacity simulations at various times
# * Perform simple analysis of results

# %%
import dreams

import matplotlib.pyplot as plt
import pandas as pd

from pathlib import Path

# %% [markdown]
# # Loading of Demo Feeder with Demand Profile
# The demo feeder is loaded and a voltage profile plot is made to ensure
# the model loads correctly, and that there is some headroom for voltage
# fulctuations.
#
# Unlike previous demos, the specific model has a demand profile assigned to
# all loads.
# Typically, each load would have a unique timeseries of demand, but to 
# save time and space, a single per-unit profile applied to all loads.
#

# %%
model_dir = Path(r'models') / r'sfo_p1udt1469'
feeder = dreams.Feeder(model_dir/'Main_with_profile.dss', name='sfo_p1udt1469')

# %% [markdown]
# A plotly image is created to allow the selection of a bus to test
# by simply overing over the graph.

# %%

fig = feeder.plot(kind='plotly')

# %% [markdown]
# # Identification of Bus to Test
#
# A bus was selected from the model by hovering over the above plot.
#
# Note that Any valid bus can replace `bus_name` below, though documented 
# results later in the notebook will likely not correspond to buses that
# are not `p1udt16`.

# %%
bus_name = 'p1udt16'  # selected bus name
feeder.buses.loc[bus_name]

# %% [markdown]
# # Selecting Time Indicies to Test
# As mentioned, before, points of interest often include minimum and maximum
# demand times.
#
# Pandas is used to load the demand data attached to all loads and then
# identify the minimum and maximum index values - which are then 
# transformed into seconds, which is used in the `NodalSnapshot` function
# to select the time of interest in the model.

# %%
demand_fp = model_dir / 'pu_substation_demand.csv'
demand = pd.read_csv(demand_fp, header=None)
ax = demand.plot(legend=False)  # to show PU demand profile
ax.grid()
ax.set_axisbelow(True)
ax.set_title('PU Demand Profile')
ax.set_xlabel('Sample Number')

# %%
# adding 1 to account for opendss first time step being 1
min_idx = demand[0].idxmin() + 1
max_idx = demand[0].idxmax() + 1

time_step_sec = 15 * 60  # 15 minute data

min_t = min_idx * time_step_sec
max_t = max_idx * time_step_sec

# %% [markdown]
# # Load (Demand) Hosting Capacity
# First, a default call of the standard `NodalSnapshot` function is performed to 
# get a baseline result.
#
# As shown below, since `bus_name` is a single string, it must be transformed
# into a list to meet function input requirements.
#

# %%
voltage_hc = dreams.hc.NodalSnapshot(feeder, bus_names=[bus_name])

# %% [markdown]
# The next two solutions utilize the `at_sec` and `mode` parameters to 
# define the time to be simulated, and to ensure that the 
# specific profile is used.
#
# In this case, all loads were calibrated such that their `duty` followed the
#  demand profile of interest
#
# Further, since the input profile is PU, the expectation is that the max
# demand result should be very similar to the standard 'no time' solution.
#
# It is also expected that at the minimum demand time, a different 
# hosing capacity result will be calculated.
#
# Simulations are run and results combined into a DataFrame for easier presntation.

# %%
vchc_max_demand = dreams.hc.NodalSnapshot(
    feeder,
    bus_names=[bus_name],
    mode='duty',
    at_sec=max_t,
    )

# %%
vchc_min_demand = dreams.hc.NodalSnapshot(
    feeder,
    bus_names=[bus_name],
    mode='duty',
    at_sec=min_t,
    save_violations=True,  # NOTE: by default, this is False
    )

# %% [markdown]
# As shown below, the demand based voltage constrained hosting capacity is 
# very similar between the initial solve and max demand case, but different
# in the minimum demand case.

# %%
demand_hc = {
    'initial_solve':voltage_hc.result_df['voltage_hc_kw'],
    'max_demand':vchc_max_demand.result_df['voltage_hc_kw'],
    'min_demand':vchc_min_demand.result_df['voltage_hc_kw']
}

pd.DataFrame.from_dict(demand_hc)

# %% [markdown]
# The `save_violations` parameter will save all violations found on the
# feeder from the last 'violation having' power flow solution so one can 
# identify the element and condition that caused the hosting capcity limit
# to be found.
#
# As this process increases simulation time, the default setting is `False`.

# %%
vchc_min_demand.result_df  # standard dataframe results

# %%
vchc_min_demand.violations[bus_name]['under_voltage']  # identification of violation at bus_name hosting capacity

# %% [markdown]
# Since all violations are stored in the violations dictionary, other issues 
# can be identified.
#
# In this case, since there were also line overloading, one may ask 
# "how many lines were overloaded?"

# %%
vchc_min_demand.violations[bus_name]['n_over_capacity']

# %% [markdown]
# Since there are many over capacity violations, it is expected that the
# thermal constrained hosting capacity will be less than the voltage 
# constrianed hosting capacity.

# %%
tchc_min_demand = dreams.hc.NodalSnapshot(
    feeder,
    bus_names=[bus_name],
    constraint='thermal',
    mode='duty',
    at_sec=min_t,
    save_violations=True,
    )

# %% [markdown]
# As expected, the thermal hosting capacity is less than the thermal hosting 
# capacity at the originally selected bus.
#
# Additional information in the violations dictionary can lead to the exact 
# element in violation.

# %%
tchc_min_demand.result_df

# %%
tchc_min_demand.violations[bus_name]['n_over_capacity']

# %%
tchc_min_demand.violations[bus_name]['over_capacity']

# %% [markdown]
# # Generation (PV) Hosting Capacity
# Similarly, the time of simulation also impacts the PV hosting capacity.
#
# Below are results from minimum and maximum demand times assuming a
# a generation based hosting capacity is executed.

# %%
pv_vchc_max_demand = dreams.hc.NodalSnapshot(
    feeder,
    bus_names=[bus_name],
    hc_kind='pv',
    mode='duty',
    at_sec=max_t,
    )


# %%
pv_vchc_min_demand = dreams.hc.NodalSnapshot(
    feeder,
    bus_names=[bus_name],
    hc_kind='pv',
    mode='duty',
    at_sec=min_t,
    )


# %% [markdown]
# In this case the maximum demand time allows for a larger system to be
# added compared to the minimum demand result.
#
# This makes intuitive sense because the generation source has more load
# to feed before voltage issues occur.

# %%
pv_hc = {
    'max_demand':pv_vchc_max_demand.result_df['voltage_hc_kw'],
    'min_demand':pv_vchc_min_demand.result_df['voltage_hc_kw']
}
pd.DataFrame.from_dict(pv_hc)


# %% [markdown]
# # Conclusion
# This noteboke showed how the DREAMS nodal hosting capacity function can
# be used at different simulated times of a model to produce different results.
#
# This involved defining the `mode`, `at_sec` and optionally the 
# `save_violations` parameters to the `NodalSnapshot` hosting capacity function.
#
# In typical, well behaved models, during maximum demand, there is less 
# available hosting capacity for additional load, and more hosting capacity
# for generation.
# However, this may not always be the case due to various model characteristics.
#
# The difference between minimum and maximum demand can have large impacts on 
# hosting capacity results.
#
# In the example above, demand voltage hosting capacity varied by ~10 MW between the two 
# demand situation while and PV hosting capacity reported nearly a 3 MW 
# difference.
#
# The ability to identify elements in violation at a hosting capacity step
# can inform planners and researchers of potential system bottle necks or 
# other operational issues to address.
