---
name: extract-orkg
description: API contract for the dtreg.extract_orkg module. Covers the extract_orkg function for extracting ORKG template metadata, property details, and cardinality from the ORKG registry API.
---

# Public API Contract

## `extract_orkg` Function

### Signature
```python
def extract_orkg(datatype_id: str) -> dict[str, list[list[dict[str, any]]]]
```

### Parameter Specification
- **`datatype_id`**: `str`
  - A URL identifier of an ORKG (Open Research Knowledge Graph) template.
  - Expected format: `"{scheme}://{host}/template/{resource_id}"` (e.g., `"https://orkg.org/template/R758316"`).
  - Must contain at least 4 slashes (`/`).

### Return Specification
- **Type**: `dict[str, list[list[dict[str, any]]]]`
- **Structure**:
  - **Key**: `str` - Normalized template name (lowercased, spaces and dashes replaced with underscores).
  - **Value**: `list[list[dict[str, any]]]` of length 2:
    - **Index 0**: `list[dict]` containing a single schema metadata dictionary:
      ```python
      {
          "dt_name": str,       # Normalized template name
          "dt_id": str,         # Template resource ID (e.g., "R758316")
          "dt_class": str       # Target class ID (e.g., "C102007")
      }
      ```
    - **Index 1**: `list[dict]` containing properties of the template:
      ```python
      [
          {
              "dtp_name": str,             # Normalized property name (or "label")
              "dtp_id": str,               # Property ID (or "label")
              "dtp_card_min": int | None,  # Minimum cardinality
              "dtp_card_max": int | None,  # Maximum cardinality
              "dtp_value_type": str        # Value type or target class ID (e.g., "Integer", "C102007")
          },
          ...
      ]
      ```
      *Note: A default `"label"` property dictionary is always appended as the last element of this list:*
      ```python
      {
          "dtp_name": "label",
          "dtp_id": "label",
          "dtp_card_min": 0,
          "dtp_card_max": 1,
          "dtp_value_type": "string"
      }
      ```

---

# Minimal Working Recipe

## Real-world API Call
```python
from dtreg.extract_orkg import extract_orkg

# Retrieve and extract ORKG template structure
template_data = extract_orkg("https://orkg.org/template/R758316")
print(template_data)
```

## Mocked API Call for Testing
```python
from unittest.mock import patch
from dtreg.extract_orkg import extract_orkg

# Mocked responses for ORKG endpoints
def mock_request_orkg(route: str) -> dict:
    if route == "https://orkg.org/api/templates/R758316":
        return {
            "id": "R758316",
            "label": "My Template",
            "target_class": {"id": "C102007"},
            "properties": [
                {
                    "min_count": 0,
                    "max_count": None,
                    "path": {"id": "P160024", "label": "property3"},
                    "datatype": {"id": "Integer"}
                }
            ]
        }
    raise ValueError(f"Unexpected route: {route}")

# Patch request_dtr dependency to use the mock
with patch("dtreg.extract_orkg.request_dtr", side_effect=mock_request_orkg):
    result = extract_orkg("https://orkg.org/template/R758316")
    assert result == {
        "my_template": [
            [
                {
                    "dt_name": "my_template",
                    "dt_id": "R758316",
                    "dt_class": "C102007"
                }
            ],
            [
                {
                    "dtp_name": "property3",
                    "dtp_id": "P160024",
                    "dtp_card_min": 0,
                    "dtp_card_max": None,
                    "dtp_value_type": "Integer"
                },
                {
                    "dtp_name": "label",
                    "dtp_id": "label",
                    "dtp_card_min": 0,
                    "dtp_card_max": 1,
                    "dtp_value_type": "string"
                }
            ]
        ]
    }
```

---

# Anti-patterns & Design Issues

## Source Code Anti-patterns

### 1. Fragile URL Parsing via `split`
- **Pattern**:
  ```python
  part = datatype_id.split("/", 4)
  orkg_hostname = part[0] + "//" + part[2]
  resource_id = part[4]
  ```
- **Risk**: Raises `IndexError` if input contains fewer than 4 slashes (e.g., `"R758316"` or `"https://orkg.org"`).
- **Remedy**: Use standard library `urllib.parse.urlparse`.

### 2. Recursive Guard Key Inconsistency (Potential Infinite Loop / Redundant Network Requests)
- **Pattern**:
  ```python
  nested_name = info_n["content"][0]["label"]
  if nested_name not in extract_all:
      extractor_function(nested_id)
  ```
- **Risk**: The keys of `extract_all` are normalized via `format_string` (e.g., `"my_template"`), but `nested_name` is verified in its raw/unformatted form (e.g., `"My Template"`). Since `"My Template"` is not in `extract_all`, the condition `nested_name not in extract_all` is evaluated to `True`, triggering redundant extraction or infinite recursion for circular dependencies.
- **Remedy**: Compare normalized keys: `format_string(nested_name) not in extract_all`.

### 3. Tight Coupling & Lack of Dependency Injection
- **Pattern**:
  ```python
  from .request_dtr import request_dtr
  # ...
  info = request_dtr(...)
  ```
- **Risk**: Impedes testability. Testing requires monkey patching/mocking of global/module-level dependencies (`unittest.mock.patch`).
- **Remedy**: Pass a requester function or client object as an optional argument to `extract_orkg`.

### 4. No Error Handling for Network Requests / Schema Structure
- **Pattern**:
  ```python
  info = request_dtr(orkg_hostname + "/api/templates/" + resource_id)
  # ...
  "dt_class": info["target_class"]["id"]
  ```
- **Risk**: Throws unhandled exceptions (`requests.RequestException`, `KeyError`, `TypeError`) if endpoint is offline, returns invalid JSON, or if standard ORKG keys like `target_class` are missing from payload.
- **Remedy**: Add standard `try/except` blocks and schema validation.

### 5. Non-Standard Closure State Mutation
- **Pattern**:
  ```python
  def extract_orkg(datatype_id):
      extract_all = {}
      def extractor_function(resource_id):
          # Mutates extract_all in outer scope
          extract_all[schema_dict["dt_name"]] = list(extracted)
  ```
- **Risk**: Relies on implicit state mutation inside nested functions, which is harder to reason about, test, and adapt for multi-threading.
- **Remedy**: Make `extractor_function` return parsed dictionaries/structures and construct the aggregate dict at the outer level.


## Test Suite Anti-patterns

### 1. Brittle String-Based Assertions on Internal Collections
- **Pattern**:
  ```python
  values = schema["dtreg_test_template2"][1][0].values()
  expected = "dict_values(['property3', 'P160024', 0, None, 'Integer'])"
  self.assertEqual(str(values), expected)
  ```
  ```python
  expected = "dict_keys(['dtreg_test_template2', 'dtreg_test_template1'])"
  self.assertEqual(str(schema.keys()), expected)
  ```
- **Risk**: String representations of `dict_values` and `dict_keys` are implementation-dependent and can vary across Python versions or order of entries, leading to brittle tests.
- **Remedy**: Assert directly on standard collections (lists or sets):
  ```python
  self.assertEqual(list(values), ['property3', 'P160024', 0, None, 'Integer'])
  self.assertEqual(set(schema.keys()), {'dtreg_test_template2', 'dtreg_test_template1'})
  ```
