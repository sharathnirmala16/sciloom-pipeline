#!/usr/bin/env python3
"""
Replication script for CLAIM-007:
"Mean feather cort was significantly lower in Kure samples than in
 historical Laysan samples."
Expected: Kure: mean±sd = 3.60±2.24 pg/mg vs
          Laysan-Historical: mean±sd = 5.62±2.14 pg/mg (p < 0.05)
"""
import pandas as pd
import numpy as np
from scipy import stats
from statsmodels.formula.api import ols
from statsmodels.stats.anova import anova_lm
from statsmodels.stats.multitest import multipletests
from itertools import combinations
import sys
import json

DATA_PATH = "Table_S1._Detailed_information_on_feather_sample_collection_date__location__source__and_corticosterone_concentrations.csv"
CLAIMS_PATH = "../.sciloom/CLAIMS.json"

def main():
    df = pd.read_csv(DATA_PATH, encoding='latin-1')
    
    # Create group labels
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
    df['log_cort'] = np.log(df['CALC_CONC_SAMPLE_pg.mg'])
    
    # Descriptive stats on raw scale
    kure = df[df['Group'] == 'Kure']['CALC_CONC_SAMPLE_pg.mg']
    hist = df[df['Group'] == 'Laysan-Historical']['CALC_CONC_SAMPLE_pg.mg']
    
    kure_mean = kure.mean()
    kure_sd = kure.std()
    hist_mean = hist.mean()
    hist_sd = hist.std()
    
    print(f"Kure: mean={kure_mean:.2f}, sd={kure_sd:.2f}, n={len(kure)}")
    print(f"Laysan-Historical: mean={hist_mean:.2f}, sd={hist_sd:.2f}, n={len(hist)}")
    
    # Expected values
    exp_kure_mean = 3.60
    exp_kure_sd = 2.24
    exp_hist_mean = 5.62
    exp_hist_sd = 2.14
    
    means_match = (abs(kure_mean - exp_kure_mean) < 0.01 and 
                   abs(kure_sd - exp_kure_sd) < 0.01 and
                   abs(hist_mean - exp_hist_mean) < 0.01 and 
                   abs(hist_sd - exp_hist_sd) < 0.01)
    
    # Post-hoc test: Fisher's LSD with BH correction
    groups_list = ['Laysan-Historical', 'Laysan-Contemporary', 'Midway', 'Kure']
    model = ols('log_cort ~ C(Group)', data=df).fit()
    anova_results = anova_lm(model, typ=1)
    mse = anova_results['mean_sq']['Residual']
    resid_df = int(anova_results['df']['Residual'])
    
    group_data = {g: df[df['Group']==g]['log_cort'].values for g in groups_list}
    
    all_pvals = []
    all_comps = []
    for g1, g2 in combinations(groups_list, 2):
        n1, n2 = len(group_data[g1]), len(group_data[g2])
        mean1, mean2 = group_data[g1].mean(), group_data[g2].mean()
        se = np.sqrt(mse * (1/n1 + 1/n2))
        t_stat = (mean1 - mean2) / se
        p_val = 2 * stats.t.sf(abs(t_stat), resid_df)
        all_pvals.append(p_val)
        all_comps.append((g1, g2))
    
    _, p_corrected, _, _ = multipletests(all_pvals, method='fdr_bh')
    
    # Find Kure vs Laysan-Historical
    p_adj = None
    for i, (g1, g2) in enumerate(all_comps):
        if (g1 == 'Kure' and g2 == 'Laysan-Historical') or \
           (g1 == 'Laysan-Historical' and g2 == 'Kure'):
            p_adj = p_corrected[i]
            break
    
    print(f"\nKure vs Laysan-Historical: adjusted p = {p_adj:.6f}")
    
    p_match = p_adj < 0.05
    
    if means_match and p_match:
        print("\n✓ CLAIM-007 REPLICATED SUCCESSFULLY")
        print(f"  Means/SDs match: {kure_mean:.2f}±{kure_sd:.2f} vs {hist_mean:.2f}±{hist_sd:.2f}")
        print(f"  p = {p_adj:.4f} (p < 0.05)")
        
        with open(CLAIMS_PATH, 'r') as f:
            claims = json.load(f)
        for claim in claims:
            if claim['id'] == 'CLAIM-007':
                claim['replicated'] = True
                claim['replicationError'] = None
                claim['computed_p'] = round(p_adj, 4)
        with open(CLAIMS_PATH, 'w') as f:
            json.dump(claims, f, indent=2)
        print("  CLAIMS.json updated.")
        return True
    else:
        print("\n✗ CLAIM-007 FAILED TO REPLICATE")
        if not means_match:
            print(f"  Means/SDs don't match expected values")
        if not p_match:
            print(f"  p = {p_adj:.4f}, expected p < 0.05")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
