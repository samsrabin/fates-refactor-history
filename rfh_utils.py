"""
Useful functions for this module
"""
# pylint: disable=invalid-name
# pylint: disable=missing-function-docstring
# pylint: disable=too-many-arguments
# pylint: disable=fixme

import glob
import os
import shutil
import re
import base64
from io import BytesIO
from socket import gethostname
import subprocess
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

# E.g.:
#    TEST_NAME = (
#        "SMS_Lm49.f10_f10_mg37.I2000Clm60Fates.derecho_intel.clm-FatesColdAllVarsMonthly"
#    )
#    PUBLISH_DIR = "/glade/u/home/samrabin/analysis-outputs/fates-refactor-history"
#    PUBLISH_URL = "https://samsrabin.github.io/analysis-outputs/fates-refactor-history/"
#    THISREPO_URL = "https://github.com/samsrabin/fates-refactor-history"
#    set8 = "/glade/derecho/scratch/samrabin/tests_1001-170645de"
#    set14 = "/glade/derecho/scratch/samrabin/tests_1008-131302de"
#    TESTSET_DIR_LIST = [set8, set14]
from options import PUBLISH_DIR, PUBLISH_URL, TEST_NAME, THISREPO_URL, TESTSET_DIR_LIST

# What machine are we on?
hostname = gethostname()
if any(x in hostname for x in ["derecho", "casper"]) or "crhtc" in hostname:
    machine = "glade"
    # Only possible because I have export PYTHONPATH=$HOME in my .bash_profile
    from ctsm_python_gallery_myfork.ctsm_py import fates_xarray_funcs as fates_utils
else:
    raise NotImplementedError(f"Hostname not recognized: {hostname}")

# Per-age variables that I added for diagnostic purposes
MY_ADDED_DIAGNOSTICS = [
    "FATES_MORTALITY_A_CANOPY_SZAP",
    "FATES_MORTALITY_A_USTORY_SZAP",
    "FATES_MORTALITY_B_USTORY_SZAP",
    "FATES_MORTALITY_C_CANOPY_SZAP",
    "FATES_MORTALITY_C_USTORY_SZAP",
    "FATES_MORTALITY_D_CANOPY_SZAP",
    "FATES_MORTALITY_D_USTORY_SZAP",
]
# Non-perage variables that I added for diagnostic purposes
MY_ADDED_DIAGNOSTICS_NONPERAGE = [
    "FATES_CANOPYAREA",
    "FATES_NCL",
    "FATES_PATCHAREA",
    "FATES_SCORCH_HEIGHT_PF",
    "FATES_SECONDAREA_ANTHRODIST",
    "FATES_SECONDAREA_DIST",
    "FATES_ZSTAR",
]

if not isinstance(TESTSET_DIR_LIST, list):
    TESTSET_DIR_LIST = [TESTSET_DIR_LIST]
TESTSET_DIR_BASENAME_LIST = [os.path.basename(x) for x in TESTSET_DIR_LIST]

LOGFILE = os.path.join(
    PUBLISH_DIR, ".".join(["NONwtd"] + TESTSET_DIR_BASENAME_LIST + [TEST_NAME, "html.tmp"])
)
if os.path.exists(LOGFILE):
    os.remove(LOGFILE)
print(f"Log file: {LOGFILE}")

N_TESTS = len(TESTSET_DIR_LIST)
COMPARING_2 = N_TESTS > 1
if COMPARING_2 and N_TESTS > 2:
    raise RuntimeError("Max # runs to compare is 2")


def log_br(msg):
    if "img src" not in msg:
        print(msg.replace("<p>", ""))

    msg += "<br>\n"
    with open(LOGFILE, "a") as f:
        f.write(msg)


def log_ul(title, items):
    if not items:
        return

    print("\n     ".join([f"\n{title}"] + items))

    with open(LOGFILE, "a") as f:
        f.write("<p>\n")
        f.write(f"{title}:<br>\n")
        f.write("<ul>\n")
        for i in items:
            f.write(f"<li>{i}</li>\n")
        f.write("</ul>\n")


def log_plot():
    # Convert plot to base64 string
    buf = BytesIO()
    plt.gcf().savefig(buf, format="png")
    buf.seek(0)
    plot_data = base64.b64encode(buf.read()).decode("utf8")
    plt.close()

    # Embed plot in HTML log message
    plot_html = '<p><img src="data:image/png;base64,{}">'.format(plot_data)
    log_br(plot_html)
    buf.close()


