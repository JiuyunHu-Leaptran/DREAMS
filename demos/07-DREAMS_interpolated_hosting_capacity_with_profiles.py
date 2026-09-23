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
#     name: dreams_2026
# ---

# %% [markdown]
# # DREAMS Interpolated QSTS Hosting Capacity with Asset Profiles
#
# With the interpolated hosting capacity approach, it is possible to use
# profiles that modify the added asset's contribution to the system.
#
# This is useful to model the temporal interactions between demand and
# generation assocaited with, for example, PV geneartion or Large load
# time-of-use schedules.
#
# It should be noted that this method is still experimental and being refined.
# Currently, the method is designed to study 3-phase medium voltage buses.

# %%
import dreams

from pathlib import Path
import os
import pandas as pd
import matplotlib.pyplot as plt


# %% [markdown]
# # Define Paths
# Similar to the previous demo, the feeder used here is the synthetic bay 
# area feeder with a single time series demand profile for all loads.

# %%
model_dir = Path(r'models') / 'sfo_p1udt1469'
profile_dir  = Path(r'models') / 'generic_profiles'

output_dir = model_dir / 'temp_outputs'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# %% [markdown]
# # Select Buses
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
feeder.buses.loc[buses_to_test]

# %% [markdown]
# # Import Time series for Shape Creation
# This demo will utilize generic time series data that are used to create
# Shape objects to simulate:
# irradiance, windspeed, and demand time-of-use
#
# The below process also normalizes the irradiance and wind speed data 
# according to typical values.

# %%
os.listdir(profile_dir)

# %%
irradiance_profile = dreams.Shape(
    profile_dir/'generic_15min_wpm2.csv',
    'generic_irradiance',
    hour_interval=15/60,
    column=0,
    mode='duty',
    )
irradiance_profile.data /= 1000  # to ensure PU
ax = irradiance_profile.data.plot()
ax.set_xlim([0, 24*4*7])
ax.grid(True)
ax.set_title('PU Irradiance')

# %%
wind_profile = dreams.Shape(
    profile_dir/'generic_15min_mps.csv',
    'generic_wind',
    hour_interval=15/60,
    column=0,
    mode='duty',
    )

# modify raw profile to PU while accounting for cut in and out
cut_in = 3.5
cut_out = 25
rated = 14

under_cut_in = wind_profile.data < cut_in
over_cut_out = wind_profile.data > cut_out
no_gen = under_cut_in | over_cut_out

wind_profile.data /= rated
wind_profile.data[no_gen] = 0
ax = wind_profile.data.plot()
ax.set_xlim([0, 24*4*7])
ax.grid(True)
ax.set_title('PU Wind')

# %%
tou_profile = dreams.Shape(
    profile_dir/'generic_15min_tou.csv',
    'generic_tou',
    hour_interval=15/60,
    column=0,
    mode='duty',
    )

ax = tou_profile.data.plot()
ax.set_xlim([0, 24*4*7])

ax.grid(True)
ax.set_title('PU Time-of-use Demand')

# %% [markdown]
# # Run interpolated generation hosting capacity
# The `QSTS_HC` method accepts all simulation parameters and returns an 
# object that contains results and timings.
#
# For this demo, a constant simulation is run, followed by one with a profile.
# This is so that the constant interpolated results can be compared to 
# snapshot results, and then the interpolated profile results can be 
# compared to the constant interpolated results to show how a profile may
# affect hosting capacity.

# %%
constant_power_res = dreams.hc.interp.QSTS_HC(
    feeder,
    buses_to_test,
    output_dir=output_dir,
    kind='gen',
    step_size_seconds=60*15,  # 15 minute profile
    total_time_steps=24*4*7,  # run for 7 days
    name='constant_power'
)

# %%
pv_profile_res = dreams.hc.interp.QSTS_HC(
    feeder,
    buses_to_test,
    output_dir=output_dir,
    kind='gen',
    asset_shape=irradiance_profile,
    step_size_seconds=60*15,  # 15 minute profile
    total_time_steps=24*4*7,  # run for 7 days
    name='pv_profile'
)

# %%
wind_profile_res = dreams.hc.interp.QSTS_HC(
    feeder,
    buses_to_test,
    output_dir=output_dir,
    kind='gen',
    asset_shape=wind_profile,
    step_size_seconds=60*15,  # 15 minute profile
    total_time_steps=24*4*7,  # run for 7 days
    name='wind_profile',
)

# %% [markdown]
# # Run Snapshot hosting capacity to validate results

