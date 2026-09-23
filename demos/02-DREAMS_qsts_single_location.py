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
# # DREAMS - QSTS Single Location
#
# This demo shows how to run a multi-day QSTS simulation of concentread PV
# at a single location with PV, inverter controls.
#
# NOTE: code for storage and controls are also included, though not implemented (yet)
#

# %%
import dreams

from pathlib import Path
import os

# %%
model_dir = Path(r'models') / r'sfo_p1udt1469'

output_dir = model_dir / 'temp_outputs'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# %%
feeder = dreams.Feeder(model_dir/'Main.dss', name='sfo_p1udt1469')

# %% [markdown]
# # identifying single location and connected line
# for system location and control monitoring

# %%
is_hv = feeder.loads['primary']
feeder.loads[~is_hv].sort_values('kw', ascending=False).head(3)

# %%
single_location = feeder.loads[~is_hv].sort_values('kw', ascending=False).iloc[0]
single_location

# %%
service_line = (feeder.lines['short_bus2'] == single_location['short_bus1']) \
    | (feeder.lines['short_bus1'] == single_location['short_bus1'])

feeder.lines[service_line]

# %%
# line feeding single location should be used to control storage
line_to_monitor = feeder.lines[service_line].index[0]
feeder.lines.loc[line_to_monitor]

# %% [markdown]
# # adding qsts profiles

# %% [markdown]
# ## demand data
# loading and identifying max day

# %%
demand_fp = model_dir / 'pu_substation_demand.csv'

demand_shape = dreams.Shape(demand_fp, 'demand_profile', column=0, hour_interval=15/60)

ax = (demand_shape.data).plot()
ax.grid()
ax.set_axisbelow(True)
ax.set_title('Demand Profile')
ax.set_ylabel('Demand [kW]')
ax.set_xlabel('15 Minute Interval')

# %% [markdown]
# Locating timestep surrounding max demand day and crating range for plot

# %%
max_demand_ts = demand_shape.data.idxmax()
max_demand_ts

max_day = int(max_demand_ts / (24 * 4))


# %%
max_demand_ts

# %%
start_index = (max_day-1)*(4*24)
end_index = start_index + 3*4*24

# %%

ax = (demand_shape.data).plot()
ax.grid()
ax.set_axisbelow(True)
ax.set_title('Demand Profile')
ax.set_ylabel('Demand [kW]')
ax.set_xlabel('15 Minute Interval')
ax.set_xlim([start_index, end_index])

# %%
irradiance_fp = model_dir / 'pu_irradiance.csv'

irradiance_shape = dreams.Shape(irradiance_fp, 'irradiance_profile', column=0, hour_interval=15/60)

ax = irradiance_shape.plot()
ax.grid()
ax.set_axisbelow(True)
ax.set_title('Irradiance Profile')
ax.set_ylabel('Irradiance [PU]')
ax.set_xlabel('15 Minute Interval')

# %%
ax = irradiance_shape.plot()
ax.grid()
ax.set_axisbelow(True)
ax.set_title('Irradiance Profile')
ax.set_ylabel('Irradiance [PU]')
ax.set_xlabel('15 Minute Interval')
ax.set_xlim([start_index, end_index])

# %% [markdown]
# # qsts scenario creation

# %%
qsts_scenario = dreams.hc.Scenario(
    name='QSTS Concentrated PV and Storage with Control',
    feeder=feeder,
    n_simulations=1,  # single location
    n_steps=5,
    qsts_step_size_sec = 60*60,  # x one hour timestep.
    duration_seconds = 3*24*60*60, # three day sim
    qsts_hour_offset=start_index,
    max_control_iterations=1000
    #step_title='PV [MW]',
    #step_labels=step_labels
)

# %% [markdown]
# ## adding shapes
# shapes are added to th bse redirects
# and loads altered to follow demand shape

# %%
# add demand profile redirect scenario
qsts_scenario.base_redirects.append(demand_shape.create_shape_redirect(use_file=False))

# apply demand profile to all loads
qsts_scenario.base_redirects.append(demand_shape.create_edit_elements_redirect(feeder))

# add irradiance profile to base redirects
qsts_scenario.base_redirects.append(irradiance_shape.create_shape_redirect(use_file=False))

# %% [markdown]
# # inverter control
#
# This control applies to all pv inverters that have control listed as 'default_vv',
# which is added to the pv allocation as a control rule.
#
# Additional parameters can be added to the InverterControl that describe the 
# control type:
# * vv (volt/var) 
# * vw (volt/watt)
# * vv_vw (both volt var and volt watt)
#
# Note: in this case, vv_vw conflicts with the storage action at the single location
# as both controls deal with real power - so, for this reason, only vv is shown here.
#
# More information can be found in the InverterControl.py class file.

# %%
# creating inverter control, adding to definition to control redirects
inverter_control = dreams.InverterControl(name='default_vv', kind='vv')  
qsts_scenario.add_control_redirect(inverter_control.create_control_redirect())

# %% [markdown]
# # pv allocation

# %%
allocation = dreams.hc.Allocation(feeder, name='Concentrated PV')
concentrated_max_pv = 1000  # kw

# create pv allocation element
stepeed_pv = dreams.hc.PhotovoltaicAllocationElement(
    'Concentrated Location',
    element_prepend='added_pv_',
    element_kva=concentrated_max_pv/qsts_scenario.n_steps,
    total_kva=concentrated_max_pv,
    kind='total',
    element_kv=single_location['kv']/1.732,
)
allocation.add_allocation_element(stepeed_pv)

allocation.add_location_rule(
    'Single Location',
    feeder_element_class='loads',
    element_attribute='short_bus1',
    comparison_operation='==',
    comparison_value=single_location.short_bus1,
    )

