# Module: dtreg.helpers

Utility functions for formatting, parsing prefixes, determining cardinality, and generating unique stateful IDs.

## Public API Contract

### `format_string`
Converts a string to lowercase and replaces spaces and hyphens with underscores.
```python
def format_string(string: str) -> str
```
- **Parameters:**
  - `string`: `str` - The input string to format.
- **Returns:**
  - `str` - The formatted string.

### `get_prefix`
Extracts a registry/data prefix from a URL string. Supports specific domains and structures.
```python
def get_prefix(url_string: str) -> str
```
- **Parameters:**
  - `url_string`: `str` - The full URL string containing the identifier.
- **Returns:**
  - `str` - The extracted prefix string.
- **Exceptions:**
  - `UnboundLocalError`: Raised if the URL structure does not match ORKG (`orkg.org` in domain segment) or ePIC (`21.T11969` in path segment).
  - `IndexError`: Raised if the URL string has fewer than 4 segments when split by `/`.

### `specify_cardinality`
Parses a cardinality string and returns min/max limits.
```python
def specify_cardinality(cardinality_string: str) -> dict[str, int | None]
```
- **Parameters:**
  - `cardinality_string`: `str` - A string specifying cardinality (e.g., `"1"`, `"0 - 1"`, `"1 - n"`).
- **Returns:**
  - `dict[str, int | None]` - A dictionary with keys `"min"` and `"max"`.
    - `"min"`: `int`
    - `"max"`: `int` or `None` (for unbounded `"n"` cardinality).
- **Exceptions:**
  - `ValueError`: Raised if parsed components are not integers and not `"n"`.

### `generate_uid`
Factory that returns a stateful closure function for sequential ID generation starting from 1.
```python
from typing import Callable

def generate_uid() -> Callable[[], int]
```
- **Returns:**
  - `Callable[[], int]` - A function that returns a new sequential integer on each invocation.

---

## Minimal Working Recipe

```python
from dtreg.helpers import (
    format_string,
    get_prefix,
    specify_cardinality,
    generate_uid
)

# 1. Format string
formatted = format_string("a-B c")  # "a_b_c"

# 2. Extract Prefix
epic_prefix = get_prefix("https://doi.org/21.T11969/74bc7748b8cd520908bc")  # "https://doi.org/21.T11969/"
orkg_prefix = get_prefix("https://incubating.orkg.org/template/R855534")  # "https://incubating.orkg.org/"

# 3. Parse Cardinality
card_single = specify_cardinality("1")       # {'min': 1, 'max': 1}
card_range = specify_cardinality("0 - 1")    # {'min': 0, 'max': 1}
card_unbound = specify_cardinality("1 - n")  # {'min': 1, 'max': None}

# 4. Generate Stateful Sequential UIDs
next_id = generate_uid()
id_1 = next_id()  # 1
id_2 = next_id()  # 2
```

---

## Common Anti-patterns & Gotchas

### 1. Unbound Variable / Missing Default Case in `get_prefix`
If `url_string` does not match the hardcoded rules (`"orkg.org"` in host or `"21.T11969"` in path), `prefix` remains unbound, throwing `UnboundLocalError`.
- **Source Code:**
  ```python
  def get_prefix(url_string):
      part = url_string.split("/", 4)
      if "orkg.org" in url_string.split("/", 4)[2]:
          prefix = part[0] + "//" + part[2] + "/"
      elif url_string.split("/", 4)[3] == '21.T11969':
          prefix = part[0] + "//" + part[2] + "/" + part[3] + "/"
      return prefix  # UnboundLocalError when both conditions fail
  ```

### 2. Inefficient Multi-splitting of URL
`url_string.split("/", 4)` is evaluated three times instead of reusing the local variable `part`.
- **Source Code:**
  ```python
  part = url_string.split("/", 4)
  if "orkg.org" in url_string.split("/", 4)[2]: ...
  elif url_string.split("/", 4)[3] == '21.T11969': ...
  ```

### 3. Fragile URL Parsing (Index and Formatting Fragility)
`get_prefix` uses hardcoded array offsets. For example, it expects a strict URI format like `scheme://domain/path`. If a URL is missing a schema (e.g. `doi.org/21.T11969/74bc7748b8cd520908bc`), indexing will be misaligned, throwing an `IndexError`.

### 4. Vulnerable Cardinality Parsing (No Input Validation)
`specify_cardinality` does not validate string formats and can raise unhandled `ValueError`.
- **Examples:**
  - `specify_cardinality("invalid")` raises `ValueError: invalid literal for int()`.
  - `specify_cardinality("1 - x")` raises `ValueError: invalid literal for int()`.

### 5. Incomplete Test Coverage (Weak Closure Assertions)
`test_uid` in `tests/helpers_tests.py` only asserts the type of the returned object rather than verifying statefulness and sequential output.
- **Inadequate Test Code:**
  ```python
  def test_uid(self):
      self.assertEqual(str(type(generate_uid())), "<class 'function'>")
  ```
- **Recommended Test Pattern:**
  ```python
  def test_uid_statefulness(self):
      uid_gen = generate_uid()
      self.assertEqual(uid_gen(), 1)
      self.assertEqual(uid_gen(), 2)
  ```
