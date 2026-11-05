"""Compresser sans perte les grands résultats publics de l'audit."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from .audit import AUDIT_RESULTS
from .data import write_json
from .download import digest

DIRECT = [
    "development/allocation.csv",
    "development/cells.csv",
    "development/metrics.csv",
    "corrected_2025/cells.csv",
    "corrected_2025/departments.csv",
    "simulation/pilot_diagnostics.csv",
    "simulation/trials.csv",
]
PARTITIONED = {"development/departments.csv": ["2022", "2023", "2024"]}
MANIFEST = AUDIT_RESULTS / "packed_manifest.json"


def compressed(data):
    return gzip.compress(data, compresslevel=9, mtime=0)


def storage_record(path):
    return {"path": path.relative_to(AUDIT_RESULTS).as_posix(), "bytes": path.stat().st_size,
            "sha256": digest(path)}


def reconstruct(logical, records):
    parts = [gzip.decompress((AUDIT_RESULTS / record["path"]).read_bytes()) for record in records]
    if logical in PARTITIONED:
        header = parts[0].splitlines(keepends=True)[0]
        return parts[0] + b"".join(part[len(header):] for part in parts[1:])
    return parts[0]


def pack():
    entries = {}
    for relative in DIRECT:
        source = AUDIT_RESULTS / relative
        if not source.exists():
            raise FileNotFoundError(source)
        data = source.read_bytes()
        target = source.with_suffix(source.suffix + ".gz")
        target.write_bytes(compressed(data))
        entries[relative] = {"uncompressed_bytes": len(data),
                             "uncompressed_sha256": hashlib.sha256(data).hexdigest(),
                             "assembly": "gzip", "storage": [storage_record(target)]}
        source.unlink()

    for relative, years in PARTITIONED.items():
        source = AUDIT_RESULTS / relative
        if not source.exists():
            raise FileNotFoundError(source)
        data = source.read_bytes()
        lines = data.splitlines(keepends=True)
        header, rows = lines[0], lines[1:]
        records = []
        for year in years:
            selected = [line for line in rows if line.split(b",", 3)[1] == year.encode()]
            if not selected:
                raise ValueError(f"Partition vide : {relative}, {year}")
            target = source.with_name(f"{source.stem}-{year}{source.suffix}.gz")
            target.write_bytes(compressed(header + b"".join(selected)))
            records.append(storage_record(target))
        entries[relative] = {"uncompressed_bytes": len(data),
                             "uncompressed_sha256": hashlib.sha256(data).hexdigest(),
                             "assembly": "headers_identiques_puis_lignes_2022_2023_2024",
                             "storage": records}
        source.unlink()
    write_json(MANIFEST, {"format": 1, "compression": "gzip, niveau 9, mtime=0",
                          "lossless": True, "files": entries})
    verify()


def verify():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for logical, record in manifest["files"].items():
        for stored in record["storage"]:
            path = AUDIT_RESULTS / stored["path"]
            if path.stat().st_size != stored["bytes"] or digest(path) != stored["sha256"]:
                raise ValueError(f"Archive altérée : {path}")
        data = reconstruct(logical, record["storage"])
        if len(data) != record["uncompressed_bytes"] or hashlib.sha256(data).hexdigest() != record["uncompressed_sha256"]:
            raise ValueError(f"Reconstruction altérée : {logical}")
    print(len(manifest["files"]), "résultats compressés vérifiés")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["pack", "verify"])
    arguments = parser.parse_args()
    pack() if arguments.action == "pack" else verify()
