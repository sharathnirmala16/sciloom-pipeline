#!/usr/bin/env python3
"""
Replication script for CLAIM-002:
"Mean feather cort concentrations were statistically significantly lower in
 Laysan-Historical samples compared with Laysan-Contemporary samples."
Expected: Laysan-Historical: mean±sd = 5.62±2.14 pg/mg (p<0.05) vs
          Laysan-Contemporary: mean±sd = 9.61±4.31 pg/mg
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
    hist = df[df['Group'] == 'Laysan-Historical']['CALC_CONC_SAMPLE_pg.mg']
    cont = df[df['Group'] == 'Laysan-Contemporary']['CALC_CONC_SAMPLE_pg.mg']
    
    hist_mean = hist.mean()
    hist_sd = hist.std()
    cont_mean = cont.mean()
    cont_sd = cont.std()
    
    print(f"Laysan-Historical: mean={hist_mean:.2f}, sd={hist_sd:.2f}, n={len(hist)}")
    print(f"Laysan-Contemporary: mean={cont_mean:.2f}, sd={cont_sd:.2f}, n={len(cont)}")
    
    # Expected values
    exp_hist_mean = 5.62
    exp_hist_sd = 2.14
    exp_cont_mean = 9.61
    exp_cont_sd = 4.31
    
    means_match = (abs(hist_mean - exp_hist_mean) < 0.01 and 
                   abs(hist_sd - exp_hist_sd) < 0.01 and
                   abs(cont_mean - exp_cont_mean) < 0.01 and 
                   abs(cont_sd - exp_cont_sd) < 0.01)
    
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
    
    # Find Laysan-Historical vs Laysan-Contemporary
    p_adj = None
    for i, (g1, g2) in enumerate(all_comps):
        if (g1 == 'Laysan-Historical' and g2 == 'Laysan-Contemporary') or \
           (g1 == 'Laysan-Contemporary' and g2 == 'Laysan-Historical'):
            p_adj = p_corrected[i]
            break
    
    print(f"\nLaysan-Historical vs Laysan-Contemporary: adjusted p = {p_adj:.6f}")
    
    p_match = p_adj < 0.05
    
    if means_match and p_match:
        print("\n✓ CLAIM-002 REPLICATED SUCCESSFULLY")
        print(f"  Means/SDs match: {hist_mean:.2f}±{hist_sd:.2f} vs {cont_mean:.2f}±{cont_sd:.2f}")
        print(f"  p = {p_adj:.4f} (p < 0.05)")
        
        with open(CLAIMS_PATH, 'r') as f:
            claims = json.load(f)
        for claim in claims:
            if claim['id'] == 'CLAIM-002':
                claim['replicated'] = True
                claim['replicationError'] = None
                claim['computed_p'] = round(p_adj, 4)
        with open(CLAIMS_PATH, 'w') as f:
            json.dump(claims, f, indent=2)
        print("  CLAIMS.json updated.")
        return True
    else:
        print("\n✗ CLAIM-002 FAILED TO REPLICATE")
        if not means_match:
            print(f"  Means/SDs don't match expected values")
        if not p_match:
            print(f"  p = {p_adj:.4f}, expected p < 0.05")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
