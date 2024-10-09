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
    plt.gcf().savefig(buf, format="png")
    buf.seek(0)
    plot_data = base64.b64encode(buf.read()).decode("utf8")
    plt.close()

    # Embed plot in HTML log message
    plot_html = '<p><img src="data:image/png;base64,{}">'.format(plot_data)
    log_br(logfile, plot_html)
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


def make_boxplots(logfile, datasets, perage_var, this_dict, var_to_print):
    boxdatas = []
    labels = []
    for i, da_diff in enumerate(this_dict["da_diffs"]):
        boxdata = da_diff.values[np.where(np.abs(da_diff) > 0)]
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
        plt.boxplot(boxdatas, tick_labels=labels)
    except:
        plt.boxplot(boxdatas, labels=labels)
    plt.ylabel(f"discrepancy ({datasets[0][perage_var].attrs['units']})")
    plt.title(var_to_print)
    log_plot(logfile, log_br)


def compare_results(this_dict, da, da_ap_sum):
    is_close = np.all(np.isclose(da, da_ap_sum, equal_nan=True))
    this_dict["isclose"].append(is_close)
    this_dict["isclose_emoji"].append("✅" if is_close else "❌")
    this_dict["isclose_glyph"].append("✓" if is_close else "X")
    da_diff = da_ap_sum - da
    this_dict["da_diffs"].append(da_diff)
    this_dict["max_abs_diff"].append(np.nanmax(np.abs(da_diff).values))
    this_dict["max_pct_diff"].append(100 * np.nanmax(np.abs(da_diff / da).values))
    return this_dict


def add_result_text(
    my_added_diagnostics,
    my_added_diagnostics_nonperage,
    logfile,
    comparing_2,
    non_perage_equiv,
    perage_var,
    this_dict,
    var_to_print,
):
    emojis = " → ".join(this_dict["isclose_emoji"])

    with open(logfile, "a") as f:
        f.write("<hr>\n")
        f.write(f"<h2>{emojis} {var_to_print}</h2>\n")
    print(f"{emojis} {var_to_print}:")

    # Note variables that I added for diagnostic purposes
    if perage_var in my_added_diagnostics:
        log_br(logfile, "NOTE: Added by Sam Rabin for diagnostic purposes")
    if non_perage_equiv in my_added_diagnostics_nonperage:
        log_br(
            logfile,
            "NOTE: Non-per-age version added by Sam Rabin for diagnostic purposes",
        )

    max_abs_diff = this_dict["max_abs_diff"]
    max_pct_diff = this_dict["max_pct_diff"]
    if not comparing_2 or (
        max_abs_diff[0] == max_abs_diff[1] and max_pct_diff[0] == max_pct_diff[1]
    ):
        log_br(logfile, f"     max abs diff = {max_abs_diff[0]:.3g}")
        log_br(logfile, f"     max rel diff = {max_pct_diff[0]:.1f}%")
    else:
        log_br(
            logfile,
            f"     max abs diff = {max_abs_diff[0]:.3g} → {max_abs_diff[1]:.3g}",
        )
        log_br(
            logfile,
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


def add_end_text(logfile, nonperage_missing, too_many_duplexed, weights_var_missing):
    with open(logfile, "a") as f:
        f.write("<hr>\n")
        f.write("<h2>Other</h2>\n")
    log_ul(logfile, "🤷 Non-per-age equivalent not in Dataset", nonperage_missing)
    log_ul(logfile, "🤷 Too many (> 2) duplexed dimensions", too_many_duplexed)
    log_ul(logfile, "🤷 Weights variable missing", weights_var_missing)


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


def publish(publish_dir, url, logfile):
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
            elif (
                l != '  (use "git add <file>..." to include in what will be committed)'
            ):
                new_files.append(l.replace("\t", ""))
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
