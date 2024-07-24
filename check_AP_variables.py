"""
Given the run directory from a FatesColdAllVars(Monthly) test, check the last timestep to see which
per-ageclass variables have the issue where their weighted sum doesn't equal the non-per-ageclass
version.
"""

# %% Setup
import glob
import os
import re
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

# What machine are we on?
from socket import gethostname
hostname = gethostname()
if any(x in hostname for x in ["derecho", "casper"]) or "crhtc" in hostname:
    machine = "glade"
    # Only possible because I have export PYTHONPATH=$HOME in my .bash_profile
    from ctsm_python_gallery_myfork.ctsm_py import fates_xarray_funcs as fates_utils
else:
    raise NotImplementedError(f"Hostname not recognized: {hostname}")


# %% Import

set0 = "tests_0718-095838de"  # Before changes
set1 = "tests_0718-130915de"  # _AP fixes only
set2 = "tests_0722-142229de"  # All fixes
set3 = "tests_0723-141100de"  # 103fdc9 (b4b with above)

# testset_dir_list = [set0, set1]
# testset_dir_list = [set1, set2]
testset_dir_list = [set0, set3]
# testset_dir_list = set3

top_dir = "/glade/derecho/scratch/samrabin"
test_name = "SMS_Lm49.f10_f10_mg37.I2000Clm60Fates.derecho_intel.clm-FatesColdAllVarsMonthly"

datasets = []
comparing_2 = isinstance(testset_dir_list, list) and len(testset_dir_list) > 1
if comparing_2 and len(testset_dir_list) > 2:
    raise RuntimeError("Max # runs to compare is 2")
if not isinstance(testset_dir_list, list):
    testset_dir_list = [testset_dir_list]
for testset_dir in testset_dir_list:
    test_run_dir = os.path.join(top_dir, testset_dir, test_name + "*", "run")
    test_run_dir = os.path.join(test_run_dir, "*.clm2.h0.*nc")

    file_list = glob.glob(test_run_dir)
    if len(file_list) == 0:
        raise FileNotFoundError(f"No files found matching {test_run_dir}")
    file_list.sort()

    # Only examine the last timestep, for efficiency
    this_file = file_list[-1]
    ds = xr.open_dataset(this_file)
    if "time" in ds.dims:
        ds = ds.isel(time=-1)
    datasets.append(ds)

# %% Process

weightvar = "FATES_PATCHAREA_AP"

# Check dataset
if weightvar not in ds:
    raise RuntimeError(f"This analysis relies on {weightvar}, which is missing from {this_file}")

# Get per-ageclass variables and their equivalents
pattern = "FATES_[A-Z_]+_[A-Z]*AP[A-Z]*"
p = re.compile(pattern)
dict_perage_to_non_equiv = {}
var_list = [v for v in ds]
var_list.sort()
for this_var in var_list:
    match = p.match(this_var)
    if match is None:
        continue
    suffix = this_var.split("_")[-1]
    suffix2 = suffix.replace("AP", "")
    non_perage_equiv = "_".join(this_var.split("_")[:-1])
    if suffix2:
        non_perage_equiv += "_" + suffix2
    if non_perage_equiv in ds:
        dict_perage_to_non_equiv[this_var] = {
            "non_perage_equiv": non_perage_equiv,
            "isclose": [],
            "isclose_emoji": [],
            "isclose_glyph": [],
            "max_abs_diff": [],
            "max_pct_diff": [],
            "da_diffs": [],
        }
    else:
        dict_perage_to_non_equiv[this_var] = {
            "non_perage_equiv": None,
        }

