# Group Comparison

This tutorial exemplifies the use of the Group Comparison data type ([https://doi.org/21.T11969/b9335ce2c99ed87735a6](https://doi.org/21.T11969/b9335ce2c99ed87735a6)) for a t-test for petal length of Setosa and Virginica Iris species, and the description of this data analysis using the Group Comparison data type in dtreg.

## Requirements
The tutorial is for both Python and the Python [dtreg package](https://pypi.org/project/dtreg/), which you can install with `pip install dtreg`, and R and the R [dtreg package](https://doi.org/10.32614/CRAN.package.dtreg), which you can install with `install.packages("dtreg")`.

## Scientific code

We begin with the code that implements the t-test. Having imported required packages, we load the Iris dataset, prepare the data, perform the t-test, and create a data frame to store the p-value and other parameters. We show this first in Python and then in R.

```
from sklearn import datasets
from scipy.stats import ttest_ind
import pandas as pd

iris = datasets.load_iris(as_frame=True).frame
iris['Species'] = iris['target'].replace({0: 'setosa', 1: 'versicolor', 2: 'virginica'})
setosa = iris[iris['Species'] == 'setosa']['petal length (cm)']
virginica = iris[iris['Species'] == 'virginica']['petal length (cm)']
tt = ttest_ind(setosa, virginica, equal_var=False)
df_results = pd.DataFrame({"t.statistic": [tt.statistic],
                           "df": [tt.df],
                           "p.value": [tt.pvalue]})
```

```
library(dplyr)

data(iris)
setosa <- iris |>
  dplyr::filter(Species == "setosa") |>
  dplyr::select(Petal.Length)
virginica <- iris |>
  dplyr::filter(Species == "virginica") |>
  dplyr::select(Petal.Length)

tt <- stats::t.test(setosa, virginica, var.equal = FALSE)
df_results = data.frame(
  t.statistic = tt$statistic,
  df = tt$parameter,
  p.value = tt$p.value
)
rownames(df_results) <- "value"
```

We obtain a p-value of 9.3e-50. 

## dtreg code

We can now extend the scientific code and use the Group Comparison data type with dtreg to describe this finding with structured data that can be published and automatically ingested into the TIB Knowledge Loom. We first import the required dtreg functions, then load the Data Analysis and the Group Comparison data types, and finally describe the t-test as a part of a data analysis. The resulting structured data is saved to a file. We show this first in Python and then in R.

```
from dtreg.load_datatype import load_datatype
from dtreg.to_jsonld import to_jsonld

dt1 = load_datatype("https://doi.org/21.T11969/feeb33ad3e4440682a4d") # Data Analysis
dt2 = load_datatype("https://doi.org/21.T11969/b9335ce2c99ed87735a6") # Group Comparison

da1 = dt1.data_analysis(
  has_part=dt2.group_comparison(
    label="t-test Iris petal length setosa vs virginica",
    executes=dt2.software_method(
      label="ttest_ind",
      is_implemented_by="ttest_ind(setosa, virginica, equal_var = False)",
      part_of=dt2.software_library(
        label="scipy",
        version_info="1.15.1",
        part_of=dt2.software(label="Python",
                             version_info="3.12.5")
      )
    ),
    targets=dt2.component(label="petal length (cm)"),
    has_input=dt2.data_item(label="Iris petal length setosa virginica",
                            source_table=iris),
    has_output=dt2.data_item(source_table=df_results)
  )
)

json = to_jsonld(da1)

with open("da1.json", "w") as f:
  f.write(json)
```

```
library(dtreg)

dt1 <- dtreg::load_datatype("https://doi.org/21.T11969/feeb33ad3e4440682a4d") # Data Analysis
dt2 <- dtreg::load_datatype("https://doi.org/21.T11969/b9335ce2c99ed87735a6") # Group Comparison

da1 <- dt1$data_analysis(
  has_part = dt2$group_comparison(
    label = "t-test Iris petal length setosa vs virginica",
    executes = dt2$software_method(
      label = "t.test",
      is_implemented_by = "stats::t.test(setosa, virginica, var.equal = FALSE)",
      part_of = dt2$software_library(
        label = "stats",
        version_info = "4.3.1",
        part_of = dt2$software(label = "R",
                               version_info = "4.3.1")
      )
    ),
    targets = dt2$component(label = "Petal.Length"),
    has_input = dt2$data_item(label = "Iris petal length setosa virginica",
                              source_table = iris),
    has_output = dt2$data_item(source_table = df_results)
  )
)

json <- dtreg::to_jsonld(da1)

write(json, "da1.json")
```

## As a comment block

As an alternative to describing the algorithm evaluation using dtreg, you can also describe the algorithm evaluation with a comment block by including information about the environment (recommended for older setups) and listing the analysis steps with type and main code line as follows.

```
# Environment
# Python 3.12.5
# pandas==2.2.2, scikit-learn==1.2.2, scipy==1.13.1
# Statement 1: There is a statistically significant difference in petal length between setosa and virginica Iris species.
# Analysis Step 1: Group Comparison, ttest_ind(setosa, virginica, equal_var = False)
```

In R you can easily obtain environment information with `sessionInfo()`.

```
# Environment
# R 4.5.1
# dplyr==1.1.4
# Statement 1: There is a statistically significant difference in petal length between setosa and virginica Iris species.
# Analysis Step 1: Group Comparison, stats::t.test(setosa, virginica, var.equal = FALSE)
```

## Examples

There are numerous loom records that make use of the Group Comparison data type. Take a look at these to see this data type in action.

- Gentsch, N. (2026). The legacy effect of Cover Crops on soil structure amelioration: When focusing on individual soil horizons, pairwise comparison indicates significantly higher mean weight diameter (MWD) compared to the fallow treatment for clover at 0-10 cm (18.8% higher, p=0.017), Mix12 at 20-30 cm (37.6% higher, p=0.049), and phacelia (17.0% higher, p=0.018) and Mix4 (12.8% higher, p=0.037) at 30-40 cm. (Version 1) [Dataset]. Technische Informationsbibliothek (TIB). https://doi.org/10.82209/4KZX-8644 
