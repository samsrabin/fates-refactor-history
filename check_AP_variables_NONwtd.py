# %%
"""
Given the run directory from a FatesColdAllVars(Monthly) test, check the last timestep to see which
per-ageclass variables have the issue where their NON-weighted sum doesn't equal the
non-per-ageclass version.
"""
# pylint: disable=invalid-name
# pylint: disable=fixme

# %% Setup
import os
import re
import rfh_utils

# E.g.:
#    set8 = "tests_1001-170645de"
#    set14 = "tests_1008-131302de"
#    testset_dir_list = [set8, set14]
from test_sets import testset_dir_list


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

top_dir = "/glade/derecho/scratch/samrabin"
test_name = (
    "SMS_Lm49.f10_f10_mg37.I2000Clm60Fates.derecho_intel.clm-FatesColdAllVarsMonthly"
)

publish_dir = "/glade/u/home/samrabin/analysis-outputs/fates-refactor-history"
url = "https://samsrabin.github.io/analysis-outputs/fates-refactor-history/"

if not isinstance(testset_dir_list, list):
    testset_dir_list = [testset_dir_list]

logfile = os.path.join(
    top_dir, ".".join(["NONwtd"] + testset_dir_list + [test_name, "html"])
)
if os.path.exists(logfile):
    os.remove(logfile)
print(f"Log file: {logfile}")

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
    # pylint: disable=line-too-long
    f.write("<b>How to read these plots</b><br>")
    f.write(
        "This webpage compares two runs of the above test, with different code versions noted below. Figures contain one boxplot for each test. The boxplots represent the difference between a per-ageclass variable (e.g., FATES_BURNFRAC_AP)---AFTER summing across the age-class axis---and its non-per-ageclass equivalent (e.g., FATES_BURNFRAC). Each data point in the boxplots represent one member of the non-per-ageclass array in the last saved timestep of the test. So for FATES_BURNFRAC each datapoint is a gridcell, whereas for FATES_VEGC_PF each is a PFT in a gridcell.<br><br>"
    )
    f.write(
        "If a code version is behaving as expected, ideally all data points should be zero. In practice, because of rounding errors, this can't be achieved. Instead, we expect that the data points should be grouped more or less symmetrically around zero, with small (say, < 1e-10) absolute values.<br><br>"
    )
    f.write(
        "Yes, we really want the SUM across the age-class axis to match, even though in most cases what users want of the variable is each age-class's actual value. (If we were saving that, then in order to make the comparison, we would need to take the area-weighted mean across age classes.) We have this behavior because it allows for better preservation of numerical accuracy.<br><br>"
    )


datasets = rfh_utils.get_datasets(testset_dir_list, top_dir, test_name, logfile)


# Process

# Get per-ageclass variables and their equivalents
pattern = "FATES_[A-Z_]+_[A-Z]*AP[A-Z]*"
p = re.compile(pattern)
dict_perage_to_non_equiv = {}
ds = datasets[-1]
var_list = list(ds.variables)
# TODO: Add comparison of datasets' variable lists
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
        if weightvar == "FATES_CANOPYAREA_AP" and testset_dir_list[i] not in [
            "tests_0717-152801iz",
            "tests_0718-095838de",
        ]:
            # Starting with FATES commit 5942a0d (first included in CTSM commit a6ccdf3ec), the
            # denominator of FATES_CANOPYAREA_AP is age-class area instead of site area. That's
            # fine for FATES_CANOPYAREA_AP per se, but it means that when you use it as a weight,
            # you need to multiply it by FATES_PATCHAREA_AP.
            weights *= ds["FATES_PATCHAREA_AP"]
        weights = weights.fillna(0)

        # Deduplex, if needed and possible
        if do_deduplex:
            da_ap, too_many_duplexed = rfh_utils.deduplex(
                ds, suffix, too_many_duplexed, perage_var, var_to_print
            )
            if var_to_print in too_many_duplexed:
                break

        # Get unweighted sum
        da_ap_sum = da_ap.sum(dim="fates_levage")
        if suffix == "SZAPPF":
            raise RuntimeError("This requires more testing")
            # pylint: disable=unreachable
            da_ap_sum = da_ap_sum.stack(fates_levscpf=("fates_levscls", "fates_levpft"))
            da_ap_sum = da_ap_sum.transpose("fates_levscpf", "lat", "lon")
        if da.dims != da_ap_sum.dims:
            raise RuntimeError(
                f"Dimensions of da_ap_sum ({da_ap_sum.dims}) don't match those of da ({da.dims})"
            )

        # Test
        this_dict = rfh_utils.compare_results(this_dict, da, da_ap_sum)

    if too_many_duplexed and too_many_duplexed[-1] == var_to_print:
        continue

    rfh_utils.add_result_text(
        my_added_diagnostics,
        my_added_diagnostics_nonperage,
        logfile,
        comparing_2,
        non_perage_equiv,
        perage_var,
        this_dict,
        var_to_print,
    )

    # Make boxplots
    rfh_utils.make_boxplots(logfile, datasets, perage_var, this_dict, var_to_print)

    dict_perage_to_non_equiv[perage_var] = this_dict

# Finish up
rfh_utils.add_end_text(
    logfile, nonperage_missing, too_many_duplexed, weights_var_missing
)
rfh_utils.publish(publish_dir, url, logfile)
