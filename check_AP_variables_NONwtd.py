"""
Given the run directory from a FatesColdAllVars(Monthly) test, check the last timestep to see which
per-ageclass variables have the issue where their NON-weighted sum doesn't equal the
non-per-ageclass version.
"""
# pylint: disable=invalid-name
# pylint: disable=fixme

import numpy as np
import rfh_utils

###############
### Process ###
###############

# Get datasets
datasets = rfh_utils.get_datasets()

# Get per-ageclass variables and their equivalents
dict_perage_to_non_equiv, missing_var_lists = rfh_utils.get_dict_perage_to_non_equiv(
    datasets
)

# Analyze
nonperage_missing = []
too_many_duplexed = []
all_nan = []
no_boxdata = []

for perage_var in dict_perage_to_non_equiv:
    (
        non_perage_equiv,
        suffix,
        this_dict,
        do_deduplex,
        var_to_print,
    ) = rfh_utils.get_variable_info(dict_perage_to_non_equiv, perage_var)

    if non_perage_equiv is None:
        nonperage_missing.append(var_to_print)
        continue

    for i, ds in enumerate(datasets):
        # Get DataArrays to work with
        da = ds[non_perage_equiv]

        # Deduplex, if needed and possible
        if do_deduplex:
            da_ap, too_many_duplexed = rfh_utils.deduplex(
                ds, suffix, too_many_duplexed, perage_var, var_to_print
            )
            if var_to_print in too_many_duplexed:
                break
        else:
            da_ap = ds[perage_var].copy()

        # Get unweighted sum
        da_ap_sum = rfh_utils.get_unweighted_sum(suffix, da, da_ap)

        # Test
        this_dict = rfh_utils.compare_results(this_dict, da, da_ap_sum)

    if too_many_duplexed and too_many_duplexed[-1] == var_to_print:
        continue

    # Check for data that won't be plotted
    if all(np.all(np.isnan(da_diff)) for da_diff in this_dict["da_diffs"]):
        all_nan.append(var_to_print)
        continue
    if all(len(boxdata) == 0 for boxdata in this_dict["boxdata"]):
        no_boxdata.append(var_to_print)
        continue

    rfh_utils.add_result_text(
        non_perage_equiv,
        perage_var,
        this_dict,
        var_to_print,
    )

    # Make boxplots
    rfh_utils.make_boxplots(datasets, perage_var, this_dict, var_to_print)

    dict_perage_to_non_equiv[perage_var] = this_dict

#################
### Finish up ###
#################

rfh_utils.add_end_text(
    nonperage_missing, too_many_duplexed, missing_var_lists, all_nan, no_boxdata
)
rfh_utils.publish()