allocation.add_shape_rule(kind='yearly', name='irradiance_profile')

# adding control rule to  pv allocation
allocation.add_control_rule('default_vv')

# adding pv allocation to scenario
qsts_scenario.add_allocation(allocation)


# %% [markdown]
# # storage control
#
# This storage control monitors the flow on the given element, to achieve
# peak shave high and low whil allowing some export.
#
# Again, further information can be found in the StorageControl class definition
# or in the openDSS documentation as the class accomodates for variable keywords
# to be passed to the resulting dss defintion.
#
# Note: the max_ctrl_iter value is very large to allow the control actions to 
# complete - this may not be required all the times.
#

# %%
storage_controller = dreams.StorageControl(
    name='storage_control',
    element=f'line.{line_to_monitor}',
    kwtarget=50,  # manage peak draw
    kwtargetlow=-25,  # handle pv export.
    resetlevel=0.2,  # minimum soc to allow discharge
    reserve=0,
    # inhibittime=1.0,
    max_ctrl_iter=1000,
    eventlog='yes',
    # dispfactor=0.1,
    monphase='min'  # should it be min? defaults to ave..
    )  

# add storage controller to scenario base redirects (comment out below to NOT add storage control)
qsts_scenario.add_control_redirect(storage_controller.create_control_redirect())

# %% [markdown]
# ## storage allocation
# ratio of pv to storage
#

# %%
storage_to_pv = 2.0

per_step_storage = concentrated_max_pv/qsts_scenario.n_steps * storage_to_pv

each_step_storage = [x*per_step_storage for x in range(0,qsts_scenario.n_steps+1)]

# %%
each_step_storage

# %%
storage_allocation_obj = dreams.hc.Allocation(feeder, name='Centralized Storage')


storage_to_add = dreams.hc.StorageAllocationElement(
    'Concentrated Storage',  # this is the name, or reference, to the allocation element
    element_prepend= f'new_storage_', 
    element_kva= 400, 
    element_kwh= 1200,
    total_kva= each_step_storage,
    element_stored = 20,
    kind= 'each_step'
)

storage_allocation_obj.add_allocation_element(storage_to_add)

# add location rule for allocation
storage_allocation_obj.add_location_rule(
    'single location',
    feeder_element_class='loads',
    element_attribute='short_bus1',
    comparison_operation='==',
    comparison_value=single_location.short_bus1,
    )

storage_allocation_obj.add_control_rule('storage_control')  

# add allocation to scenario
# qsts_scenario.add_allocation(storage_allocation_obj) # comment out to remove storage

# %% [markdown]
# # run simulation

# %%
qsts_scenario.write_steps()  
qsts_scenario.run()


# %% [markdown]
# Note that non-converged steps will be identified during runtime - 
# this can happen for a wide variety of reasons.
#
# Typically, non-converging simulations are not believable or could indicate a very serious system flaw

# %%
# dreams.dss.cmd('show eventlog')  # this will show the event log for control action

# %% [markdown]
# maybe something about how QSTS results are stored? 
#
# monitors, group results...
#
# result export

# %%
qsts_scenario.results.export_results()  # allows for later results analysis

# %% [markdown]
# # results

# %%
# to ensure propoper allocation
qsts_scenario.seed_results[0].plot(kind='pv_allocation')

# %%
# to ensure propper allocation
qsts_scenario.seed_results[0].plot(kind='storage_allocation')

# TODO Modify for single ax, update labels.

# %%
fig, ax = qsts_scenario.seed_results[0].plot(kind='p', use_dt=True)



# %%
fig, ax = qsts_scenario.seed_results[0].plot(kind='q', use_dt=True)

# %%
fig, ax = qsts_scenario.seed_results[0].plot(kind='voltage', use_dt=True, legend=False)
ax.set_title('Primary Maximum and Minimum Voltages')

# %%
fig, ax = qsts_scenario.seed_results[0].plot(kind='voltage', use_dt=True, primary=False, legend=True)
ax.set_title('Secondary Maximum and Minimum Voltages')

# %%
fig, ax = qsts_scenario.seed_results[0].plot(kind='line', primary=True, use_dt=True)
qsts_scenario.seed_results[0].plot(kind='line', primary=False, legend=True, use_dt=True, ax=ax)
ax.set_title('Maximum Used Capacity of System Lines\n(dashed=secondary)')

# %%
fig, ax = qsts_scenario.seed_results[0].plot(kind='transformer', use_dt=True)

# %%
fig, axes = qsts_scenario.seed_results[0].plot(kind='violations', use_dt=True, as_percent=False)

# %%
fig, ax = qsts_scenario.seed_results[0].plot(kind='pv_p', use_dt=True, legend_outside=True)


# %%
fig, ax = qsts_scenario.seed_results[0].plot(kind='pv_q', use_dt=True, legend_outside=True)  # NOTE: will change if volt/var controls are changed

# %%
# fig, ax = qsts_scenario.seed_results[0].plot(kind='storage_p', use_dt=True, legend_outside=True)  # for storage plot

# %%
# fig, ax = qsts_scenario.seed_results[0].plot(kind='storage_soc', use_dt=True, legend_outside=True) # for storage plot

# %%
feeder.plot(kind='topo')  # single location of system

# %% [markdown]
# NOTE: looks like this violation is due to an issue witht he control?
# shouldn't just stop right?

# %% [markdown]
# # goto step qsts
# accounting for storage behavior may be required, else always re-initialized 
#

# %%
qsts_scenario.go_to_step(step=2, qsts_step=37, update_feeder=True)

# %%
feeder.id_violations()['over_capacity']


