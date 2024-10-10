"""
Useful functions for this module
"""
# pylint: disable=invalid-name
# pylint: disable=missing-function-docstring
# pylint: disable=too-many-arguments
# pylint: disable=fixme

import glob
import os
import re
from socket import gethostname
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from options import PUBLISH_DIR, TEST_NAME, TESTSET_DIR_LIST
from rfh_git import Rfh_Git
from rfh_write import Rfh_Write

THISREPO_URL = "https://github.com/samsrabin/fates-refactor-history"
PUBLISH_DIR = os.path.realpath(PUBLISH_DIR)

# What machine are we on?
hostname = gethostname()
if any(x in hostname for x in ["derecho", "casper"]) or "crhtc" in hostname:
    machine = "glade"
    # Only possible because I have export PYTHONPATH=$HOME in my .bash_profile
    from ctsm_python_gallery_myfork.ctsm_py import fates_xarray_funcs as fates_utils
else:
    raise NotImplementedError(f"Hostname not recognized: {hostname}")

if not isinstance(TESTSET_DIR_LIST, list):
    TESTSET_DIR_LIST = [TESTSET_DIR_LIST]
TESTSET_DIR_BASENAME_LIST = [os.path.basename(x) for x in TESTSET_DIR_LIST]

LOGFILE = os.path.join(
    PUBLISH_DIR,
    ".".join(["NONwtd"] + TESTSET_DIR_BASENAME_LIST + [TEST_NAME, "html.tmp"]),
)
if os.path.exists(LOGFILE):
    os.remove(LOGFILE)
print(f"Log file: {LOGFILE}")

N_TESTS = len(TESTSET_DIR_LIST)
COMPARING_2 = N_TESTS > 1
if COMPARING_2 and N_TESTS > 2:
    raise RuntimeError("Max # runs to compare is 2")

git = Rfh_Git(PUBLISH_DIR, LOGFILE)
write = Rfh_Write(LOGFILE, TESTSET_DIR_BASENAME_LIST, THISREPO_URL)
write.write_front_matter(TEST_NAME, COMPARING_2)


def ctsm_sha_to_fates(ctsm_sha, srcroot_git_status_file):
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
        sha = fates_sha_from_git_status_file(ctsm_sha, srcroot_git_status_file)
    return sha


def fates_sha_from_git_status_file(ctsm_sha, srcroot_git_status_file):
    try:
        pattern = re.compile(".*    fates .*")
        match = None
        for line in open(srcroot_git_status_file):
            matches = pattern.match(line)
            if matches:
                match = matches[0]
                break
        if match is None:
            raise EOFError(f"FATES line not found in {srcroot_git_status_file}")
        if "is out of sync with .gitmodules" in match:
            x = 3
        else:
            x = -1
        sha = re.split(r"\s+", match)[x]
        if len(sha) > 8:
            sha = sha[:8]
        sha = "fates-" + sha
    except (FileNotFoundError, EOFError):
        print(f"Unable to get FATES SHA for CTSM SHA {ctsm_sha}")
        sha = "ctsm-" + ctsm_sha
    except:  # pylint: disable=try-except-raise
        raise
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
        plt.boxplot(boxdatas, tick_labels=labels)
    except TypeError:
        plt.boxplot(boxdatas, labels=labels)
    except:  # pylint: disable=try-except-raise
        raise
    plt.ylabel(f"discrepancy ({datasets[0][perage_var].attrs['units']})")
    plt.title(var_to_print)
    write.log_plot()


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
    write.add_result_text(
        non_perage_equiv,
        perage_var,
        this_dict,
        var_to_print,
        COMPARING_2,
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
    write.add_end_text(
        nonperage_missing,
        too_many_duplexed,
        missing_var_lists,
        all_nan,
        no_boxdata,
        )


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
        ds.attrs["label"] = ctsm_sha_to_fates(sha, srcroot_git_status_file)
        with open(LOGFILE, "a") as f:
            f.write(f"<h3>{testset_dir}</h3>\n")
        write.log_br(ds.attrs["this_commit"])
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


def publish():
    git.publish()
