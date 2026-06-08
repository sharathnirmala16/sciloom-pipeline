---
name: to-jsonld
description: API contract for the dtreg.to_jsonld module. Covers the to_jsonld serializer, differ_input type router, and df_structure DataFrame-to-CSVW normalizer for converting schema instances and DataFrames into JSON-LD format.
---

# Module: `dtreg.to_jsonld`

## Technical Specification & API Contract

### Type definitions and Protocols

```python
from typing import Any, Dict, Generator, Protocol, Union
import pandas as pd

class DataTypeRegInstance(Protocol):
    """
    Protocol describing the required interface of schema-related instances 
    passed to `to_jsonld`.
    """
    dt_id: str
    prefix: str
    prop_list: list[str]
    prop_info: list[dict[str, str]]  # list of properties: [{"dtp_name": str, "dtp_id": str}]

    def add_df_constants(self) -> dict[str, str]:
        """Returns a dict mapping 'table', 'column', 'row', 'cell' names to their URI strings."""
        ...

    def add_dt_type(self, identifier: str) -> str:
        """Translates a schema identifier to its JSON-LD class URI/curie."""
        ...

    def add_dtp_type(self, identifier: str) -> str:
        """Translates a property identifier to its JSON-LD property URI/curie."""
        ...

    def add_context(self, prefix: str) -> dict[str, str]:
        """Generates the JSON-LD context map."""
        ...
```

### Functions

```python
def to_jsonld(instance: DataTypeRegInstance) -> str:
    """
    Converts a schema-related class instance to a JSON-LD formatted string.

    Args:
        instance: An object conforming to DataTypeRegInstance Protocol.

    Returns:
        A serialized JSON string in JSON-LD format.
        
    Side Effects:
        - Mutates module-level globals `uid` and `constants`.
    """

def differ_input(input: Any) -> Any:
    """
    Differentiates input type to determine structural normalization.

    Args:
        input: Any python object. If it is a pandas.DataFrame, routes to `df_structure`.
               Otherwise, returns the input unchanged.

    Returns:
        The normalized dictionary representation if a DataFrame; otherwise, the unchanged input.
    """

def df_structure(df: pd.DataFrame) -> dict[str, Any]:
    """
    Normalizes a pandas DataFrame into a CSVW-compliant schema dictionary.

    Args:
        df: The pandas DataFrame to normalize. Optional custom label can be supplied 
            via the custom `df.name` attribute.

    Returns:
        A dictionary representation containing tabular structure (columns, rows, cells).
        
    Preconditions:
        - Relies on module-level global state `uid` and `constants` being initialized.
    """
```

---

## Minimal Working Recipe

```python
import pandas as pd
from dtreg.load_datatype import load_datatype
from dtreg.to_jsonld import to_jsonld

# 1. Load schema template from Registry (ePIC registry in this case)
dt = load_datatype("https://doi.org/21.T11969/aff130c76e68ead3862e")

# 2. Build tabular data as a pandas DataFrame and label it
df = pd.DataFrame({
    "Column_A": [10.5, 20.3],
    "Column_B": ["Value_1", "Value_2"]
})
df.name = "experiment_results"

# 3. Instantiate the dynamic schema class with properties and nested entities
instance = dt.data_item(
    source_table=df,
    has_expression=dt.url()
)

# 4. Serialize to JSON-LD formatted string
json_ld_output: str = to_jsonld(instance)
print(json_ld_output)
```

---

## Common Anti-Patterns & Defect Profiles

### 1. Concurrency Safety: Module-Level Globals

* **Location:** `src/dtreg/to_jsonld.py:6-7`, `18-21`, `70-71`
* **Defect:** Thread-unsafe global references (`uid` and `constants`) initialized in `to_jsonld` and consumed in `df_structure`.
* **Impact:** 
  - Prevents independent execution of `differ_input` and `df_structure` without first calling `to_jsonld` (or mock-patching the module).
  - Causes concurrent serialization tasks to corrupt/overwrite each other's identifier generation or schema constants.
* **Code Excerpt:**
  ```python
  constants = None
  uid = None

  def to_jsonld(instance):
      ...
      global uid
      uid = generate_uid()
      global constants
      constants = instance.add_df_constants()
  ```

### 2. Broken Test Assertion: Silent `assertRaisesRegex` Context Manager

* **Location:** `tests/to_jsonld_tests.py:46-53`
* **Defect:** `self.assertRaisesRegex` is invoked without a context manager (`with` block) or callable parameter.
* **Impact:** The assertions are never executed. The test falsely passes even though the production logic does not raise the asserted exception.
* **Code Excerpt:**
  ```python
  def test_no_function(self):
      ...
      instance = dt.data_item(source_table=abc)
      to_jsonld(instance)
      self.assertRaisesRegex(
          ValueError, "SystemExit: Input in source_table should not be a function")
  ```

### 3. Identity Check Bug on Empty List Literals

* **Location:** `src/dtreg/to_jsonld.py:32`
* **Defect:** Checks empty list using the `is` operator against a new list literal (`instance_field is []`).
* **Impact:** Because `is` checks for object identity rather than value equality, `instance_field is []` evaluates to `False`. An empty list passes through to the next block, where `instance_field[0]` triggers an immediate `IndexError` crash.
* **Code Excerpt:**
  ```python
  if instance_field is None or instance_field is []:
      pass
  elif isinstance(instance_field, list) and hasattr(instance_field[0], "prop_list"):
      result[prop_type] = list(map(write_info, instance_field))
  ```

### 4. Non-Standard Warning Suppression

* **Location:** `src/dtreg/to_jsonld.py:34-35`
* **Defect:** Uses a side-effect print statement to notify of invalid function properties instead of raising exceptions.
* **Impact:** Allows invalid types to silently fall through to subsequent logic or output incorrect JSON-LD representations.
* **Code Excerpt:**
  ```python
  elif isfunction(instance_field):
      print("Input in " + field + " should not be a function")
  ```
