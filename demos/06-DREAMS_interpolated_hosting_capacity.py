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
# # DREAMS Interpolated QSTS Hosting Capacity
# This notebook is meant to demonstrate the interpolated hosting capacity
# cababilities of DREAMS.
#
# Unlike the Nodal Hosting Capacity function, which looks at a single point
# in time and iterates to a hosting capacity value, this interpolated approach
# instead uses opendss monitors to collect time series data of interest from
# the model, and then interpolate (or extapolate) at each time point an estimate
# of the asset size that would cause a hosting capacity threshold to be met.
# The smallest result for all time is then selected as a conservative 
# hosting capacity value.
#
# To demonstrate this, a small number of buses are selected for analysis over the 
# course of three days for both generation and demand hosting capacity.
#
# Then, interpolated results are compared to results created using the 
# nodal hosting capacity function at the same point in simulated time.
#
# It should be noted that this method is still experimental and being refined.
# Currently, the method is designed to study 3-phase medium voltage buses.

# %%
import dreams

from pathlib import Path
import os
import pandas as pd

# %% [markdown]
# # Define Paths
# Similar to other demos, the feeder used here is the synthetic bay area feeder with a 
# single time series demand profile for all loads.
#
# Unlike other DREAMS hosting capacity methods, this exports the collected data
# from each bus by default (though this can be turned off).

# %%
model_dir = Path(r'models') / r'sfo_p1udt1469'

output_dir = model_dir / 'temp_outputs'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# %% [markdown]
# # Select Buses to test
# This method is designed for 3-phase medium voltage locations.
# While the approach is valid for other locations, extra considerations would
# have to be accounted for that is beyond the scope of this demo and current 
# code base.

# %%
feeder = dreams.Feeder(model_dir/'Main_with_profile.dss', name='sfo_p1udt1469')

# %%
buses_to_test = [
    'p1udt888',
    'p1udt222',
    'p1udt16',
    'p1udt333',
    'p1udt440',
    ]

# %%
feeder.buses.loc[buses_to_test]

# %% [markdown]
# # Run interpolated generation hosting capacity
# The `QSTS_HC` method of the `dreams.hc.interp` code accepts all 
# simulation parameters and returns an object that contains results,
# execution timings, and other possibly useful data points.
#
# As mentioned before, recorded monitor streams for each bus tested are 
# output as netCDF files via the xarray package in the `output_dir` directory.
# This is to allow a separation between simulation and calculation of HC
# as well as facilitate further method developement.

# %%

interp_gen_hc = dreams.hc.interp.QSTS_HC(
    feeder,
    buses_to_test,
    output_dir=output_dir,
    kind='gen',
    step_size_seconds=60*15,  # 15 minute profile
    total_time_steps=24*4*3,  # run for 3 days
    debug=False  # This will produce a 'slightly' more robust output if True
)

# %% [markdown]
# Example of substation demand from openDSS monitor showing 3 days of demand.

# %%
src_df = interp_gen_hc.first_step_monitors['vsource']['source'].df
ax = (src_df['P_total_kW']*-1).plot()
ax.grid()
ax.set_title('Feeder Demand')

# %% [markdown]
# Results and timings are compiled into a data frame with various columns of note

# %%
interp_gen_hc.result_df.columns

# %% [markdown]
# # Run snapshot hosting capacity to validate results

# %% [markdown]
# For each interpolated result, the index of the result (or simulated time step),
# is used to adjust the initial model state and run the nodal snapshot hosting
# capacity method to validate interpolation results.
#
# This is done a bus at a time as the 'critical time step' may be different
# for each bus location.

# %%
feeder = dreams.Feeder(model_dir/'Main_with_profile.dss', name='sfo_p1udt1469')

snap_shot_res = []

time_step = 60*15  # 15 minutes per step

