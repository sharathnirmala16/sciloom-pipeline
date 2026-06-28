#!/usr/bin/env python3
"""
DTREG Metadata Generation Script for Loom Records.

Reads CLAIMS.json and generates independent JSON-LD loom records
for each replicated claim using the Group Comparison data type.

Each record is saved as: dtreg_output_CLAIM_<id>.jsonld
"""
import json
import re
import sys
import os
import platform
import importlib.metadata
from pathlib import Path

from dtreg.load_datatype import load_datatype
from dtreg.to_jsonld import to_jsonld

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CLAIMS_PATH = os.path.join(os.path.dirname(__file__), "..", ".sciloom", "CLAIMS.json")
DATA_CSV = os.path.join(os.path.dirname(__file__),
    "Table_S1._Detailed_information_on_feather_sample_collection_date__location__"
    "source__and_corticosterone_concentrations.csv")

# ePIC DTR schema URIs
DT_DATA_ANALYSIS = "https://doi.org/21.T11969/feeb33ad3e4440682a4d"
DT_GROUP_COMPARISON = "https://doi.org/21.T11969/b9335ce2c99ed87735a6"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _version(pkg: str) -> str:
    """Return installed version of a package, or 'unknown'."""
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


_GROUP_SYNONYMS = {
    "Laysan-Historical": [
        "Laysan-Historical", "historical Laysan", "Laysan-Historical samples",
    ],
    "Laysan-Contemporary": [
        "Laysan-Contemporary", "contemporary Laysan", "Laysan-Contemporary samples",
    ],
    "Midway": ["Midway"],
    "Kure": ["Kure"],
}


def _extract_groups_from_claim(claim_text: str) -> list[str]:
    """
    Dynamically extract group names mentioned in a claim's text.
    Matches known group labels and their synonyms from the study.
    """
    found = []
    for group_name, synonyms in _GROUP_SYNONYMS.items():
        if any(syn.lower() in claim_text.lower() for syn in synonyms):
            found.append(group_name)
    return found if found else ["All groups"]


def _extract_comparison_pair(claim_text: str) -> tuple[str, str] | None:
    """
    For pairwise claims, extract the two groups being compared.
    Returns (group1, group2) or None for omnibus tests.
    """
    found = _extract_groups_from_claim(claim_text)
    if len(found) == 2:
        return (found[0], found[1])
    return None


def _parse_degrees_of_freedom(metrics: str) -> dict:
    """
    Parse degrees of freedom from metrics string.
    e.g. '$F_{3,35} = 7.285$' -> {'df_between': 3, 'df_within': 35}
    """
    result = {}
    # ANOVA F-test pattern: F_{df1, df2}
    m = re.search(r'F_\{(\d+),(\d+)\}', metrics)
    if m:
        result['df_between'] = int(m.group(1))
        result['df_within'] = int(m.group(2))
    return result


def _is_anova_claim(claim_text: str) -> bool:
    """Check if the claim is an omnibus ANOVA (contains F-statistic)."""
    return "F_{" in claim_text or "F(" in claim_text


