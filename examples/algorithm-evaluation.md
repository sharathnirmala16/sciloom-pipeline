# Algorithm Evaluation

This tutorial exemplifies the use of the Algorithm Evaluation data type ([https://doi.org/21.T11969/5e782e67e70d0b2a022a](https://doi.org/21.T11969/5e782e67e70d0b2a022a)) for a simple machine learning classification task, namely the training and evaluation of a classifier for Iris species, and then the description of the implementation using the Algorithm Evaluation data type in dtreg.

## Requirements

The tutorial uses Python and the Python [dtreg package](https://pypi.org/project/dtreg/), which you can install using `pip`.

```
pip install dtreg
```

## Scientific code

We begin with the code that trains and evaluates a machine learning model. Having imported required packages, we load the Iris dataset, prepare the data, train and cross validate a support vector machine based classifer, and create a data frame to store the main scores.

```
import pandas as pd
from sklearn import datasets
from sklearn.svm import SVC
from sklearn.model_selection import cross_validate

data = datasets.load_iris(as_frame=True).frame

X = data.drop("target", axis=1)
y = data["target"]

model = SVC()

scores = cross_validate(model, X, y, cv=5, scoring=["precision_macro", "recall_macro", "f1_macro"])

scores = pd.DataFrame({"Precision": [scores["test_precision_macro"].mean()],
                       "Recall": [scores["test_recall_macro"].mean()],
                       "F1 score": [scores["test_f1_macro"].mean()]})

print(scores)
```

Having evaluated the performance of the classifer, we obtain an F1 score of 0.97. 

## dtreg code

We can now extend the scientific code and use the Algorithm Evaluation data type with dtreg to describe this finding with structured data that can be published and automatically ingested into the TIB Knowledge Loom. We first import the required dtreg functions, then load the Data Analysis and the Algorithm Evaluation data types, and finally describe the training and evaluation of the classifier as a part of a data analysis. The resulting structured data is saved to a file.

```
from dtreg.load_datatype import load_datatype
from dtreg.to_jsonld import to_jsonld

dt1 = load_datatype("https://doi.org/21.T11969/feeb33ad3e4440682a4d") # Data Analysis
dt2 = load_datatype("https://doi.org/21.T11969/5e782e67e70d0b2a022a") # Algorithm Evaluation

# Statement 1: Support Vector Machine (SVM) evaluates 0.97 F1 score on the Iris dataset for the species classification task.

da1 = dt1.data_analysis(
  has_part=dt2.algorithm_evaluation(
    label="Training and evaluation of SVC classifier for Iris species.",
    executes=dt2.software_method(
      label="cross_validate",
      is_implemented_by='cross_validate(model, X, y, cv=5, scoring=["precision_macro", "recall_macro", "f1_macro"])',
      part_of=dt2.software_library(
        label="sklearn.model_selection",
        version_info="1.2.2",
        part_of=dt2.software(label="Python",
                             version_info="3.12.5")
      )
    ),
    evaluates=dt2.algorithm(label="Support Vector Machine (SVM)"),
    evaluates_for=dt2.task(label="Iris species classification"),
    has_input=dt2.data_item(label="Iris dataset (source: sklearn.datasets.load_iris).", 
                            source_table=data),
    has_output=dt2.data_item(source_table=scores)
  )
)

json = to_jsonld(da1)

with open("da1.json", "w") as f:
  f.write(json)
```

## As a comment block

As an alternative to describing the algorithm evaluation using dtreg, you can also describe the algorithm evaluation with a comment block by including information about the environment (recommended for older setups) and listing the analysis steps with type and main code line as follows.

```
# Environment
# Python 3.12.5
# pandas==2.2.2, scikit-learn==1.2.2
# Statement 1: Support Vector Machine (SVM) evaluates 0.97 F1 score on the Iris dataset for the species classification task.
# Analysis Step 1: Algorithm Evaluation, cross_validate(model, X, y, cv=5, scoring=["precision_macro", "recall_macro", "f1_macro"])
```

## Examples

There are numerous loom records that make use of the Algorithm Evaluation data type. Take a look at these to see this data type in action.

- Haris, M., & Stocker, M. (2026). Performance of selected models for the recognition of 16 named entities in plasma physics research articles (Version 1) [Dataset]. Technische Informationsbibliothek (TIB). [https://doi.org/10.82209/HV44-A941](https://doi.org/10.82209/HV44-A941)
