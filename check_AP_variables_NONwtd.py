# %%
"""
Originally copied from check_AP_variables.py at commit a016a65.

That file's description: Given the run directory from a FatesColdAllVars(Monthly) test, check the last timestep to see which
per-ageclass variables have the issue where their weighted sum doesn't equal the non-per-ageclass version.

This file's description: Given the run directory from a FatesColdAllVars(Monthly) test, check the last timestep to see which
per-ageclass variables have the issue where their NON-weighted sum doesn't equal the non-per-ageclass version.
"""

# %% Setup
import glob
import os
import shutil
import re
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import subprocess
import rfh_utils

# What machine are we on?
from socket import gethostname
hostname = gethostname()
if any(x in hostname for x in ["derecho", "casper"]) or "crhtc" in hostname:
    machine = "glade"
    # Only possible because I have export PYTHONPATH=$HOME in my .bash_profile
    from ctsm_python_gallery_myfork.ctsm_py import fates_xarray_funcs as fates_utils
else:
    raise NotImplementedError(f"Hostname not recognized: {hostname}")

# Per-age variables that I added for diagnostic purposes
my_added_diagnostics = [
    "FATES_MORTALITY_A_CANOPY_SZAP",
    "FATES_MORTALITY_A_USTORY_SZAP",
    "FATES_MORTALITY_B_USTORY_SZAP",
    "FATES_MORTALITY_C_CANOPY_SZAP",
    "FATES_MORTALITY_C_USTORY_SZAP",
    "FATES_MORTALITY_D_CANOPY_SZAP",
    "FATES_MORTALITY_D_USTORY_SZAP",
]
# Non-perage variables that I added for diagnostic purposes
my_added_diagnostics_nonperage = [
    "FATES_CANOPYAREA",
    "FATES_NCL",
    "FATES_PATCHAREA",
    "FATES_SCORCH_HEIGHT_PF",
    "FATES_SECONDAREA_ANTHRODIST",
    "FATES_SECONDAREA_DIST",
    "FATES_ZSTAR",
]


# %% Import

set00 = "tests_0717-152801iz" # Pure baseline
set0 = "tests_0718-095838de"  # Before substantive changes (CTSM 8e7a1d85, FATES ff87ce15)
set1 = "tests_0718-130915de"  # _AP fixes only
set2 = "tests_0722-142229de"  # All fixes
set3 = "tests_0723-141100de"  # 103fdc9 (b4b with above)
set4 = "tests_0724-101913de"  # a0881c5 (Fix FATES_MORTALITY_CANOPY_SZAP and FATES_MORTALITY_USTORY_SZAP)
set5 = "tests_0724-125943de"  # a807670c1 (scag_denominator_area needs to be in patchloop)
set6 = "tests_0906-171030de"  # Revert my weighting changes (CTSM 6098ae6b1, FATES 91f043a7)
set7 = "tests_0911-131117de"  # Refactoring and troubleshooting (CTSM c311c24f1, FATES ed7a4e60)
set8 = "tests_1001-170645de"  # Baseline with extra outputs (CTSM a5e4aab86, FATES 60ec242a47)
set9 = "tests_1002-110327de"  # After refactoring (CTSM cc43b21db, FATES 46bcd0c9), only roundoff diffs from set8
set10 = "tests_1002-233952de"  # After fixes to bad per-ageclass vars (CTSM b6b50eb2f, FATES c8b04d41)
set11 = "tests_1003-115109de"  # Amended version of above
set12 = "tests_1003-122810de"  # Mortality fixes? (CTSM a695f62ff, FATES 7134803f)
set13 = "tests_1008-110217de"  # Mortality fixes? (CTSM 1a4f331cd16, FATES c17a4e10)
set14 = "tests_1008-131302de"  # Remove mortality component outputs (CTSM bf9386b93b, FATES fa87c89c)

