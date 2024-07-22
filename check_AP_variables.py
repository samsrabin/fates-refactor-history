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
    from ctsm_python_gallery_myfork.ctsm_py import utils
    from ctsm_python_gallery_myfork.ctsm_py import fates_xarray_funcs as fates_utils
else:
    raise NotImplementedError(f"Hostname not recognized: {hostname}")


# %% Import

# test_run_dir = "/glade/derecho/scratch/samrabin/tests_0718-095838de/SMS_Lm49.f10_f10_mg37.I2000Clm60Fates.derecho_intel.clm-FatesColdAllVarsMonthly.GC.*/run"
# test_run_dir = "/glade/derecho/scratch/samrabin/tests_0718-130915de/SMS_Lm49.f10_f10_mg37.I2000Clm60Fates.derecho_intel.clm-FatesColdAllVarsMonthly.GC.0718-130915de_int/run"
test_run_dir = "/glade/derecho/scratch/samrabin/tests_0722-142229de/SMS_Lm49.f10_f10_mg37.I2000Clm60Fates.derecho_intel.clm-FatesColdAllVarsMonthly.GC.0722-142229de/run"

file_list = glob.glob(os.path.join(test_run_dir, "*.clm2.h0.*nc"))
file_list.sort()

# Only examine the last timestep, for efficiency
this_file = file_list[-1]
ds = xr.open_dataset(this_file)
if "time" in ds.dims:
    ds = ds.isel(time=-1)

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
    if match is not None:
        suffix = this_var.split("_")[-1]
        suffix2 = suffix.replace("AP", "")
        non_perage_equiv = "_".join(this_var.split("_")[:-1])
        if suffix2:
            non_perage_equiv += "_" + suffix2
        if non_perage_equiv in ds:
            dict_perage_to_non_equiv[this_var] = non_perage_equiv
        else:
            dict_perage_to_non_equiv[this_var] = None

# Analyze
weights = ds[weightvar].fillna(0)
nonperage_missing = []
too_many_duplexed = []
for i, (perage_var, non_perage_equiv) in enumerate(dict_perage_to_non_equiv.items()):

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

    # Get DataArrays to work with
    da = ds[non_perage_equiv]
    da_ap = ds[perage_var]

    # Deduplex, if needed and possible
    if do_deduplex:
        n_duplexed_dims = len(suffix) / 2
        if n_duplexed_dims > 2:
            too_many_duplexed.append(var_to_print)
            continue
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
    if da.dims != da_ap_wtmean.dims:
        raise RuntimeError(f"Dimensions of da_ap_wtmean ({da_ap_wtmean.dims}) don't match those of da ({da.dims})")

    # Check weighted mean
    try:
        xr.testing.assert_allclose(da, da_ap_wtmean)
    except AssertionError as e:
        da_diff = da_ap_wtmean - da
        max_abs_diff = np.nanmax(np.abs(da_diff).values)
        max_pct_diff = 100*np.nanmax(np.abs(da_diff/da).values)
        print(f"❌ {var_to_print}:")
        print(f"     max abs diff = {max_abs_diff:.3g}")
        print(f"     max rel diff = {max_pct_diff:.1f}%")
        # da_diff.plot()
        # plt.show()
    else:
        print(f"✅ {var_to_print}")

print("\n     ".join(["\n🤷 Non-per-age equivalent not in Dataset:"] + nonperage_missing))

print("\n     ".join([f"\n🤷 Too many (> 2) duplexed dimensions:"] + too_many_duplexed))