def ctsm_sha_to_fates(ctsm_sha):
    if ctsm_sha == "8e7a1d85f":
        sha = "fates-ff87ce15"
    elif ctsm_sha == "a6ccdf3ec":
        sha = "fates-66cc4f81"
    elif ctsm_sha == "7680fc6e8":
        sha = "fates-1ec6d6eb"
    elif ctsm_sha == "41a4cb47b":
        sha = "fates-103fdc96"
    elif ctsm_sha == "fe9ed7376":
        sha = "fates-a0881c536"
    elif ctsm_sha == "a807670c1":
        sha = "fates-f21fa95b"
    else:
        print(f"Unable to get FATES SHA for CTSM SHA {ctsm_sha}")
        sha = "ctsm-" + ctsm_sha
    return sha


def make_boxplots(datasets, perage_var, this_dict, var_to_print):
    boxdatas = []
    labels = []
    for i, boxdata in enumerate(this_dict["boxdata"]):
        boxdatas.append(boxdata)
        label = datasets[i].attrs["label"]
        if label is None:
            if i == 0:
                label = "before"
            elif i == 1:
                label = "after"
            else:
                label = str(i)
        emoji = this_dict["isclose_glyph"][i]
        labels.append(f"{label} {emoji}")
    try:
        # pylint: disable=unexpected-keyword-arg
        plt.boxplot(
            boxdatas, tick_labels=labels
        )
    except TypeError:
        plt.boxplot(boxdatas, labels=labels)
    except:  # pylint: disable=try-except-raise
        raise
    plt.ylabel(f"discrepancy ({datasets[0][perage_var].attrs['units']})")
    plt.title(var_to_print)
    log_plot()


def compare_results(this_dict, da, da_ap_sum):
    da_diff = da_ap_sum - da
    this_dict["da_diffs"].append(da_diff)
    max_abs_diff = np.nanmax(np.abs(da_diff).values)
    this_dict["max_abs_diff"].append(max_abs_diff)
    max_rel_diff = 100 * np.nanmax(np.abs(da_diff / da).values)
    this_dict["max_pct_diff"].append(max_rel_diff)

    is_close = max_abs_diff < 1e-9 and (max_rel_diff < 1e-6 or np.isnan(max_rel_diff))
    this_dict["isclose"].append(is_close)
    this_dict["isclose_emoji"].append("✅" if is_close else "❌")
    this_dict["isclose_glyph"].append("✓" if is_close else "X")

    this_dict["boxdata"].append(da_diff.values[np.where(np.abs(da_diff) >= 0)])
    return this_dict


def add_result_text(
    non_perage_equiv,
    perage_var,
    this_dict,
    var_to_print,
):
    emojis = " → ".join(this_dict["isclose_emoji"])

    with open(LOGFILE, "a") as f:
        f.write("<hr>\n")
        f.write(f"<h2>{emojis} {var_to_print}</h2>\n")
    print(f"{emojis} {var_to_print}:")

    # Note variables that I added for diagnostic purposes
    if perage_var in MY_ADDED_DIAGNOSTICS:
        log_br("NOTE: Added by Sam Rabin for diagnostic purposes")
    if non_perage_equiv in MY_ADDED_DIAGNOSTICS_NONPERAGE:
        log_br(
            "NOTE: Non-per-age version added by Sam Rabin for diagnostic purposes",
        )

    max_abs_diff = this_dict["max_abs_diff"]
    max_pct_diff = this_dict["max_pct_diff"]
    if not COMPARING_2 or (
        max_abs_diff[0] == max_abs_diff[1] and max_pct_diff[0] == max_pct_diff[1]
    ):
        log_br(f"     max abs diff = {max_abs_diff[0]:.3g}")
        log_br(f"     max rel diff = {max_pct_diff[0]:.1f}%")
    else:
        log_br(
            f"     max abs diff = {max_abs_diff[0]:.3g} → {max_abs_diff[1]:.3g}",
        )
        log_br(
            f"     max rel diff = {max_pct_diff[0]:.1f}% → {max_pct_diff[1]:.1f}%",
        )


def get_variable_info(dict_perage_to_non_equiv, perage_var):
    this_dict = dict_perage_to_non_equiv[perage_var]
    non_perage_equiv = this_dict["non_perage_equiv"]

    # Will de-duplexing be needed?
    suffix = perage_var.split("_")[-1]
    do_deduplex = len(suffix) > 2
    if do_deduplex:
        var_to_print = perage_var.replace("AP", "(AP)")
    else:
        var_to_print = perage_var.replace("_AP", "(_AP)")
    return non_perage_equiv, suffix, this_dict, do_deduplex, var_to_print


