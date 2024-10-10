"""
Functions useful for writing to HTML file
"""
# pylint: disable=invalid-name
# pylint: disable=missing-function-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=too-many-arguments
# pylint: disable=fixme

import base64
from io import BytesIO
import matplotlib.pyplot as plt

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


class Rfh_Write:
    def __init__(self, logfile, testset_dir_basename_list, thisrepo_url):
        self.logfile = logfile
        self.testset_dir_basename_list = testset_dir_basename_list
        self.thisrepo_url = thisrepo_url

    def add_result_text(
        self,
        non_perage_equiv,
        perage_var,
        this_dict,
        var_to_print,
        comparing_2,
    ):
        emojis = " → ".join(this_dict["isclose_emoji"])

        with open(self.logfile, "a") as f:
            f.write("<hr>\n")
            f.write(f"<h2>{emojis} {var_to_print}</h2>\n")
        print(f"{emojis} {var_to_print}:")

        # Note variables that I added for diagnostic purposes
        if perage_var in MY_ADDED_DIAGNOSTICS:
            self.log_br("NOTE: Added by Sam Rabin for diagnostic purposes")
        if non_perage_equiv in MY_ADDED_DIAGNOSTICS_NONPERAGE:
            self.log_br(
                "NOTE: Non-per-age version added by Sam Rabin for diagnostic purposes",
            )

        max_abs_diff = this_dict["max_abs_diff"]
        max_pct_diff = this_dict["max_pct_diff"]
        if not comparing_2 or (
            max_abs_diff[0] == max_abs_diff[1] and max_pct_diff[0] == max_pct_diff[1]
        ):
            self.log_br(f"     max abs diff = {max_abs_diff[0]:.3g}")
            self.log_br(f"     max rel diff = {max_pct_diff[0]:.1f}%")
        else:
            self.log_br(
                f"     max abs diff = {max_abs_diff[0]:.3g} → {max_abs_diff[1]:.3g}",
            )
            self.log_br(
                f"     max rel diff = {max_pct_diff[0]:.1f}% → {max_pct_diff[1]:.1f}%",
            )

    def log_br(self, msg):
        if "img src" not in msg:
            print(msg.replace("<p>", ""))

        msg += "<br>\n"
        with open(self.logfile, "a") as f:
            f.write(msg)

    def log_ul(self, title, items):
        if not items:
            return

        print("\n     ".join([f"\n{title}"] + items))

        with open(self.logfile, "a") as f:
            f.write("<p>\n")
            f.write(f"{title}:<br>\n")
            f.write("<ul>\n")
            for i in items:
                f.write(f"<li>{i}</li>\n")
            f.write("</ul>\n")

    def log_plot(self):
        # Convert plot to base64 string
        buf = BytesIO()
        plt.gcf().savefig(buf, format="png")
        buf.seek(0)
        plot_data = base64.b64encode(buf.read()).decode("utf8")
        plt.close()

        # Embed plot in HTML log message
        plot_html = '<p><img src="data:image/png;base64,{}">'.format(plot_data)
        self.log_br(plot_html)
        buf.close()

    def write_front_matter(self, test_name, comparing_2):
        with open(self.logfile, "a") as f:
            a = self.testset_dir_basename_list[0]
            if comparing_2:
                b = self.testset_dir_basename_list[1]
                msg = f"<h1>Comparing NONwtd {a} and {b}</h1>\n"
            else:
                msg = f"<h1>{a}</h1>\n"
            f.write(msg)
        self.log_br(f"Test: {test_name} <br>")
        with open(self.logfile, "a") as f:
            # pylint: disable=line-too-long
            f.write("<b>How to read these plots</b><br>")
            f.write(
                "This webpage compares two runs of the above test, with different code versions noted below. Figures contain one boxplot for each test. The boxplots represent the difference between a per-ageclass variable (e.g., FATES_BURNFRAC_AP)---AFTER summing across the age-class axis---and its non-per-ageclass equivalent (e.g., FATES_BURNFRAC). Each data point in the boxplots represent one member of the non-per-ageclass array in the last saved timestep of the test. So for FATES_BURNFRAC each datapoint is a gridcell, whereas for FATES_VEGC_PF each is a PFT in a gridcell.<br><br>"
            )
            f.write(
                "If a code version is behaving as expected, ideally all data points should be zero. In practice, because of rounding errors, this can't usually be achieved. Instead, we expect that the data points should be grouped more or less symmetrically around zero, with small absolute and relative differences. Here, ✅ indicates boxplots with all absolute values of absolute differences < 1e-9 and relative differences < 1e-8. Boxplots that do not meet those criteria are marked with ❌.<br><br>"
            )
            f.write(
                "Yes, we really want the SUM across the age-class axis to match, even though in most cases what users want of the variable is each age-class's actual value. (If we were saving that, then in order to make the comparison, we would need to take the area-weighted mean across age classes.) We have this behavior because it allows for better preservation of numerical accuracy. <br><br>"
            )
            thisrepo_link = f'<a href="{self.thisrepo_url}">this repo</a>.'
            f.write(
                "This analysis was performed (and this webpage was published) using the code in "
                + thisrepo_link
            )
