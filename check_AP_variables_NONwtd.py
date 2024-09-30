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

# What machine are we on?
from socket import gethostname
hostname = gethostname()
if any(x in hostname for x in ["derecho", "casper"]) or "crhtc" in hostname:
    machine = "glade"
    # Only possible because I have export PYTHONPATH=$HOME in my .bash_profile
    from ctsm_python_gallery_myfork.ctsm_py import fates_xarray_funcs as fates_utils
else:
    raise NotImplementedError(f"Hostname not recognized: {hostname}")

# Non-perage variables that I added to diagnostic purposes
my_added_diagnostics = [
    "FATES_CANOPYAREA",
    "FATES_NCL",
    "FATES_PATCHAREA",
    "FATES_SCORCH_HEIGHT_PF",
    "FATES_SECONDAREA_ANTHRODIST",
    "FATES_SECONDAREA_DIST",
    "FATES_ZSTAR"
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

# testset_dir_list = [set0, set1]
# testset_dir_list = [set1, set2]
# testset_dir_list = [set0, set3]
# testset_dir_list = [set3, set4]
# testset_dir_list = [set4, set5]
# testset_dir_list = [set0, set5]
testset_dir_list = [set0, set6]
testset_dir_list = [set00, set7]
# testset_dir_list = set5

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
def log_br(logfile, msg):
    if "img src" not in msg:
        print(msg.replace("<p>", ""))

    msg += "<br>\n"
    with open(logfile, "a") as f:
        f.write(msg)

def log_ul(logfile, title, items):
    if not items:
        return

    print("\n     ".join([f"\n{title}"] + items))

    with open(logfile, "a") as f:
        f.write("<p>\n")
        f.write(f"{title}:<br>\n")
        f.write("<ul>\n")
        for i in items:
            f.write(f"<li>{i}</li>\n")
        f.write("</ul>\n")

def log_plot(logfile, log_br):
    # Convert plot to base64 string
    buf = BytesIO()
    plt.gcf().savefig(buf, format='png')
    buf.seek(0)
    plot_data = base64.b64encode(buf.read()).decode('utf8')
    plt.close()

    # Embed plot in HTML log message
    plot_html = '<p><img src="data:image/png;base64,{}">'.format(plot_data)
    log_br(logfile, plot_html)
    buf.close()

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
log_br(logfile, f"Test: {test_name} <br>")

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
        ds.attrs["label"] = ctsm_sha_to_fates(sha)
        with open(logfile, "a") as f:
            f.write(f"<h3>{testset_dir}</h3>\n")
        log_br(logfile, ds.attrs["this_commit"])
    except:
        ds.attrs["this_commit"] = "unknown"
        ds.attrs["label"] = "unknown"
        pass


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
            else:
                raise NotImplementedError(f"Unrecognized suffix: _{suffix}")

        # Get unweighted sum
        da_ap_sum = da_ap.sum(dim="fates_levage")

        # Get weighted mean
        # CURRENTLY UNUSED
        da_ap_wtmean = da_ap.weighted(weights).mean(dim="fates_levage")
        np.all(np.isclose(da, da_ap.mean(dim="fates_levage"), equal_nan=True))
        if da.dims != da_ap_wtmean.dims:
            raise RuntimeError(f"Dimensions of da_ap_wtmean ({da_ap_wtmean.dims}) don't match those of da ({da.dims})")

        # Test
        is_close = np.all(np.isclose(da, da_ap_sum, equal_nan=True))
        this_dict["isclose"].append(is_close)
        this_dict["isclose_emoji"].append("✅" if is_close else "❌")
        this_dict["isclose_glyph"].append("✓" if is_close else "X")
        da_diff = da_ap_sum - da
        this_dict["da_diffs"].append(da_diff)
        this_dict["max_abs_diff"].append(np.nanmax(np.abs(da_diff).values))
        this_dict["max_pct_diff"].append(100*np.nanmax(np.abs(da_diff/da).values))

    if too_many_duplexed and too_many_duplexed[-1] == var_to_print:
        continue

    emojis = " → ".join(this_dict["isclose_emoji"])

    with open(logfile, "a") as f:
        f.write("<hr>\n")
        f.write(f"<h2>{emojis} {var_to_print}</h2>\n")
    print(f"{emojis} {var_to_print}:")

    # Note non-perage variables that I added for diagnostic purposes
    if non_perage_equiv in my_added_diagnostics:
        log_br(logfile, "NOTE: Added by Sam Rabin for diagnostic purposes")

    max_abs_diff = this_dict["max_abs_diff"]
    max_pct_diff = this_dict["max_pct_diff"]
    if not comparing_2 or (max_abs_diff[0] == max_abs_diff[1] and max_pct_diff[0] == max_pct_diff[1]):
        log_br(logfile, f"     max abs diff = {max_abs_diff[0]:.3g}")
        log_br(logfile, f"     max rel diff = {max_pct_diff[0]:.1f}%")
    else:
        log_br(logfile, f"     max abs diff = {max_abs_diff[0]:.3g} → {max_abs_diff[1]:.3g}")
        log_br(logfile, f"     max rel diff = {max_pct_diff[0]:.1f}% → {max_pct_diff[1]:.1f}%")

    # Make boxplots
    boxdatas = []
    labels = []
    for i, da_diff in enumerate(this_dict["da_diffs"]):
        boxdata = da_diff.values[np.where(np.abs(da_diff) > 0)]
        boxdatas.append(boxdata)
        label = datasets[i].attrs["label"]
        if label is None:
            if i==0:
                label = "before"
            elif i==1:
                label = "after"
            else:
                label = str(i)
        emoji = this_dict["isclose_glyph"][i]
        labels.append(f"{label} {emoji}")
    try:
        plt.boxplot(boxdatas, tick_labels=labels)
    except:
        plt.boxplot(boxdatas, labels=labels)
    plt.ylabel(f"discrepancy ({datasets[0][perage_var].attrs['units']})")
    plt.title(var_to_print)
    log_plot(logfile, log_br)

    dict_perage_to_non_equiv[perage_var] = this_dict

with open(logfile, "a") as f:
    f.write("<hr>\n")
    f.write("<h2>Other</h2>\n")
log_ul(logfile, "🤷 Non-per-age equivalent not in Dataset", nonperage_missing)
log_ul(logfile, "🤷 Too many (> 2) duplexed dimensions", too_many_duplexed)
log_ul(logfile, "🤷 Weights variable missing", weights_var_missing)


# Publish

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

# Ensure publishing dir is clean
status = run_git_cmd(f"git -C {publish_dir} status")
if status[-1] != "nothing to commit, working tree clean":
    raise RuntimeError(f"publish_dir not clean: {publish_dir}")

# Copy to publishing directory
destfile = os.path.join(publish_dir, os.path.basename(logfile))
shutil.copyfile(logfile, destfile)

status = run_git_cmd(f"git -C {publish_dir} status")
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
        elif l != '  (use "git add <file>..." to include in what will be committed)':
            new_files.append(l.replace('\t', ''))
if modified_files:
    print("Updating files:\n   " + "\n   ".join(modified_files))
if new_files:
    print("Adding files:\n   " + "\n   ".join(new_files))

# Commit
status = run_git_cmd(f"git -C {publish_dir} status")
if status[-1] != "nothing to commit, working tree clean":
    # Stage
    print("Staging...")
    cmd = f"git -C {publish_dir} add {os.path.join(publish_dir, '*')}"
    status = run_git_cmd(cmd)

    # Commit
    print("Committing...")
    cmd = f"git -C {publish_dir} commit -m Update"
    status = run_git_cmd(cmd)

    # Push
    print("Pushing...")
    cmd = f"git -C {publish_dir} push"
    status = run_git_cmd(cmd)

    print("Done! Published to:")
    for f in modified_files + new_files:
        file_url = url + os.path.basename(f)
        print("   " + file_url)
else:
    print("Nothing to commit")