# %% [markdown]
# As in the previous demo, for each interpolated result, a snapshot hosting 
# capacity is also calculated to validate the interpolated hosting 
# capacity results.

# %%
feeder = dreams.Feeder(model_dir/'Main_with_profile.dss', name='sfo_p1udt1469')

snap_shot_res = []

time_step = 60*15  # 15 minutes per step

for bus_name, row in constant_power_res.result_df.iterrows():
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

    thermal_element = thermal_bus_res.violations[bus_name]['over_capacity']['Name'].values[0]
    bus_res.result_df['thermal_hc_kw'] = thermal_bus_res.result_df['thermal_hc_kw']
    bus_res.result_df['thermal_element'] = thermal_element

    snap_shot_res.append(bus_res.result_df)

nodal_gen_hc = pd.concat(snap_shot_res)

# %% [markdown]
# # Generation Hosting Capacity Result Comparisons
# For a clearer, immediate comparison of profile impacts, the below plots
# show how the snapshot and constant results are very similar - which
# validates the interpolation method, and then the Wind and PV results
# are different from the constant asset profile result.
#
# In this example, the results show that applying a reasonable generation
# profile to the hosting capacity asset reveals that more capacity is
# available.

# %%
fig, ax = plt.subplots()

ax.scatter(nodal_gen_hc['bus_dist_km'], nodal_gen_hc['voltage_hc_kw'])
ax.scatter(constant_power_res.result_df['distance_from_sub'], constant_power_res.result_df['vchc'], marker='x')
ax.scatter(wind_profile_res.result_df['distance_from_sub'], wind_profile_res.result_df['vchc'])
ax.scatter(pv_profile_res.result_df['distance_from_sub'], pv_profile_res.result_df['vchc'])


ax.set_ylim([0,70e3])
ax.legend(['Snapshot', 'Constant', 'Wind', 'PV'])
ax.grid()
ax.set_title('VCHC Generation')
ax.set_ylabel('Hosting Capacity [kW]')
ax.set_xlabel('Distance from Substation [km]')

# %%
fig, ax = plt.subplots()

ax.scatter(nodal_gen_hc['bus_dist_km'], nodal_gen_hc['thermal_hc_kw'])
ax.scatter(constant_power_res.result_df['distance_from_sub'], constant_power_res.result_df['tchc'], marker='x')
ax.scatter(wind_profile_res.result_df['distance_from_sub'], wind_profile_res.result_df['tchc'])
ax.scatter(pv_profile_res.result_df['distance_from_sub'], pv_profile_res.result_df['tchc'])

ax.set_ylim([0,25e3])
ax.legend(['Snapshot', 'Constant', 'Wind', 'PV'])
ax.grid()
ax.set_title('TCHC Generation')
ax.set_ylabel('Hosting Capacity [kW]')
ax.set_xlabel('Distance from Substation [km]')


# %% [markdown]
# Detailed results from the generation hosting capacity are printed below,
# with high level take aways being:
#
# Constant power results are close to the nodal snapshot results, this is
# expected as they are meant to be equivalent.
#
# In general, the profiles identified different critical time steps in which
# violations occur.
# This is due to the non-constant profiles used.
#
# Using profiles results in different, typically higher VCHC - due to:
# 1. Effective de-rating of asset due to non-perfect (more realistic) output
# 2. temporal interactions (no pv generation at night and intermittent 
# wind generation)
#
# SCHC is much higher as it:
# 1. Avoids unrealistic overnight lows when PV is inactive.
# 2. Includes de-rating of asset due to non-perfect (more realistic) output

# %%
nodal_gen_hc[['voltage_hc_kw', 'thermal_hc_kw', 'voltage_element', 'thermal_element',]]

# %%
constant_power_res.result_df[['vchc','tchc','vchc_element','vchc_ndx', 'tchc_element', 'schc']]


# %%
wind_profile_res.result_df[['vchc','tchc','vchc_element', 'vchc_ndx','tchc_element', 'schc']]


# %%
pv_profile_res.result_df[['vchc','tchc','vchc_element', 'vchc_ndx', 'tchc_element', 'schc']]

# %% [markdown]
# # Run interpolated demand hosting capacity
# Demand, or load, hosting capacity is configured in a similar fashion as 
# generation hosting capacity, though the `kind` variable is set to `load`.

# %%
constant_load_res = dreams.hc.interp.QSTS_HC(
    feeder,
    buses_to_test,
    output_dir=output_dir,
    kind='load',
    step_size_seconds=60*15,  # 15 minute profile
    total_time_steps=24*4*7,  # run for 7 days
    name='constant_demand'
)

