"""Vérifier les gels, rôles et comparaisons de l'amendement publié."""
import json
import gzip
import hashlib
from datetime import datetime, timezone

import pandas as pd

from .audit import AUDIT_RESULTS, fingerprint
from .data import BASE, write_json
from .download import digest


def frozen_path(name):
    if name.startswith(("development/", "simulation/")):
        return AUDIT_RESULTS / name
    return BASE / name


def frozen_digest(name):
    path = frozen_path(name)
    if path.exists():
        return digest(path)
    compressed = path.with_suffix(path.suffix + ".gz")
    if compressed.exists():
        return hashlib.sha256(gzip.decompress(compressed.read_bytes())).hexdigest()
    partitions = sorted(path.parent.glob(f"{path.stem}-*{path.suffix}.gz"))
    if partitions:
        parts = [gzip.decompress(part.read_bytes()) for part in partitions]
        header = parts[0].splitlines(keepends=True)[0]
        data = parts[0] + b"".join(part[len(header):] for part in parts[1:])
        return hashlib.sha256(data).hexdigest()
    return None


def run():
    frozen = json.loads((BASE / "audit_freeze.json").read_text(encoding="utf-8"))
    checks = {}
    checks["fingerprint_matches_freeze"] = frozen["fingerprint"] == fingerprint()
    checks["frozen_files_match_sha256"] = all(
        frozen_digest(name) == expected for name, expected in frozen["sha256"].items())

    development_path = AUDIT_RESULTS / "development" / "metrics.csv"
    development = pd.read_csv(development_path if development_path.exists()
                              else development_path.with_suffix(".csv.gz"))
    final = pd.read_csv(AUDIT_RESULTS / "corrected_2025" / "metrics.csv")
    roles_development = json.loads((AUDIT_RESULTS / "development" / "roles.json").read_text(encoding="utf-8"))
    roles_final = json.loads((AUDIT_RESULTS / "corrected_2025" / "roles.json").read_text(encoding="utf-8"))
    checks["development_excludes_2025"] = set(development.year) == {2022, 2023, 2024}
    checks["corrected_phase_only_2025"] = set(final.year) == {2025} and bool(final.post_publication_2025.all())
    checks["no_historical_oracle_in_2025"] = not final.method.str.startswith("oracle_").any()
    checks["roles_disjoint"] = all(item["roles"]["all_roles_disjoint"] for item in roles_development + roles_final)
    checks["geographies_disjoint"] = all(
        item["roles"]["source_target_departments_disjoint"] for item in roles_development + roles_final)
    checks["density_source_aligned_and_independent"] = all(
        item["density_audit"]["source_role"] == "tuning"
        and item["density_audit"]["source_calibration_overlap"] == 0
        and item["density_audit"]["same_source_year_and_departments"]
        for item in roles_development + roles_final)
    comparisons = pd.concat([development, final], ignore_index=True)
    local = comparisons[(comparisons.budget > 0) & comparisons.deployable]
    distinct = local.groupby(["phase", "year", "split", "model", "budget", "seed", "allocation"])[
        "calibration_ids_sha256"].nunique()
    checks["same_local_labels_across_scopes"] = int(distinct.max()) == 1
    checks["same_domain_control_present"] = set(comparisons.phase).issubset(
        set(comparisons[comparisons.method == "same_domain_source_pooled"].phase))
    if (AUDIT_RESULTS / "packed_manifest.json").exists():
        from .audit_pack import verify
        verify()
        checks["packed_results_lossless"] = True
    if not all(checks.values()):
        raise AssertionError({name: value for name, value in checks.items() if not value})
    write_json(AUDIT_RESULTS / "validation.json", {
        "validated_utc": datetime.now(timezone.utc).isoformat(), "checks": checks,
        "development_rows": len(development), "corrected_2025_rows": len(final)})
    print(len(checks), "contrôles réussis")


if __name__ == "__main__":
    run()