def add_end_text(
    nonperage_missing,
    too_many_duplexed,
    missing_var_lists,
    all_nan,
    no_boxdata,
):
    with open(LOGFILE, "a") as f:
        f.write("<hr>\n")
        f.write("<h2>Other</h2>\n")
    log_ul("🤷 Non-per-age equivalent not in Dataset", nonperage_missing)
    log_ul("🤷 Too many (> 2) duplexed dimensions", too_many_duplexed)
    log_ul("🤷 All data NaN", all_nan)
    log_ul("🤷 No included data", no_boxdata)
    for i, missing_var_list in enumerate(missing_var_lists):
        if missing_var_list:
            missing_var_list.sort()
            n_ds = len(missing_var_lists)
            log_ul(f"🤷 Missing from Dataset {i+1}/{n_ds}", missing_var_list)


def run_git_cmd(cmd):
    try:
        result = subprocess.check_output(
            cmd.split(" "),
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        ).splitlines()
    except subprocess.CalledProcessError as e:
        print("Command: " + " ".join(e.cmd))
        print("Message: ", e.stdout)
        raise e
    return result


def publish():
    # Ensure publishing dir is clean
    status = run_git_cmd(f"git -C {PUBLISH_DIR} status")
    if status[-1] != "nothing to commit, working tree clean":
        raise RuntimeError(f"PUBLISH_DIR not clean: {PUBLISH_DIR}")

    # Rename log file
    destfile = os.path.join(PUBLISH_DIR, os.path.basename(LOGFILE).replace("html.tmp", "html"))
    shutil.move(LOGFILE, destfile)

    status = run_git_cmd(f"git -C {PUBLISH_DIR} status")
    modified_files = []
    new_files = []
    in_untracked_files = False
    for l in status:
        if not in_untracked_files:
            if re.compile("^\tmodified:").match(l):
                modified_files.append(l.split(" ")[-1])
            elif l == "Untracked files:":
                in_untracked_files = True
        else:
            if l == "":
                break
            if l != '  (use "git add <file>..." to include in what will be committed)':
                new_files.append(l.replace("\t", ""))
    if modified_files:
        print("Updating files:\n   " + "\n   ".join(modified_files))
    if new_files:
        print("Adding files:\n   " + "\n   ".join(new_files))

    commit(modified_files, new_files)


def commit(modified_files, new_files):
    status = run_git_cmd(f"git -C {PUBLISH_DIR} status")
    if status[-1] != "nothing to commit, working tree clean":
        # Stage
        print("Staging...")
        cmd = f"git -C {PUBLISH_DIR} add {os.path.join(PUBLISH_DIR, '*')}"
        status = run_git_cmd(cmd)

        # Commit
        print("Committing...")
        cmd = f"git -C {PUBLISH_DIR} commit -m Update"
        status = run_git_cmd(cmd)

        # Push
        print("Pushing...")
        cmd = f"git -C {PUBLISH_DIR} push"
        status = run_git_cmd(cmd)

        print("Done! Published to:")
        for f in modified_files + new_files:
            file_url = PUBLISH_URL + os.path.basename(f)
            print("   " + file_url)
    else:
        print("Nothing to commit")


def deduplex(ds, suffix, too_many_duplexed, perage_var, var_to_print):
    n_duplexed_dims = len(suffix) / 2
    if n_duplexed_dims > 2:
        too_many_duplexed.append(var_to_print)
        return None, too_many_duplexed
    if suffix == "APFC":
        da_ap = fates_utils.agefuel_to_age_by_fuel(perage_var, ds)
    elif suffix == "APPF":
        da_ap = fates_utils.deduplex(ds, perage_var, "age", "pft")
    elif suffix == "SZAP":
        da_ap = fates_utils.deduplex(ds, perage_var, "scls", "age")
    elif suffix == "SZAPPF":
        raise RuntimeError("This requires more testing")
        # pylint: disable=unreachable
        da_ap = fates_utils.scappf_to_scls_by_age_by_pft(perage_var, ds)
    else:
        raise NotImplementedError(f"Unrecognized suffix: _{suffix}")
    return da_ap, too_many_duplexed


def get_sha(testset_dir, top_testset_dir, ds):
    srcroot_git_status_file = os.path.join(top_testset_dir, "SRCROOT_GIT_STATUS")
    this_commit = None
    sha = None
    pattern = re.compile("^Current hash:.*$")
    try:
        for line in open(srcroot_git_status_file):
            for match in re.finditer(pattern, line):
                this_commit = match.group()
                sha = this_commit.split(" ")[2]
        ds.attrs["this_commit"] = this_commit.replace(
            "Current hash", "Current CTSM hash"
        )
        ds.attrs["label"] = ctsm_sha_to_fates(sha)
        with open(LOGFILE, "a") as f:
            f.write(f"<h3>{testset_dir}</h3>\n")
        log_br(ds.attrs["this_commit"])
    except FileNotFoundError:
        ds.attrs["this_commit"] = "unknown"
        ds.attrs["label"] = "unknown"
    except:  # pylint: disable=try-except-raise
        raise
    return ds


