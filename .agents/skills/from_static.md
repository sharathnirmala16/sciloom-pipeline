# Module: dtreg.from_static

## Public API Contract

### Function: `from_static`

```python
def from_static(datatype_id: str) -> dict | None:
    """
    Get schema information from static files.

    Args:
        datatype_id (str): A schema identifier (expected to be an absolute URI with at least 4 slashes, e.g., HTTPS URL).

    Returns:
        dict | None: The requested schema information as parsed JSON, or None if not found in static files.

    Raises:
        IndexError: If datatype_id contains fewer than 4 slashes (e.g., "3df63b7acb0522da685d").
    """
```

## Minimal Working Recipe

```python
from dtreg.from_static import from_static

# Fetch schema from static JSON resource
schema = from_static("https://doi.org/21.T11969/3df63b7acb0522da685d")

if schema is not None:
    print("Schema loaded:", schema)
else:
    print("Schema not found in static resources.")
```

## Anti-Patterns & Risks

### 1. `IndexError` on Raw/Short Identifiers
- **Source**: `id = datatype_id.split("/", 4)[4]`
- **Risk**: Assumes the identifier always contains at least four slashes (such as a full URL `https://doi.org/...`). If a caller passes a raw suffix (e.g., `"3df63b7acb0522da685d"`), it raises an unhandled `IndexError: list index out of range`.

### 2. Linear Scan of Resource Directory
- **Source**: `for f in files("dtreg.data").iterdir():`
- **Risk**: Performs an $O(N)$ linear scan over all static files in the package directory on every function call. This does not scale well if the number of static schemas grows.

### 3. Partial/Fuzzy Stem Match Collision
- **Source**: `if id in f.stem:`
- **Risk**: Matches using substring containment (`in`) instead of exact name equality. A short or generic `id` could falsely match multiple file stems (e.g., `"abc"` matches `"123_abc_456.json"` and `"abc_xyz.json"`), returning whatever file happens to be processed last in the loop.

### 4. Redundant Loop Continuation
- **Source**: No `break` statement inside the loop after matching and parsing.
- **Risk**: Even after finding and loading the correct schema, the function continues iterating through all remaining files in the directory.
