# Public API Contract

## Class / Function Signatures

### `request_dtr`
Fetches and deserializes datatype registry (DTR) schema information.

```python
def request_dtr(route: str) -> dict:
    """
    Request an API of a datatype registry to get information about a schema.

    Args:
        route (str): Absolute URL path or endpoint of the DTR API.

    Returns:
        dict: Parsed JSON response payload from the datatype registry.

    Raises:
        requests.exceptions.RequestException: On network failures or timeouts.
        requests.exceptions.JSONDecodeError: If response is not valid JSON.
    """
```

### Dependencies
- `requests >= 2.0.0`

---

# Minimal Working Recipe

```python
from dtreg.request_dtr import request_dtr

# Endpoint path
dtr_endpoint = "https://doi.org/21.T11969/fb2e379f820c6f8f9e82?locatt=view:json"

# Execution
try:
    schema_info = request_dtr(dtr_endpoint)
    print(f"Schema Name: {schema_info.get('name')}")
except Exception as e:
    print(f"Failed to fetch DTR schema: {e}")
```

---

# Anti-Patterns

## Source Implementation Anti-Patterns

### 1. Lack of HTTP Timeout
* **Defect**: `requests.get(route)` omits the `timeout` argument.
* **Risk**: Thread hangs indefinitely if remote endpoint is unresponsive.
* **Remediation**:
  ```python
  # Correct
  requests.get(route, timeout=10)
  ```

### 2. Missing HTTP Status Code Verification
* **Defect**: The response is deserialized (`r.json()`) without checking the HTTP status code first.
* **Risk**: Non-200 responses (e.g. 404, 500) containing HTML or plain-text error messages cause unhandled `JSONDecodeError`.
* **Remediation**:
  ```python
  # Correct
  r = requests.get(route, timeout=10)
  r.raise_for_status()
  return r.json()
  ```

### 3. Lack of Error Handling
* **Defect**: Network-level exceptions (`ConnectionError`, `Timeout`, etc.) propagate directly to the caller without translation or handling.
* **Risk**: Unhandled standard library / requests library errors expose internal implementation details.
* **Remediation**: Wrap the request in `try-except` blocks.

### 4. Absence of Type Annotations
* **Defect**: Function parameters and return values are untyped.
* **Risk**: Static type checkers cannot validate correct usage.
* **Remediation**: Add standard type hints.

## Testing Anti-Patterns

### 1. Code-Under-Test Not Executed
* **Defect**: `tests/request_dtr_tests.py` does not import or call `request_dtr`. It only calls mock helper functions directly.
* **Risk**: The tests pass even if `request_dtr.py` is non-functional or deleted.
* **Evidence (`tests/request_dtr_tests.py` lines 7-14)**:
  ```python
  def test_obtain_epic(self):
      schema = mocked_request_epic(
          'https://doi.org/21.T11969/fb2e379f820c6f8f9e82?locatt=view:json')
      self.assertEqual(schema["name"], 'integer_in_string')
  ```
* **Remediation**: Refactor tests to import and patch `request_dtr`:
  ```python
  from unittest.mock import patch
  from dtreg.request_dtr import request_dtr

  @patch("dtreg.request_dtr.requests.get")
  def test_obtain_epic(self, mock_get):
      mock_get.return_value.json.return_value = {"name": "integer_in_string"}
      # ... call actual request_dtr and assert
  ```

### 2. Rigid / Hardcoded Mocking Helpers
* **Defect**: Mock helper implementations (`mocked_request_epic`, `mocked_request_orkg`) rely on exact string equality check on the URL.
* **Risk**: Brittle tests, hard to scale, cannot easily support dynamic parameter variations.
* **Evidence (`tests/helpers_mock/mocking.py` lines 3-8)**:
  ```python
  if route == "https://doi.org/21.T11969/31483624b5c80014b6c7?locatt=view:json":
      mocked_info = info_epic_1
  # ...
  else:
      print("Please check the URL for mocking")
  ```
* **Remediation**: Use library-based mocking/fixtures (e.g., `requests-mock` or generic unit mock setups).
