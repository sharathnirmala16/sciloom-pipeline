# `load_datatype` API Contract & Specification

## 1. Module Overview
- **Module Path:** `src/dtreg/load_datatype.py`
- **Tests Path:** `tests/load_datatype_tests.py`
- **Purpose:** Dynamically resolves schemas from a Data Type Registry (DTR) and builds dynamic Python classes mapping schema fields to instance attributes.

---

## 2. Public API Contract

### Function Signatures
```python
from types import SimpleNamespace
from typing import Dict, Type

def load_datatype(datatype_id: str) -> SimpleNamespace:
    """
    Resolves a schema by ID, constructs classes for its types,
    and returns them bundled within a SimpleNamespace.
    """

def write_classes(datatype_id: str) -> Dict[str, Type]:
    """
    Queries the registry for schema definitions and constructs 
    dynamic Type objects mapped by class names.
    """
```

### Input & Output Specifications

#### `load_datatype(datatype_id)`
- **`datatype_id`** (`str`): Fully qualified URI for the registry schema (e.g., `"https://doi.org/21.T11969/..."` or `"https://orkg.org/template/..."`).
- **Returns** (`types.SimpleNamespace`): Namespace whose attributes represent dynamically created class definitions corresponding to schema components.

#### `write_classes(datatype_id)`
- **`datatype_id`** (`str`): Fully qualified URI for the registry schema.
- **Returns** (`Dict[str, Type]`): Mapping of formatting-compliant schema type names to dynamic subclass objects.

---

## 3. Dynamically Generated Class Specification

Classes created via `write_classes` possess the following specifications:

### Base Classes
- **ePIC Schemas:** Inherits from `dtreg.dtr_interface.Epic`.
- **ORKG Schemas:** Inherits from `dtreg.dtr_interface.Orkg`.

### Class Attributes
| Attribute Name | Type | Description |
| :--- | :--- | :--- |
| `prefix` | `str` | Base registry URL prefix (e.g., `https://doi.org/21.T11969/`). |
| `dt_name` | `str` | Formatted snake_case name of the class datatype. |
| `dt_id` | `str` | Registry unique identifier of the datatype. |
| `dt_class` | `str` | Class type categorization from schema. |
| `prop_list` | `List[str]` | List of snake_case names of registry property fields. |
| `prop_info` | `List[Dict[str, Any]]` | Raw metadata dictionary list for schema properties. |

### Instantiation Constructor (`__init__`)
```python
def __init__(self, *args: Any, **kwargs: Any) -> None:
    """
    Initializes instance variables matching `self.prop_list` 
    from provided keyword arguments.
    """
```
- **Behavior:** Iterates through `self.prop_list`. Calls `setattr(self, name, kwargs.get(name))` for each element.
- **Note:** All positional arguments in `*args` are ignored. Missing properties in `kwargs` default to `None`.

---

## 4. Minimal Working Recipe

```python
from types import SimpleNamespace
from dtreg.load_datatype import load_datatype

# 1. Resolve schema classes from registry URL (e.g., ePIC matrix_size datatype)
schema_uri = "https://doi.org/21.T11969/31483624b5c80014b6c7"
schema_ns: SimpleNamespace = load_datatype(schema_uri)

# 2. Extract dynamic class definition
MatrixSize = schema_ns.matrix_size

# 3. Read class metadata attributes
print(MatrixSize.dt_name)    # "matrix_size"
print(MatrixSize.prop_list)  # ["number_of_rows", "number_of_columns"]
print(MatrixSize.prefix)     # "https://doi.org/21.T11969/"

# 4. Instantiate object via keywords
matrix = MatrixSize(number_of_rows=5, number_of_columns=10)

# 5. Access resolved instance attributes
print(matrix.number_of_rows)     # 5
print(matrix.number_of_columns)  # 10
```

---

## 5. DTR Schema Response Reference Format

The underlying schema queried by `write_classes` expected from `get_schema_info` adheres to the dictionary layout:

```json
{
  "DATATYPE_NAME": [
    [
      {
        "dt_name": "string",
        "dt_id": "string",
        "dt_class": "string"
      }
    ],
    [
      {
        "dtp_name": "string",
        "dtp_id": "string",
        "dtp_card_min": "integer_or_null",
        "dtp_card_max": "integer_or_null",
        "dtp_value_type": "string"
      }
    ]
  ]
}
```

---

## 6. Anti-Patterns & Design Flaws

### 1. Silent Failures / Uninformative Exceptions
- **Unchecked DTR Selection:** If `select_dtr(datatype_id)` fails to identify the registry, it prints to stdout and returns `None`. `write_classes` immediately invokes `datypreg()` leading to an uninformative `TypeError: 'NoneType' object is not callable` instead of a custom `ValueError`.

### 2. Defective Dynamic Constructor Design
- **Silently Discarded Positional Arguments:** `__init__` takes `*args` but does not process them, raise a `TypeError`, or pass them to parent. Calling `MatrixSize(5, 10)` sets nothing and results in both properties being `None`.
- **Bypassed Parent Initialization:** The dynamic `__init__` does not invoke `super().__init__(*args, **kwargs)`. If the parent class (`Epic` or `Orkg`) defines initialization code, it is bypassed completely.

### 3. Outdated and Inaccurate Docstrings
- **`load_datatype` Type Mismatch:** Docstring says `return: a list of schemata as SimpleNamespace objects`. It actually returns a *single* `SimpleNamespace` containing classes.
- **`write_classes` Type Mismatch:** Docstring says `return: a list of classes`. It actually returns a dictionary mapping strings to classes (`Dict[str, Type]`).

### 4. Fragile Routing Logic
- **Rigid URI Parsing:** Helper and selector code utilizes raw `split("/", 4)` operations. Any variation in trailing slashes or URL query parameters can break segment index targets, resulting in `IndexError` or faulty registry routing.

### 5. Loop-Nested Function Declarations
- **Redefining `__init__`:** Declaring `def __init__(...)` inside the `for` loop body of `write_classes`. Although functionally safe here because `type()` captures the local function binding instantly, it represents a namespace pollution anti-pattern.
