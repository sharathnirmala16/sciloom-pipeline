# Data Preprocessing

This tutorial exemplifies the use of the Data Preprocessing data type ([https://doi.org/21.T11969/37182ecfb4474942e255](https://doi.org/21.T11969/37182ecfb4474942e255)) using the Iris dataset. Specifically, we filter the original data to include Setosa species only.

## Requirements

The tutorial uses Python and the Python [dtreg package](https://pypi.org/project/dtreg/), which you can install using `pip`.

```
pip install dtreg
```

## Scientific code

We begin with the code that filters the original data to include only Setosa species (`target = 0`). Having imported required package, we load the Iris dataset and then filter.

```
from sklearn import datasets

data = datasets.load_iris(as_frame=True).frame

data_filtered = data.loc[data["target"] == 0]
```

## dtreg code

We can now extend the scientific code and use the Data Preprocessing data type with dtreg to describe this finding with structured data that can be published and automatically ingested into the TIB Knowledge Loom. We first import the required dtreg functions, then load the Data Analysis and the Data Preprocessing data types, and finally describe the training and evaluation of the classifier as a part of a data analysis. The resulting structured data is saved to a file.

```
from dtreg.load_datatype import load_datatype
from dtreg.to_jsonld import to_jsonld

dt1 = load_datatype("https://doi.org/21.T11969/feeb33ad3e4440682a4d") # Data Analysis
dt2 = load_datatype("https://doi.org/21.T11969/37182ecfb4474942e255") # Data Preprocessing

# Statement 1: Original Iris data filtered to include only the Setosa species.

da1 = dt1.data_analysis(
  has_part=dt2.data_preprocessing(
    label="Iris data filtered to include only the Setosa species.",
    executes=dt2.software_method(
      label="pandas.DataFrame.loc",
      has_support_url="https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.loc.html",
      is_implemented_by='data.loc[data["target"] == 0]',
      part_of=dt2.software_library(
        label="pandas",
        version_info="3.0.1",
        has_support_url="https://pandas.pydata.org",
        part_of=dt2.software(label="Python",
                             version_info="3.12.5",
                             has_support_url="https://www.python.org/")
      )
    ),
    has_input=dt2.data_item(label="Iris dataset (source: sklearn.datasets.load_iris).",
                            source_table=data,
                            has_characteristic=dt2.matrix_size(
                                number_of_rows=data.shape[0],
                                number_of_columns=data.shape[1]
                            )),
    has_output=dt2.data_item(label="Filtered Iris dataset to include only Setosa species.",
                            source_table=data_filtered,
                            has_characteristic=dt2.matrix_size(
                                number_of_rows=data_filtered.shape[0],
                                number_of_columns=data_filtered.shape[1]
                            ))
  )
)

json = to_jsonld(da1)

with open("da1.json", "w") as f:
  f.write(json)
```

## As a comment block

As an alternative to describing the data analysis using dtreg, you can also describe the data preprocessing with a comment block by including information about the environment (recommended for older setups) and listing the analysis steps with type and main code line as follows.

```
# Environment
# Python 3.12.5
# scikit-learn==1.2.2
# Statement 1: Original Iris data filtered to include only the Setosa species.
# Analysis Step 1: Data Preprocessing, data.loc[data["target"] == 0]
```

## Examples

There are numerous Loom records that make use of the Data Preprocessing data type. Take a look at these to see this data type in action.

- TODO
