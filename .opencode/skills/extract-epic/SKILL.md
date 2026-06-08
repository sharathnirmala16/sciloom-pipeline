---
name: extract-epic
description: API contract for the dtreg.extract_epic module. Covers the extract_epic function for recursively extracting ePIC datatype schemas including nested dependencies from the ePIC DTR registry.
---

# Module: dtreg.extract_epic

## Public API Contract

### Function: `extract_epic`

```python
from typing import Dict, List, Union, Optional, TypedDict

class SchemaHeader(TypedDict):
    dt_name: str
    dt_id: str
    dt_class: str

class PropertyDetail(TypedDict):
    dtp_name: str
    dtp_id: str
    dtp_card_min: Optional[int]
    dtp_card_max: Optional[int]
    dtp_value_type: str

# Index 0 is a list containing the single schema header dict.
# Index 1 is a list of the properties' detail dicts.
ExtractedSchema = List[Union[List[SchemaHeader], List[PropertyDetail]]]

def extract_epic(datatype_id: str) -> Dict[str, ExtractedSchema]:
    """
    Extract ePIC datatype information recursively and return a dictionary of schemas.

    Args:
        datatype_id (str): The identifier (normally a DOI URL) of the root ePIC datatype.

    Returns:
        Dict[str, ExtractedSchema]: A dictionary mapping the normalized datatype name to its extracted schema details.
                                     Includes both the root schema and any recursively retrieved dependencies.
    """
```

## Minimal Working Recipe

```python
from dtreg.extract_epic import extract_epic

# Retrieve schema details and all its referenced sub-schemas recursively
schema_data = extract_epic("https://doi.org/21.T11969/fb2e379f820c6f8f9e82")

# Access the extracted datatype by its normalized (lowercase, underscore) name
main_schema = schema_data.get("integer_in_string")

if main_schema:
    # Extracted list structure: index 0 contains the SchemaHeader list
    header = main_schema[0][0]
    # Index 1 contains the properties list
    properties = main_schema[1]
    
    print(f"Loaded Schema: {header['dt_name']} (ID: {header['dt_id']}, Class: {header['dt_class']})")
    for prop in properties:
        print(f"  - Property: {prop['dtp_name']}")
        print(f"    ID: {prop['dtp_id']}")
        print(f"    Cardinality: [{prop['dtp_card_min']}, {prop['dtp_card_max']}]")
        print(f"    Value Type: {prop['dtp_value_type']}")
else:
    print("Schema could not be retrieved.")
```

## Anti-Patterns & Risks

### 1. Primitive Obsession & Fragile Nested List Structure
- **Source**: 
  ```python
  extracted = [[schema_dict]]
  ...
  extracted.append(all_props)
  ```
- **Risk**: Instead of returning structured domain models or simple dictionary with descriptive keys (e.g., `{"header": schema_dict, "properties": all_props}`), it uses a multi-level nested list of list of dicts. Callers must use magic indexes (e.g., `schema[1][0]`) to access properties, which makes code brittle, hard to read, and prone to indexing errors.

### 2. Recursive State Accumulation via Outer Scope Mutation
- **Source**:
  ```python
  extract_all = {}
  def extractor_function(datatype_id):
      ...
      extract_all[schema_dict["dt_name"]] = list(extracted)
  ```
- **Risk**: Modifying a non-local variable (`extract_all`) inside recursive closures introduces implicit side-effects, limits function reusability, and hinders isolated unit testing of sub-routines.

### 3. Fragile Slicing Assumption for Identifier Suffix Extraction
- **Source**: `info["Identifier"].split("/", 4)[1]`
- **Risk**: Assumes the `Identifier` field strictly follows a format with exactly one slash dividing prefix/suffix (e.g., `"21.T11969/fb2e379f820c6f8f9e82"`). If a full HTTP URL (e.g., `"https://doi.org/21.T11969/fb..."`) is received, the split list index `[1]` yields an empty string `""` without failing, producing malformed IDs.

### 4. Hardcoded Protocol and Host for Recursive Resolution
- **Source**: `extractor_function("https://doi.org/" + prop["Type"])`
- **Risk**: Assumes all nested types must be resolved specifically via `"https://doi.org/"`. If the nested property already contains a full URI, prepending the hardcoded string produces double-prefixed invalid URLs, breaking the API call.

### 5. Absence of Network Request Safety Nets
- **Source**: Uses `request_dtr()` without checking HTTP statuses, setting timeouts, or retrying.
- **Risk**: Malformed routes, slow connections, or down-state services will crash the application abruptly with generic, unhandled HTTP/connection exceptions (e.g., `requests.exceptions.JSONDecodeError`).

### 6. Brittle Testing via Exact Mock URI Matching
- **Source**: `tests/helpers_mock/mocking.py` matching mock routes by strict string comparison:
  ```python
  if route == "https://doi.org/21.T11969/31483624b5c80014b6c7?locatt=view:json":
  ```
- **Risk**: Tests are coupled to a precise query string configuration and host. Simple changes in query parameter ordering or scheme will cause mocks to silently fail/return `None`, throwing obscure `TypeError` failures instead of helpful diagnostic errors.
