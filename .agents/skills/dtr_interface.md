# Module: dtreg.dtr_interface

## Public API Contract

### Protocol: `DataTypeReg`

Represents the duck-typed interface of a DataType Registry (DTR) for schema extraction and JSON-LD metadata generation.

```python
from typing import Protocol, dict, list, Any

class DataTypeReg(Protocol):
    """
    Interface representing a datatype registry.
    """

    def get_schema_info(self, datatype_id: str) -> dict[str, list[list[dict[str, Any]]]]:
        """
        Obtain schema metadata from the registry.

        Args:
            datatype_id (str): A schema identifier URI.

        Returns:
            dict[str, list[list[dict[str, Any]]]]: Schema and property mapping with format:
                {
                    "<schema_name>": [
                        [{"dt_name": str, "dt_id": str, "dt_class": str}],
                        [{"dtp_name": str, "dtp_id": str, "dtp_card_min": int | None, "dtp_card_max": int | None, "dtp_value_type": str}, ...]
                    ]
                }
        """
        ...

    def add_context(self, prefix: str) -> dict[str, str]:
        """
        Write registry-specific context map for JSON-LD.

        Args:
            prefix (str): Context URL/URI prefix.

        Returns:
            dict[str, str]: JSON-LD context mappings.
        """
        ...

    def add_dt_type(self, identifier: str) -> str:
        """
        Write registry-specific schema type for JSON-LD.

        Args:
            identifier (str): Schema identifier.

        Returns:
            str: Prefixed schema type string.
        """
        ...

    def add_dtp_type(self, identifier: str) -> str:
        """
        Write registry-specific property type for JSON-LD.

        Args:
            identifier (str): Property identifier.

        Returns:
            str: Prefixed property type string.
        """
        ...

    def add_df_constants(self) -> dict[str, str]:
        """
        Write registry-specific dataframe constant mappings for JSON-LD.

        Returns:
            dict[str, str]: Mappings of standard keys (table, column, row, cell) to registry-specific URIs.
        """
        ...
```

### Function: `select_dtr`

```python
from typing import Type, Optional

def select_dtr(datatype_id: str) -> Optional[Type[DataTypeReg]]:
    """
    Selects a DTR class type based on the schema identifier pattern.

    Args:
        datatype_id (str): The schema identifier URI.

    Returns:
        Optional[Type[DataTypeReg]]: The matching Epic or Orkg class type, or None if unsupported.
    """
```

### Class: `Epic`

```python
from typing import Any

class Epic:
    """
    Class representing the ePIC DTR.
    """

    def get_schema_info(self, datatype_id: str) -> dict[str, list[list[dict[str, Any]]]]:
        """
        Retrieves ePIC schema metadata. Queries static JSON cache first;
        falls back to online lookup via `extract_epic(datatype_id)` if not cached.
        """
        ...

    def add_context(self, prefix: str) -> dict[str, str]:
        """
        Returns JSON-LD context map with keys: 'doi', 'columns', 'col_number',
        'col_titles', 'rows', 'row_number', 'row_titles', 'cells', 'column',
        'value', 'tab_label'.
        """
        ...

    def add_dt_type(self, identifier: str) -> str:
        """
        Returns: "doi:" + identifier
        """
        ...

    def add_dtp_type(self, identifier: str) -> str:
        """
        Returns: "doi:" + identifier
        """
        ...

    def add_df_constants(self) -> dict[str, str]:
        """
        Returns:
            dict[str, str]: Hardcoded mappings for table, column, row, and cell.
        """
        ...
```

### Class: `Orkg`

```python
from typing import Any

class Orkg:
    """
    Class representing the ORKG DTR.
    """

    def get_schema_info(self, datatype_id: str) -> dict[str, list[list[dict[str, Any]]]]:
        """
        Retrieves ORKG template metadata from the live registry API via `extract_orkg(datatype_id)`.
        """
        ...

    def add_context(self, prefix: str) -> dict[str, str]:
        """
        Returns JSON-LD context map with keys: 'orkgc', 'orkgr', 'orkgp',
        'columns', 'col_number', 'col_titles', 'rows', 'row_number', 'row_titles',
        'cells', 'column', 'value', 'label', 'tab_label'.
        """
        ...

    def add_dt_type(self, identifier: str) -> str:
        """
        Returns: "orkgr:" + identifier
        """
        ...

    def add_dtp_type(self, identifier: str) -> str:
        """
        Returns: "label" if identifier is "label", else "orkgp:" + identifier.
        """
        ...

    def add_df_constants(self) -> dict[str, str]:
        """
        Returns:
            dict[str, str]: Hardcoded mappings for table, column, row, and cell using 'orkgc' namespace.
        """
        ...
```