# Analyze
weights = ds[weightvar].fillna(0)
nonperage_missing = []
too_many_duplexed = []
for perage_var in dict_perage_to_non_equiv.keys():
    this_dict = dict_perage_to_non_equiv[perage_var]
    non_perage_equiv = this_dict["non_perage_equiv"]

    # Will de-duplexing be needed?
    suffix = perage_var.split("_")[-1]
    do_deduplex = len(suffix) > 2
    if do_deduplex:
        var_to_print = perage_var.replace("AP", "(AP)")
    else:
        var_to_print = perage_var.replace("_AP", "(_AP)")

    if non_perage_equiv is None:
        nonperage_missing.append(var_to_print)
        continue

    for ds in datasets:
        # Get DataArrays to work with
        da = ds[non_perage_equiv]
        da_ap = ds[perage_var]

        # Deduplex, if needed and possible
        if do_deduplex:
            n_duplexed_dims = len(suffix) / 2
            if n_duplexed_dims > 2:
                too_many_duplexed.append(var_to_print)
                break
            if suffix == "APFC":
                da_ap = fates_utils.agefuel_to_age_by_fuel(perage_var, ds)
            elif suffix == "APPF":
                da_ap = fates_utils.deduplex(ds, perage_var, "age", "pft")
            elif suffix == "SZAP":
                da_ap = fates_utils.deduplex(ds, perage_var, "scls", "age")
            else:
                raise NotImplementedError(f"Unrecognized suffix: _{suffix}")

        # Get weighted mean
        da_ap_wtmean = da_ap.weighted(weights).mean(dim="fates_levage")
        np.all(np.isclose(da, da_ap.mean(dim="fates_levage"), equal_nan=True))
        if da.dims != da_ap_wtmean.dims:
            raise RuntimeError(f"Dimensions of da_ap_wtmean ({da_ap_wtmean.dims}) don't match those of da ({da.dims})")

        # Test
        is_close = np.all(np.isclose(da, da_ap_wtmean, equal_nan=True))
        this_dict["isclose"].append(is_close)
        this_dict["isclose_emoji"].append("✅" if is_close else "❌")
        this_dict["isclose_glyph"].append("✓" if is_close else "X")
        da_diff = da_ap_wtmean - da
        this_dict["da_diffs"].append(da_diff)
        this_dict["max_abs_diff"].append(np.nanmax(np.abs(da_diff).values))
        this_dict["max_pct_diff"].append(100*np.nanmax(np.abs(da_diff/da).values))

    if too_many_duplexed and too_many_duplexed[-1] == var_to_print:
        continue

    emojis = " → ".join(this_dict["isclose_emoji"])

    print(f"{emojis} {var_to_print}:")
    max_abs_diff = this_dict["max_abs_diff"]
    max_pct_diff = this_dict["max_pct_diff"]
    if not comparing_2 or (max_abs_diff[0] == max_abs_diff[1] and max_pct_diff[0] == max_pct_diff[1]):
        print(f"     max abs diff = {max_abs_diff[0]:.3g}")
        print(f"     max rel diff = {max_pct_diff[0]:.1f}%")
    else:
        print(f"     max abs diff = {max_abs_diff[0]:.3g} → {max_abs_diff[1]:.3g}")
        print(f"     max rel diff = {max_pct_diff[0]:.1f}% → {max_pct_diff[1]:.1f}%")

    # Make boxplots
    boxdatas = []
    labels = []
    for i, da_diff in enumerate(this_dict["da_diffs"]):
        boxdata = da_diff.values[np.where(np.abs(da_diff) > 0)]
        boxdatas.append(boxdata)
        if i==0:
            label = "before"
        elif i==1:
            label = "after"
        else:
            label = str(i)
        emoji = this_dict["isclose_glyph"][i]
        labels.append(f"{label} {emoji}")
    plt.boxplot(boxdatas, labels=labels)
    plt.ylabel(f"discrepancy ({datasets[0][perage_var].attrs['units']})")
    plt.title(var_to_print)
    plt.show()

    dict_perage_to_non_equiv[perage_var] = this_dict

# Print


print("\n     ".join(["\n🤷 Non-per-age equivalent not in Dataset:"] + nonperage_missing))

print("\n     ".join([f"\n🤷 Too many (> 2) duplexed dimensions:"] + too_many_duplexed))
