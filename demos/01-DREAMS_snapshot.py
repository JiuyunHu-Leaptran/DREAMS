# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.5
#   kernelspec:
#     display_name: dreams_snl
#     language: python
#     name: python3
# ---

# %% [markdown]
# # DREAMS Snapshot Hosting Capacity
#
# Building on the introduction notebook, this notebook will show:
#
# * How to configure and run a snapshot `stepped hosting capacity` simulation looking at the impact of EV charging placed only on the C phase of the demo model.
#
# * Basic plots will be used to demonstrate the impact of this and overloading elements will be identified.
#
# * a basic statistic comparison approach will be shown
#
# * and violations from different simulation steps will be compared.
#
# Unlike more standard hosting capacity analysis, which returns only the maximum amount of an asset that may be added to a location until a system violation occurs, the stepped hosting capacity of DREAMS allows system states with violations so that the severity of impacts can be assesed and mitigation approaches tested.
#
# It is worth noting that DREAMS also has nodal hosting capacity functionality that will be shown in a later notebook.

# %% [markdown]
# # Load Feeder
# This is a typical way to load dreams and define some paths for the model and any outputs, which is described more in the introduction notebook.

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
# Initial plots and statistic collection for will be useful to compare the effects of the expected scenario simulation.

# %%
profile_fig_0, profile_ax_0 = feeder.plot()

# %%
box_fig_0, box_ax_0 = feeder.plot(kind='box')

# %%
stats_0 = feeder.stats

# %%
stats_0['init_kw']

# %%
stats_0['n_cust']

# %% [markdown]
# # Create Stepped Hosting Capacity Scenario 
#
# A simple stepped hosting capacity scenario is created below using 5 steps and 10 simulations.
#
#
# This means that the expectation is to add 5 different levels of increasing EV loading 10 times.
#
# The difference between each simulation will be the random number seed used to populate the demand across the available system locations.
#
# This is meant to account for some uncertainty of where such loads may be connected.
#

# %%
scenario = dreams.hc.Scenario(
    name='Snapshot Distributed Load',
    feeder=feeder,
    n_simulations=10,  # This is how many different random sets of allocations to run
    n_steps=5,  # this is how many steps from 0-full allocation each simulation takes
    #minimize_duplicates=False,  # Defaults to True, attempts to allocate elements to all available locations before stacking locations
)

# %% [markdown]
# ## Creation of alloctaion class and element
# The alloction object allows different types of elements to be added to a model in a user defined way.
#
# Below, the number of lvl 2 EV chargers using 15 kW is estimated to increase 1% each step.
#
# Also of note here is the `element_prepend` parameter, which can be helpful to identify to each element added to the model through this process.

# %%
# allocation class acts as container for  allocation elements
ev_alloc_2 = dreams.hc.Allocation(feeder, name='LVL_2_EV') 

# calculate number of level 2 chargers to add per scenario step
n_lvl_2 = int(feeder.stats['n_cust'] * .01)

# create load allocation element
lvl2_ev = dreams.hc.LoadAllocationElement(
    'LVL_2_EV',
    element_prepend='EV_LVL_2_',
    element_kw=15,
    element_kvar=0,
    n_elements=n_lvl_2
)

# add load elemnt to allocation
ev_alloc_2.add_allocation_element(lvl2_ev)

# display contents of ev_alloc_2 rules
ev_alloc_2.rules

# %% [markdown]
# ## definition of allocation location rule
# Each allocation can also follow various rules for placement.
#
# This example ensures that the location for interconnection is a transformer, 
# and that the bus2 phase is equal to C.

# %%

ev_alloc_2.add_location_rule(
    name='Secondary of C Phase Transformers',
    feeder_element_class='transformers',
    element_attribute='bus1_phase',
    comparison_operation='==',
    comparison_value='C',
    bus1_attribute='bus2',
    )

scenario.add_allocation(ev_alloc_2)

# %% [markdown]
# It's worth noting that standard pandas equalities are used for this comparison.
#
#
# Below showws the total number of such locations found in the demo feeder.

# %%
(feeder.transformers['bus1_phase'] == 'C').sum()

# %% [markdown]
# # writing of scenario steps and running of simulation
# DREAMS can write the steps, or openDSS redirects, used to modify the original feeder to the simulated state.
#
# this is valuable to recreate or analyze generated scenarios after simulation.
#
# These steps are written to a folder located with the model.

# %%
scenario.write_steps()  

# %% [markdown]
# The run method of the scenario class will execute the simulation.
# Results are stored in the object for later analysis.