def _build_output_table(claim: dict, is_anova: bool,
                        comparison_pair: tuple[str, str] | None) -> list[dict]:
    """
    Build the output results table rows dynamically from CLAIMS.json values.
    """
    rows = []
    if is_anova:
        f_val = claim.get("computed_F", 0)
        p_val = claim.get("computed_p", 0)
        df_info = _parse_degrees_of_freedom(claim.get("metrics", ""))
        rows.append({
            "test": "One-way ANOVA",
            "F_statistic": str(round(f_val, 3)),
            "df_between": str(df_info.get("df_between", "")),
            "df_within": str(df_info.get("df_within", "")),
            "p_value": f"{p_val:.6g}",
        })
    else:
        p_val = claim.get("computed_p", 0)
        pair = comparison_pair or ("Group A", "Group B")
        rows.append({
            "test": "Pairwise post-hoc (Fisher's LSD, BH-corrected)",
            "group_1": pair[0],
            "group_2": pair[1],
            "p_value": f"{p_val:.6g}",
        })
    return rows


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------
def generate_loom_record(claim: dict, output_dir: str) -> str:
    """
    Generate a single JSON-LD loom record for a replicated claim.
    Returns the path to the written file.
    """
    claim_id = claim["id"]
    claim_text = claim["claimText"]
    metrics = claim.get("metrics", "")
    is_anova = _is_anova_claim(claim_text)
    comparison_pair = _extract_comparison_pair(claim_text)

    # --- Load dtreg schemas ---
    dt_analysis = load_datatype(DT_DATA_ANALYSIS)
    dt_gc = load_datatype(DT_GROUP_COMPARISON)

    # --- Determine software method label & implementation code ---
    if is_anova:
        method_label = "ols + anova_lm (One-way ANOVA)"
        impl_code = "ols('log_cort ~ C(Group)', data=df).fit(); anova_lm(model, typ=1)"
        method_desc = "One-way ANOVA on log-transformed feather corticosterone across 4 island groups"
    else:
        pair_str = " vs ".join(comparison_pair) if comparison_pair else "groups"
        method_label = f"Pairwise post-hoc Fisher's LSD with BH correction ({pair_str})"
        impl_code = (
            "Fisher's LSD t-tests with Benjamini-Hochberg FDR correction "
            "on log-transformed feather corticosterone"
        )
        method_desc = f"Pairwise comparison: {pair_str}"

    # --- Build targets (group components) ---
    groups = _extract_groups_from_claim(claim_text)
    targets = [dt_gc.component(label=g) for g in groups]

    # --- Build output results table ---
    output_rows = _build_output_table(claim, is_anova, comparison_pair)
    # Create a simple DataFrame-like dict for the output
    import pandas as pd
    df_output = pd.DataFrame(output_rows)

    # --- Build the Data Analysis record ---
    da = dt_analysis.data_analysis(
        label=f"Replication of {claim_id}: {claim_text}",
        has_part=dt_gc.group_comparison(
            label=method_desc,
            executes=dt_gc.software_method(
                label=method_label,
                is_implemented_by=impl_code,
                part_of=dt_gc.software_library(
                    label="statsmodels + scipy",
                    version_info=f"statsmodels {_version('statsmodels')}, scipy {_version('scipy')}",
                    part_of=dt_gc.software(
                        label="Python",
                        version_info=platform.python_version(),
                    ),
                ),
            ),
            targets=targets,
            has_input=dt_gc.data_item(
                label=f"Feather corticosterone data for {claim_id}",
                source_table=pd.DataFrame(),  # empty placeholder; actual data referenced by URL
                comment="Source: Table_S1 feather corticosterone CSV (see source_url)",
            ),
            has_output=dt_gc.data_item(
                label=f"Statistical results for {claim_id}",
                source_table=df_output,
            ),
        ),
    )

    # --- Serialize to JSON-LD ---
    json_ld = to_jsonld(da)

    # --- Write output file ---
    out_path = os.path.join(output_dir, f"dtreg_output_{claim_id}.jsonld")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json_ld)

    return out_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    # Resolve paths
    claims_path = os.path.abspath(CLAIMS_PATH)
    output_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"Reading claims from: {claims_path}")
    with open(claims_path, "r", encoding="utf-8") as f:
        claims = json.load(f)

    replicated = [c for c in claims if c.get("replicated") is True]
    print(f"Found {len(replicated)} replicated claim(s) out of {len(claims)} total.")

    if not replicated:
        print("No replicated claims found. Nothing to generate.")
        return 1

    generated = []
    errors = []
    for claim in replicated:
        cid = claim["id"]
        try:
            path = generate_loom_record(claim, output_dir)
            generated.append((cid, path))
            print(f"  [OK] {cid} -> {os.path.basename(path)}")
        except Exception as exc:
            errors.append((cid, str(exc)))
            print(f"  [FAIL] {cid}: {exc}")

    print(f"\nGenerated {len(generated)} loom record(s).")
    if errors:
        print(f"Errors ({len(errors)}):")
        for cid, err in errors:
            print(f"  {cid}: {err}")

    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