# %%
tou_load_res = dreams.hc.interp.QSTS_HC(
    feeder,
    buses_to_test,
    output_dir=output_dir,
    kind='load',
    asset_shape=tou_profile,
    step_size_seconds=60*15,  # 15 minute profile
    total_time_steps=24*4*7,  # run for 7 days
    name='tou_profile',

)

# %%
feeder = dreams.Feeder(model_dir/'Main_with_profile.dss', name='sfo_p1udt1469')

snap_shot_res = []

time_step = 60*15  # 15 minutes per step

for bus_name, row in constant_load_res.result_df.iterrows():
    # create times to test from interpolated results
    print(bus_name)
    vchc_t = row['vchc_ndx'] * time_step
    tchc_t = row['tchc_ndx'] * time_step

    bus_res = dreams.hc.NodalSnapshot(
        feeder,
        bus_names=[bus_name],
        constraint='voltage',
        hc_kind='load',
        mode='duty',
        at_sec=vchc_t,
        save_violations=True
    )

    # generation will typically lead to over voltage violations
    vchc_element = bus_res.violations[bus_name]['under_voltage']['Bus_Name'].values[0]
    bus_res.result_df['voltage_element'] = vchc_element

    thermal_bus_res = dreams.hc.NodalSnapshot(
        feeder,
        bus_names=[bus_name],
        constraint='thermal',
        hc_kind='load',
        mode='duty',
        at_sec=tchc_t,
        save_violations=True,
    )

    thermal_element = thermal_bus_res.violations[bus_name]['over_capacity']['Name'].values[0]
    bus_res.result_df['thermal_hc_kw'] = thermal_bus_res.result_df['thermal_hc_kw']
    bus_res.result_df['thermal_element'] = thermal_element

    snap_shot_res.append(bus_res.result_df)

nodal_load_hc = pd.concat(snap_shot_res)

# %% [markdown]
# # Demand Hosting Capacity Result Comparisons
# Again, plots are presented before detailed tables are printed.
# While there is some error in the VCHC results, the TOU profile does
# apear to allow larger loads to be connected at tested buses.
#
# The interpolated TCHC results from a constant load match very well to 
# the snapshot results as the critical element was identified in all cases.
# The TOU profile increased TCHC by 500-1,000 kW at the tested buses.

# %%
fig, ax = plt.subplots()

ax.scatter(nodal_load_hc['bus_dist_km'], nodal_load_hc['voltage_hc_kw'])
ax.scatter(constant_load_res.result_df['distance_from_sub'], constant_load_res.result_df['vchc'], marker='x')
ax.scatter(tou_load_res.result_df['distance_from_sub'], tou_load_res.result_df['vchc'])
ax.set_ylim([0,80e3])
ax.legend(['Snapshot', 'Constant', 'TOU'])
ax.grid()
ax.set_title('VCHC Demand')
ax.set_ylabel('Hosting Capacity [kW]')
ax.set_xlabel('Distance from Substation [km]')

# %%
fig, ax = plt.subplots()

ax.scatter(nodal_load_hc['bus_dist_km'], nodal_load_hc['thermal_hc_kw'])
ax.scatter(constant_load_res.result_df['distance_from_sub'], constant_load_res.result_df['tchc'], marker='x')
ax.scatter(tou_load_res.result_df['distance_from_sub'], tou_load_res.result_df['tchc'])
ax.set_ylim([0,3e3])
ax.legend(['Snapshot', 'Constant', 'TOU'])
ax.grid()
ax.set_title('TCHC Demand')
ax.set_ylabel('Hosting Capacity [kW]')
ax.set_xlabel('Distance from Substation [km]')


# %%
nodal_load_hc[['voltage_hc_kw', 'thermal_hc_kw', 'voltage_element', 'thermal_element',]].head()

# %%
constant_load_res.result_df[['vchc','vchc_element', 'vchc_ndx', 'tchc', 'tchc_element','tchc_ndx']].head()

# %%
tou_load_res.result_df[['vchc','vchc_element', 'vchc_ndx', 'tchc', 'tchc_element','tchc_ndx']].head()

# %% [markdown]
# # Conclusion
# As above results show, using profiles can increase hosting capacity results.
# However, the mechanism of this reduction relies on the asset not exceeding
# the provided profile.
# While this may be obvious, care should be taken to describe the assumptions - 
# especially when describing time-of-use demand profiles.