def get_datasets():
    datasets = []
    for i, testset_dir in enumerate(TESTSET_DIR_BASENAME_LIST):
        top_testset_dir = TESTSET_DIR_LIST[i]
        top_testset_dir = os.path.realpath(top_testset_dir)
        test_run_dir = os.path.join(top_testset_dir, TEST_NAME + "*", "run")
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

        # Get SHA
        ds = get_sha(testset_dir, top_testset_dir, ds)

        datasets.append(ds)
    return datasets


# Get per-ageclass variables and their equivalents
def get_dict_perage_to_non_equiv(datasets):
    pattern = "FATES_[A-Z_]+_[A-Z]*AP[A-Z]*"
    p = re.compile(pattern)
    dict_perage_to_non_equiv = {}

    # Get variables missing from each dataset
    all_vars = []
    for ds in datasets:
        all_vars += list(ds.variables)
    unique_vars = np.unique(all_vars)
    missing_var_lists = []
    for ds in datasets:
        missing_var_lists.append([v for v in unique_vars if v not in ds])

    # Loop through variables present on both datasets
    var_list = [v for v in datasets[0] if v in datasets[1]]
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
        if all(non_perage_equiv in ds for ds in datasets):
            dict_perage_to_non_equiv[this_var] = {
                "non_perage_equiv": non_perage_equiv,
                "isclose": [],
                "isclose_emoji": [],
                "isclose_glyph": [],
                "max_abs_diff": [],
                "max_pct_diff": [],
                "da_diffs": [],
                "boxdata": [],
            }
            if this_var in ["FATES_STOMATAL_COND_AP", "FATES_LBLAYER_COND_AP"]:
                dict_perage_to_non_equiv[this_var]["weights"] = "FATES_CANOPYAREA_AP"
            else:
                dict_perage_to_non_equiv[this_var]["weights"] = "FATES_PATCHAREA_AP"
        else:
            dict_perage_to_non_equiv[this_var] = {
                "non_perage_equiv": None,
            }

    return dict_perage_to_non_equiv, missing_var_lists


def get_unweighted_sum(suffix, da, da_ap):
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

    return da_ap_sum


def write_front_matter():
    with open(LOGFILE, "a") as f:
        if COMPARING_2:
            msg = f"<h1>Comparing NONwtd {TESTSET_DIR_BASENAME_LIST[0]} and {TESTSET_DIR_BASENAME_LIST[1]}</h1>\n"
        else:
            msg = f"<h1>{TESTSET_DIR_BASENAME_LIST[0]}</h1>\n"
        f.write(msg)
    log_br(f"Test: {TEST_NAME} <br>")
    with open(LOGFILE, "a") as f:
        # pylint: disable=line-too-long
        f.write("<b>How to read these plots</b><br>")
        f.write(
            "This webpage compares two runs of the above test, with different code versions noted below. Figures contain one boxplot for each test. The boxplots represent the difference between a per-ageclass variable (e.g., FATES_BURNFRAC_AP)---AFTER summing across the age-class axis---and its non-per-ageclass equivalent (e.g., FATES_BURNFRAC). Each data point in the boxplots represent one member of the non-per-ageclass array in the last saved timestep of the test. So for FATES_BURNFRAC each datapoint is a gridcell, whereas for FATES_VEGC_PF each is a PFT in a gridcell.<br><br>"
        )
        f.write(
            "If a code version is behaving as expected, ideally all data points should be zero. In practice, because of rounding errors, this can't usually be achieved. Instead, we expect that the data points should be grouped more or less symmetrically around zero, with small absolute and relative differences. Here, ✅ indicates boxplots with all absolute values of absolute differences < 1e-9 and relative differences < 1e-8. Boxplots that do not meet those criteria are marked with ❌.<br><br>"
        )
        f.write(
            "Yes, we really want the SUM across the age-class axis to match, even though in most cases what users want of the variable is each age-class's actual value. (If we were saving that, then in order to make the comparison, we would need to take the area-weighted mean across age classes.) We have this behavior because it allows for better preservation of numerical accuracy.<br><br>"
        )
        thisrepo_link = f'<a href="{THISREPO_URL}">this repo</a>.'
        f.write(
            "This analysis was performed (and this webpage was published) using the code in " +
            thisrepo_link
        )
