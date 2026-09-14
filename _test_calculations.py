"""Quick smoke-test for signal_detection calculation functions."""
import sys
sys.path.insert(0, ".")

import pandas as pd
from pages.signal_detection import (
    validate_dataframe,
    build_contingency,
    calculate_prr,
    calculate_chi2,
    meets_screening_criteria,
    run_signal_sweep,
)

df = pd.read_csv("data/demo_adverse_events.csv")
df.columns = df.columns.str.strip()
df["Drug"]          = df["Drug"].str.strip()
df["Adverse_Event"] = df["Adverse_Event"].str.strip()

# 1. Validation
errors = validate_dataframe(df)
assert errors == [], f"Unexpected validation errors: {errors}"
print("1. Validation:                   PASS")

# 2. Contingency table — Atorvastatin/Myopathy: a=5 in demo data
ct = build_contingency(df, "Atorvastatin", "Myopathy")
assert ct["a"] == 5, f"a should be 5, got {ct['a']}"
print(f"2. Contingency (Atorvastatin/Myopathy): a={ct['a']} b={ct['b']} c={ct['c']} d={ct['d']}  PASS")

# 3. PRR > 2 for a known strong signal pair
prr = calculate_prr(ct["a"], ct["b"], ct["c"], ct["d"])
assert prr is not None and prr > 2, f"PRR should be > 2, got {prr}"
print(f"3. PRR (Atorvastatin/Myopathy):  {prr:.4f}  PASS")

# 4. Chi-square > 4 for same pair
chi2 = calculate_chi2(ct["a"], ct["b"], ct["c"], ct["d"])
assert chi2 is not None and chi2 > 4, f"Chi2 should be > 4, got {chi2}"
print(f"4. Chi2 (Atorvastatin/Myopathy): {chi2:.4f}  PASS")

# 5. Zero-division safety — Warfarin/Bleeding has c=0 (only drug with that event)
ct0   = build_contingency(df, "Warfarin", "Bleeding")
prr0  = calculate_prr(ct0["a"], ct0["b"], ct0["c"], ct0["d"])
chi20 = calculate_chi2(ct0["a"], ct0["b"], ct0["c"], ct0["d"])
# c=0 → PRR must return None, not crash
assert prr0 is None, f"PRR should be None when c=0, got {prr0}"
print(f"5. Zero-div safety (c=0, Warfarin/Bleeding): PRR={prr0} Chi2={chi20}  PASS")

# 6. meets_screening_criteria — should be False for None PRR
assert meets_screening_criteria(0, None, None) is False
print("6. Screening criteria w/ None:   PASS")

# 7. Full automated sweep
results = run_signal_sweep(df)
n_signals = int(results["Signal_Status"].str.startswith("⚠️").sum())
print(f"7. Signal sweep: {len(results)} pairs analysed, {n_signals} potential signals  PASS")

print()
print("Top 5 pairs by PRR:")
top5 = results[["Drug", "Adverse_Event", "a", "PRR", "Chi_Square", "Signal_Status"]].head(5)
top5["Signal_Status"] = top5["Signal_Status"].str.replace("⚠️", "[!]").str.replace("✅", "[ok]")
print(top5.to_string(index=False))
