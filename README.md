# Check that per-ageclass variables are weighted correctly

## Summary

`check_AP_variables_NONwtd.py` compares two runs of a given test. It generates and publishes an HTML page with figure for each per-ageclass variable. Figures contain one boxplot for each test. The boxplots represent the difference between a per-ageclass variable (e.g., `FATES_BURNFRAC_AP`)---AFTER summing across the age-class axis---and its non-per-ageclass equivalent (e.g., `FATES_BURNFRAC`). Each data point in the boxplots represent one member of the non-per-ageclass array in the last saved timestep of the test. So for `FATES_BURNFRAC` each datapoint is a gridcell, whereas for `FATES_VEGC_PF` each is a PFT in a gridcell.

If a code version is behaving as expected, ideally all data points should be zero. In practice, because of rounding errors, this can't usually be achieved. Instead, we expect that the data points should be grouped more or less symmetrically around zero, with small absolute and relative differences. Here, ✅ indicates boxplots with all absolute values of absolute differences < 1e-9 and relative differences < 1e-8. Boxplots that do not meet those criteria are marked with ❌.

Yes, we really want the _sum_ across the age-class axis to match, even though in most cases what users want of the variable is each age-class's actual value. (If we were saving that, then in order to make the comparison, we would need to take the area-weighted mean across age classes.) We have this behavior because it allows for better preservation of numerical accuracy.

## Options

There are several options you must set in a file called `options.py`. Here is an example:
```python
# The name of the test you're looking at
TEST_NAME = (
    "SMS_Lm49.f10_f10_mg37.I2000Clm60Fates.derecho_intel.clm-FatesColdAllVarsMonthly"
)

# The parent directory of each version where that test got saved
TESTSET_DIR_LIST = [
    "/glade/derecho/scratch/samrabin/tests_1001-170645de",
    "/glade/derecho/scratch/samrabin/tests_1008-131302de",
]

# Where the HTML file should be saved
PUBLISH_DIR = "/glade/u/home/samrabin/analysis-outputs/fates-refactor-history"
```