for bus_name, row in interp_gen_hc.result_df.iterrows():
    # create times to test from interpolated results
    print(bus_name)
    vchc_t = row['vchc_ndx'] * time_step
    tchc_t = row['tchc_ndx'] * time_step

    bus_res = dreams.hc.NodalSnapshot(
        feeder,
        bus_names=[bus_name],
        constraint='voltage',
        hc_kind='gen',
        mode='duty',
        at_sec=vchc_t,
        save_violations=True
    )

    # generation will typically lead to over voltage violations
    vchc_element = bus_res.violations[bus_name]['over_voltage']['Bus_Name'].values[0]
    bus_res.result_df['voltage_element'] = vchc_element

    thermal_bus_res = dreams.hc.NodalSnapshot(
        feeder,
        bus_names=[bus_name],
        constraint='thermal',
        hc_kind='gen',
        mode='duty',
        at_sec=tchc_t,
        save_violations=True,
    )

    # generation or demand will only trigger over capacity thermal issues
    thermal_element = thermal_bus_res.violations[bus_name]['over_capacity']['Name'].values[0]
    bus_res.result_df['thermal_hc_kw'] = thermal_bus_res.result_df['thermal_hc_kw']
    bus_res.result_df['thermal_element'] = thermal_element

    snap_shot_res.append(bus_res.result_df)

nodal_gen_hc = pd.concat(snap_shot_res)

# %% [markdown]
# # Generation Hosting Capacity result comparison
#
# The interpolated results also calculate substation constrainted hosting 
# capacity (SCHC), which in this case, represents a backfeeding situation, 
# or when real power delivered from the substation is 0.

# %%

nodal_gen_hc[['voltage_hc_kw', 'thermal_hc_kw', 'voltage_element', 'thermal_element',]]

# %%
interp_gen_hc.result_df[['vchc','tchc','vchc_element', 'tchc_element', 'schc']]


# %% [markdown]
# Results show that the interpolation method is reasonably close to the 
# nodal results.
#
# It is worth mentioning that the limiting element for either
# constraint is not always the same between the two approaches.

# %% [markdown]
# #Run Interpolated Demand Hosting Capacity
# Deamand, or load hosting capacity is executed in a similar fashion, with
# the `kind` parameter now set to `load`.

# %%
feeder = dreams.Feeder(model_dir/'Main_with_profile.dss', name='sfo_p1udt1469')
# best to run with a 'clean' feeder object
interp_load_hc = dreams.hc.interp.QSTS_HC(
    feeder,
    buses_to_test,
    output_dir=output_dir,
    kind='load',
    step_size_seconds=60*15,  # 15 minute profile
    total_time_steps=24*4*3,  # run for 3 days
)

# %% [markdown]
# Again, the nodal snapshot method is used to validate the demand hosting
# capacity results.

# %%
feeder = dreams.Feeder(model_dir/'Main_with_profile.dss', name='sfo_p1udt1469')

snap_shot_res = []

time_step = 60*15  # 15 minutes per step

for bus_name, row in interp_load_hc.result_df.iterrows():
    vchc_t = row['vchc_ndx'] * time_step
    tchc_t = row['tchc_ndx']* time_step

    bus_res = dreams.hc.NodalSnapshot(
        feeder,
        bus_names=[bus_name],
        hc_kind='load',
        constraint='voltage',
        mode='duty',
        at_sec=vchc_t,
        save_violations=True
    )

    vchc_element = bus_res.violations[bus_name]['under_voltage']['Bus_Name'].values[0]
    bus_res.result_df['voltage_element'] = vchc_element

    thermal_bus_res = dreams.hc.NodalSnapshot(
        feeder,
        bus_names=[bus_name],
        hc_kind='load',
        constraint='thermal',
        mode='duty',
        at_sec=tchc_t,
        save_violations=True,
    )

    thermal_element = thermal_bus_res.violations[bus_name]['over_capacity']['Name'].values[0]
    bus_res.result_df['thermal_hc_kw'] = thermal_bus_res.result_df['thermal_hc_kw']
    bus_res.result_df['thermal_element'] = thermal_element

    snap_shot_res.append(bus_res.result_df)


# %% [markdown]
# ## Demand Hosting Capacity result comparison
# Again, there is some error involved with the interpolation approach, however,
# the TCHC appears to match more closely as the violating element is often
# correctly selected.
#
# Substation constraints are not yet incorporated for demand, but such a result
# may help identify the maximum amount of load that would cause a substation
# limit to be reached, as in, maximum amount of MW the connected substation
# is rated for.

# %%
nodal_load_hc = pd.concat(snap_shot_res)

nodal_load_hc[['voltage_hc_kw', 'thermal_hc_kw', 'voltage_element', 'thermal_element']]

# %%
interp_load_hc.result_df[['vchc', 'tchc', 'vchc_element', 'tchc_element']]

# %% [markdown]
# # Conclusion
# This demo notebook showed how to use the interpolated hosting capacity
# functions of DREAMS and validate results using the snapshot hosting 
# capacity metho.