## Minimal Working Recipe

```python
from dtreg.dtr_interface import select_dtr, DataTypeReg

def process_schema(datatype_id: str) -> None:
    # 1. Identify the DTR provider
    dtr_class = select_dtr(datatype_id)
    if dtr_class is None:
        raise ValueError(f"No DTR mapping found for schema: {datatype_id}")
    
    # 2. Instantiate the DTR handler
    dtr_instance: DataTypeReg = dtr_class()
    
    # 3. Retrieve schema metadata structure
    schema_info = dtr_instance.get_schema_info(datatype_id)
    print(f"Loaded schema keys: {list(schema_info.keys())}")
    
    # 4. Generate JSON-LD components
    prefix = "https://doi.org/" if dtr_class.__name__ == "Epic" else "https://orkg.org/"
    context = dtr_instance.add_context(prefix)
    dt_type = dtr_instance.add_dt_type("sample_id")
    constants = dtr_instance.add_df_constants()
    
    print("Generated Context Keys:", list(context.keys()))
    print("Data Type URI:", dt_type)
    print("Dataframe Constants:", constants)

# Example execution with Epic DTR schema
process_schema("https://doi.org/21.T11969/1ea0e148d9bbe08335cd")
```

## Anti-Patterns & Risks

### 1. Insecure and Fragile URI Parsing in `select_dtr`
- **Source**:
  ```python
  if datatype_id.split("/", 4)[3] == '21.T11969':
  ...
  elif "orkg.org" in datatype_id.split("/", 4)[2]:
  ```
- **Risk**: Hardcoded reliance on index positions of slashed splits. If a valid URI with fewer than 4 slashes (e.g. `doi:21.T11969/1ea0` or a relative path) is passed, `split("/", 4)` yields fewer indices, leading to a silent or loud crash with `IndexError: list index out of range`. Standard parsing tools like `urllib.parse.urlparse` or proper regular expressions should be used instead.

### 2. Defunct Exception Assertion in Unit Tests
- **Source**:
  ```python
  def test_no_dtr(self):
      select_dtr("https://doi.org/22.B34567/1ea0e148d9bbe08335cd")
      self.assertRaisesRegex(
          ValueError,
          "SystemExit: Please check whether the schema belongs to the ePIC or the ORKG dtr")
  ```
- **Risk**: `self.assertRaisesRegex(expected_exception, expected_regex)` acts as a context manager when invoked without a third callable argument. Because the context manager is never entered with a `with` statement, **the assertion is entirely skipped/ignored**, making the test pass silently despite:
  - `select_dtr` NOT raising `ValueError` (it prints to stdout and returns `None`).
  - No matching exception or regex condition being evaluated.

### 3. Missing Explicit Protocol Adherence or Decorator
- **Source**: `Epic` and `Orkg` are independent classes that do not explicitly subclass or decorate with `DataTypeReg` or `Protocol`.
- **Risk**: Standard IDEs and static type checkers like `mypy` cannot verify that both `Epic` and `Orkg` maintain perfect API parity with `DataTypeReg` interface changes. A decorator like `@runtime_checkable` on the protocol is also missing, limiting runtime type checking.

### 4. Highly Coupled Hardcoded Vocabularies
- **Source**: `add_context` and `add_df_constants` methods in both `Epic` and `Orkg` classes contain hardcoded lists of identifiers (e.g., `0424f6e7026fa4bc2c4a` or `"CSVW_Columns"`).
- **Risk**: Upstream changes in ePIC or ORKG schema IDs or RDF layouts will generate stale or broken JSON-LD context mappings. These mappings should be loaded dynamically from configuration registries or schema descriptors instead of being embedded in source code.