# %%
scenario.run()

# %% [markdown]
# # Result plots
# The scenario object stores results according to seed and then step.
#
# Below is the load allocation showing the total load added, and the number of loads added at each step (cumulative).
#
# Similar alloction plots are available for other alloctaions, though for this demo, only load was applied.

# %%
scenario.seed_results[0].plot(kind='load_allocation')


# %% [markdown]
# The default plot of a snapshot simulation is the voltage profile.
# One can see that as the steps increase, more load is added, and the voltage spread increases.
#
# It is worth noting that the levels presented are system-wide voltages.

# %%
scenario.results.plot()

# %% [markdown]
# As a reminder, the original voltage profile is shown below

# %%
profile_fig_0

# %% [markdown]
# After a simulation has been run, the `feeder.plot()` method is called again, which will display the same plot, but from the most recent feeder state.
#
# Which happends to be the last step from the last seed of the hosting capacity scenario.
#
# It is easy to see that the B and C phase are much lower than the A phase, and the general voltage spread is much larger.

# %%
profile_fig_1, profile_ax_1 = feeder.plot()

# %% [markdown]
# A similar process could be completed using the box plots where the original voltage boxes are shown below

# %%
box_fig_0

# %% [markdown]
# And the post simulation voltage boxes (reprentative of the last step from the last seed) are simply created from the feeder object.

# %%
box_fig_1, box_ax_1 = feeder.plot(kind='box')

# %% [markdown]
# Another useful type of plot is the `plotly` plot that allows for a more interactive experience typical of plotly plots.

# %%
fig = feeder.plot(kind='plotly')

# %% [markdown]
# ## additional simulation plots
# Transformer and line loading plots are also available from the scenario object after it has been run.
#
# The transformer loading plot more clearly shows the impact of the different seeds - where due to the random placement, different amounts of transformer loading occurs (as shown with the various grey lines).
#
# The maximum presented is actualy the average maximum from all seeds.

# %%
scenario.results.plot(kind='transformer')

# %% [markdown]
# Additionally, the line capacity plots show that only the primary system is impacted by increased demand.
#
# This is indicative of the load being placed directly on the low side of the transformer.

# %%
scenario.results.plot(kind='line')

# %% [markdown]
# While plot calls will typically use the most recent feeder state, as of this writing, the stored dataframes need to be updated to reflect the added loads.
#
# As shown below, the call to the `loads` dataframe does not include any of the additional loads until the update method is called.

# %%
feeder.loads.tail(5)

# %%
feeder.update()
feeder.loads.tail(5)

# %% [markdown]
# ## compare pre/post statistics
# since the original statistics were stored, and the feeder has been recently updated,
# it may be worth looking at the impact of the simulation.
#
# This can be accomplished by creating a dataframe from the feeder stats dictionary, and then doing a simple substraction.
#
# Note: some columns are removed as they do not have subtraction functionality.

# %%
stats_1 = feeder.stats


# %%
import pandas as pd

cols_to_drop = ['kv_levels', 'path', 'name']
stat_df = pd.DataFrame.from_dict({'original':stats_0, 'post_ev':stats_1})
stat_df.drop(cols_to_drop, inplace=True)

stat_df['ev_impact'] = stat_df['post_ev'] - stat_df['original'] 
stat_df

# %% [markdown]
# NOTE: due to previous research direction, and speed of snapshot simulations, export of snapshot results has not been as deeply developed as QSTS results.

# %% [markdown]
# # go to step
# DREAMS allows the simulation go to a specific state, essentially running the 
# simulation again and stopping at a certain step.
#
# This allows the feeder state to be more closely examined.
#
# WARNING: using the go_to_step method will erase all previous step results.

# %% [markdown]
# To verify this operation feeder violations from the last step are saved, 
# then comparted to the violations from step 3.

# %%
violations_step_5 = feeder.id_violations()
violations_step_5.keys()

# %%
violations_step_5['n_over_capacity']

# %%
scenario.go_to_step(step=3)

# %%
violations_step_3 = feeder.id_violations()
violations_step_3['n_over_capacity']

# %% [markdown]
# As one can observed, there are fewer violations in step_3 than step_5 - 
# which makes sense, as there is more demand in step_5.
#
# Additionaly, the overcapacity lines (and other objects identified in violation) can be further examined as they are also pandas dataframes.

# %%
violations_step_3['over_capacity_lines'].head()

# %% [markdown]
# This concludes the basic snapshot stepped hosting capacity demo.