# testset_dir_list = [set0, set1]
# testset_dir_list = [set1, set2]
# testset_dir_list = [set0, set3]
# testset_dir_list = [set3, set4]
# testset_dir_list = [set4, set5]
# # testset_dir_list = [set0, set5]
# testset_dir_list = [set0, set6]
# testset_dir_list = [set00, set7]
# testset_dir_list = set5
# testset_dir_list = [set8, set9]
# testset_dir_list = [set9, set10]
# testset_dir_list = [set11, set12]
# testset_dir_list = [set12, set13]
testset_dir_list = [set8, set14]

top_dir = "/glade/derecho/scratch/samrabin"
test_name = "SMS_Lm49.f10_f10_mg37.I2000Clm60Fates.derecho_intel.clm-FatesColdAllVarsMonthly"

publish_dir = "/glade/u/home/samrabin/analysis-outputs/fates-refactor-history"
url = "https://samsrabin.github.io/analysis-outputs/fates-refactor-history/"

if not isinstance(testset_dir_list, list):
    testset_dir_list = [testset_dir_list]

logfile = os.path.join(top_dir, ".".join(["NONwtd"]+ testset_dir_list + [test_name, "html"]))
if os.path.exists(logfile):
    os.remove(logfile)
print(f"Log file: {logfile}")

datasets = []
comparing_2 = len(testset_dir_list) > 1
if comparing_2 and len(testset_dir_list) > 2:
    raise RuntimeError("Max # runs to compare is 2")

with open(logfile, "a") as f:
    if comparing_2:
        msg = f"<h1>Comparing NONwtd {testset_dir_list[0]} and {testset_dir_list[1]}</h1>\n"
    else:
        msg = f"<h1>{testset_dir_list[0]}</h1>\n"
    f.write(msg)
rfh_utils.log_br(logfile, f"Test: {test_name} <br>")
with open(logfile, "a") as f:
    f.write("<b>How to read these plots</b><br>")
    f.write("This webpage compares two runs of the above test, with different code versions noted below. Figures contain one boxplot for each test. The boxplots represent the difference between a per-ageclass variable (e.g., FATES_BURNFRAC_AP)---AFTER summing across the age-class axis---and its non-per-ageclass equivalent (e.g., FATES_BURNFRAC). Each data point in the boxplots represent one member of the non-per-ageclass array in the last saved timestep of the test. So for FATES_BURNFRAC each datapoint is a gridcell, whereas for FATES_VEGC_PF each is a PFT in a gridcell.<br><br>")
    f.write("If a code version is behaving as expected, ideally all data points should be zero. In practice, because of rounding errors, this can't be achieved. Instead, we expect that the data points should be grouped more or less symmetrically around zero, with small (say, < 1e-10) absolute values.<br><br>")
    f.write("Yes, we really want the SUM across the age-class axis to match, even though in most cases what users want of the variable is each age-class's actual value. (If we were saving that, then in order to make the comparison, we would need to take the area-weighted mean across age classes.) We have this behavior because it allows for better preservation of numerical accuracy.<br><br>")


for testset_dir in testset_dir_list:
    top_testset_dir = os.path.join(top_dir, testset_dir)
    top_testset_dir = os.path.realpath(top_testset_dir)
    test_run_dir = os.path.join(top_testset_dir, test_name + "*", "run")
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

    # Get SHA
    srcroot_git_status_file = os.path.join(top_testset_dir, "SRCROOT_GIT_STATUS")
    this_commit = None
    sha = None
    pattern = re.compile("^Current hash:.*$")
    try:
        for i, line in enumerate(open(srcroot_git_status_file)):
            for match in re.finditer(pattern, line):
                this_commit = match.group()
                sha = this_commit.split(" ")[2]
        ds.attrs["this_commit"] = this_commit.replace("Current hash", "Current CTSM hash")
        ds.attrs["label"] = rfh_utils.ctsm_sha_to_fates(sha)
        with open(logfile, "a") as f:
            f.write(f"<h3>{testset_dir}</h3>\n")
        rfh_utils.log_br(logfile, ds.attrs["this_commit"])
    except FileNotFoundError:
        ds.attrs["this_commit"] = "unknown"
        ds.attrs["label"] = "unknown"
        pass
    except:
        raise


