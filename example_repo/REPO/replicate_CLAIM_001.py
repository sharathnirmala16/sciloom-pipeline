#!/usr/bin/env python3
"""
Replication script for CLAIM-001:
"Mean feather cort differed significantly among the samples from Laysan-Historical,
 Laysan-Contemporary, Midway and Kure (F_{3,35} = 7.285, p < 0.001)."
"""
import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm
import sys
import json

# Paths
DATA_PATH = "Table_S1._Detailed_information_on_feather_sample_collection_date__location__source__and_corticosterone_concentrations.csv"
CLAIMS_PATH = "../.sciloom/CLAIMS.json"

def main():
    # Load data
    df = pd.read_csv(DATA_PATH, encoding='latin-1')
    
    # Create group labels matching the paper
    groups = []
    for _, row in df.iterrows():
        loc = row['Location_General']
        date = str(row['Date_Collected'])
        year = int(date.split('/')[-1])
        if loc == 'Laysan' and year == 1903:
            groups.append('Laysan-Historical')
        elif loc == 'Laysan':
            groups.append('Laysan-Contemporary')
        else:
            groups.append(loc)
    df['Group'] = groups
    
    # Log-transform as done in the paper
    df['log_cort'] = np.log(df['CALC_CONC_SAMPLE_pg.mg'])
    
    # One-way ANOVA on log-transformed data
    model = ols('log_cort ~ C(Group)', data=df).fit()
    anova_results = anova_lm(model, typ=1)
    
    f_stat = anova_results['F']['C(Group)']
    p_val = anova_results['PR(>F)']['C(Group)']
    df_between = int(anova_results['df']['C(Group)'])
    df_within = int(anova_results['df']['Residual'])
    
    print(f"ANOVA: F({df_between},{df_within}) = {f_stat:.3f}, p = {p_val:.6f}")
    
    # Expected values from the paper
    expected_f = 7.285
    expected_p_less_than = 0.001
    
    # Verify
    f_match = abs(f_stat - expected_f) < 0.01
    p_match = p_val < expected_p_less_than
    
    if f_match and p_match:
        print("\n✓ CLAIM-001 REPLICATED SUCCESSFULLY")
        print(f"  F({df_between},{df_within}) = {f_stat:.3f} (expected {expected_f})")
        print(f"  p = {p_val:.6f} (expected p < {expected_p_less_than})")
        
        # Update CLAIMS.json
        with open(CLAIMS_PATH, 'r') as f:
            claims = json.load(f)
        for claim in claims:
            if claim['id'] == 'CLAIM-001':
                claim['replicated'] = True
                claim['replicationError'] = None
                claim['computed_F'] = round(f_stat, 3)
                claim['computed_p'] = p_val
        with open(CLAIMS_PATH, 'w') as f:
            json.dump(claims, f, indent=2)
        print("  CLAIMS.json updated.")
        return True
    else:
        print("\n✗ CLAIM-001 FAILED TO REPLICATE")
        print(f"  Computed F={f_stat:.3f}, expected F={expected_f}")
        print(f"  Computed p={p_val:.6f}, expected p<{expected_p_less_than}")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
