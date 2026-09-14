"""Smoke-test for submission_readiness calculation functions."""
import sys
sys.path.insert(0, ".")

import pandas as pd
from pages.submission_readiness import (
    validate_csv,
    calculate_readiness,
    module_wise_readiness,
    get_missing_items,
    generate_recommendation,
    build_analysis_table,
    get_ctd_checklist,
    STATUS_PRESENT, STATUS_MISSING, STATUS_NA,
)

# ── 1. Built-in checklist has 30 items across 5 modules ──────────────────────
items = get_ctd_checklist()
assert len(items) == 30, f"Expected 30 items, got {len(items)}"
modules = set(i["Module"] for i in items)
assert modules == {"Module 1", "Module 2", "Module 3", "Module 4", "Module 5"}
print(f"1. Built-in checklist: {len(items)} items across {len(modules)} modules  PASS")

# ── 2. Load and validate the demo CSV ────────────────────────────────────────
df = pd.read_csv("data/demo_ctd_checklist.csv")
df.columns = df.columns.str.strip()
for col in ["Module", "Document", "Status"]:
    df[col] = df[col].str.strip()

errs = validate_csv(df)
assert errs == [], f"Validation errors on demo CSV: {errs}"
print(f"2. Demo CSV validation: {len(df)} rows  PASS")

# ── 3. Readiness score calculation ───────────────────────────────────────────
stats = calculate_readiness(df)
# Demo CSV: 4 Missing, 2 N/A → 28 applicable, 24 present → 85.7%
assert stats["missing"] == 4,          f"Expected 4 missing, got {stats['missing']}"
assert stats["not_applicable"] == 2,   f"Expected 2 N/A, got {stats['not_applicable']}"
assert stats["present"] == 24,         f"Expected 24 present, got {stats['present']}"
assert stats["total_applicable"] == 28,f"Expected 28 applicable, got {stats['total_applicable']}"
expected_pct = round(24 / 28 * 100, 1)
assert stats["score_pct"] == expected_pct, f"Expected {expected_pct}%, got {stats['score_pct']}%"
print(f"3. Readiness score: {stats['score_pct']}% ({stats['present']}/{stats['total_applicable']} present, N/A excluded)  PASS")

# ── 4. Module-wise readiness ──────────────────────────────────────────────────
mod_df = module_wise_readiness(df)
assert len(mod_df) == 5, f"Expected 5 modules, got {len(mod_df)}"
# Module 1 should be 100% (all 4 present)
m1 = mod_df[mod_df["Module"] == "Module 1"].iloc[0]
assert m1["Readiness_Pct"] == 100.0, f"Module 1 should be 100%, got {m1['Readiness_Pct']}"
print(f"4. Module-wise readiness: 5 modules calculated, Module 1 = {m1['Readiness_Pct']}%  PASS")

# ── 5. Missing items ──────────────────────────────────────────────────────────
missing = get_missing_items(df)
assert len(missing) == 4, f"Expected 4 missing items, got {len(missing)}"
missing_docs = set(missing["Document"].tolist())
assert "Process validation data" in missing_docs
assert "Safety study reports"    in missing_docs
print(f"5. Missing items: {len(missing)} identified  PASS")

# ── 6. Recommendation lookup ──────────────────────────────────────────────────
rec = generate_recommendation("Process validation data")
assert "validation" in rec.lower(), f"Unexpected recommendation: {rec}"
rec2 = generate_recommendation("Stability data (drug product)")
assert "stability" in rec2.lower(), f"Unexpected recommendation: {rec2}"
# Fallback for unknown document
rec3 = generate_recommendation("Some completely unknown document xyz")
assert "ICH M4" in rec3, f"Fallback recommendation missing ICH M4: {rec3}"
print(f"6. Recommendation lookup: keyword match and fallback  PASS")

# ── 7. Analysis table has Recommendation column ───────────────────────────────
analysis = build_analysis_table(df)
assert "Recommendation" in analysis.columns
missing_recs = analysis[analysis["Status"] == STATUS_MISSING]["Recommendation"]
assert missing_recs.str.len().gt(10).all(), "All missing items should have non-trivial recommendations"
print(f"7. Analysis table: {len(analysis)} rows, Recommendation column present  PASS")

# ── 8. Invalid CSV validation ─────────────────────────────────────────────────
bad_df = pd.DataFrame({"Module": ["M1"], "Document": ["X"], "Status": ["BadValue"]})
errs2 = validate_csv(bad_df)
assert len(errs2) > 0, "Should have caught invalid status value"
print(f"8. Invalid CSV validation: caught bad status value  PASS")

# ── 9. All-NA edge case → score = 0% with 0 applicable ───────────────────────
na_df = pd.DataFrame({
    "Module": ["Module 1"] * 3,
    "Document": ["Doc A", "Doc B", "Doc C"],
    "Status": [STATUS_NA, STATUS_NA, STATUS_NA],
})
na_stats = calculate_readiness(na_df)
assert na_stats["score_pct"] == 0.0
assert na_stats["total_applicable"] == 0
print(f"9. All-N/A edge case: score={na_stats['score_pct']}%, applicable={na_stats['total_applicable']}  PASS")

print()
print("All 9 tests passed.")
print()
print("Demo checklist score breakdown:")
for _, row in mod_df.iterrows():
    print(f"  {row['Module']}: {row['Readiness_Pct']}% ({row['Present']}/{row['Total_Applicable']} applicable)")