# Process

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
    if this_var == "FATES_NPATCH_AP":
        non_perage_equiv = "FATES_NPATCHES"
    else:
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
        if this_var in ["FATES_STOMATAL_COND_AP", "FATES_LBLAYER_COND_AP"]:
            dict_perage_to_non_equiv[this_var]["weights"] = "FATES_CANOPYAREA_AP"
        else:
            dict_perage_to_non_equiv[this_var]["weights"] = "FATES_PATCHAREA_AP"
    else:
        dict_perage_to_non_equiv[this_var] = {
            "non_perage_equiv": None,
        }

# Analyze
nonperage_missing = []
too_many_duplexed = []
weights_var_missing = []
for perage_var in dict_perage_to_non_equiv.keys():
    non_perage_equiv, suffix, this_dict, do_deduplex, var_to_print = rfh_utils.get_variable_info(
        dict_perage_to_non_equiv, perage_var
    )

    if non_perage_equiv is None:
        nonperage_missing.append(var_to_print)
        continue

    # Get age weights
    weightvar = this_dict["weights"]
    if weightvar not in datasets[0]:
        print(f"{perage_var}'s weighting variable ({weightvar}) missing; will skip")
        weights_var_missing.append(f"{var_to_print} (weights: {weightvar})")
        continue

    for i, ds in enumerate(datasets):
        # Get DataArrays to work with
        da = ds[non_perage_equiv]
        da_ap = ds[perage_var]
        weights = ds[weightvar]
        if weightvar == "FATES_CANOPYAREA_AP" and testset_dir_list[i] not in ["tests_0717-152801iz", "tests_0718-095838de"]:
            # Starting with FATES commit 5942a0d (first included in CTSM commit a6ccdf3ec), the
            # denominator of FATES_CANOPYAREA_AP is age-class area instead of site area. That's
            # fine for FATES_CANOPYAREA_AP per se, but it means that when you use it as a weight,
            # you need to multiply it by FATES_PATCHAREA_AP.
            weights *= ds["FATES_PATCHAREA_AP"]
        weights = weights.fillna(0)

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
            elif suffix == "SZAPPF":
                raise RuntimeError("This requires more testing")
                da_ap = fates_utils.scappf_to_scls_by_age_by_pft(perage_var, ds)
            else:
                raise NotImplementedError(f"Unrecognized suffix: _{suffix}")

        # Get unweighted sum
        da_ap_sum = da_ap.sum(dim="fates_levage")
        if suffix == "SZAPPF":
            raise RuntimeError("This requires more testing")
            da_ap_sum = da_ap_sum.stack(fates_levscpf=("fates_levscls", "fates_levpft"))
            da_ap_sum = da_ap_sum.transpose('fates_levscpf', 'lat', 'lon')
        if da.dims != da_ap_sum.dims:
            raise RuntimeError(
                f"Dimensions of da_ap_sum ({da_ap_sum.dims}) don't match those of da ({da.dims})"
            )

        # Test
        this_dict = rfh_utils.compare_results(this_dict, da, da_ap_sum)

    if too_many_duplexed and too_many_duplexed[-1] == var_to_print:
        continue

    rfh_utils.add_result_text(my_added_diagnostics, my_added_diagnostics_nonperage, logfile, comparing_2, non_perage_equiv, perage_var, this_dict, var_to_print)

    # Make boxplots
    rfh_utils.make_boxplots(logfile, datasets, perage_var, this_dict, var_to_print)

    dict_perage_to_non_equiv[perage_var] = this_dict

# Finish up
rfh_utils.add_end_text(logfile, nonperage_missing, too_many_duplexed, weights_var_missing)
rfh_utils.publish(publish_dir, url, logfile)
