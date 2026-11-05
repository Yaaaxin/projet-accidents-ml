"""Acquisition des ressources officielles ; aucune lecture des étiquettes."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research_v2"
RAW = ROOT / "data/raw/research_v2"
CATALOG = "https://www.data.gouv.fr/api/1/datasets/53698f4ca3a729239d2036df/"


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def acquire():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest_path = BASE / "data_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        with urlopen(CATALOG, timeout=120) as response:
            catalog = json.load(response)
        records = []
        for year in range(2019, 2026):
            for kind, prefixes in [("caracteristiques", ("caract", "carct")),
                                   ("lieux", ("lieux",)), ("usagers", ("usagers",))]:
                matches = [r for r in catalog["resources"]
                           if r["title"].lower().startswith(prefixes)
                           and str(year) in r["title"] and r["format"].lower() == "csv"]
                if len(matches) != 1:
                    raise ValueError(f"Ressource ambiguë : {year}/{kind}")
                r = matches[0]
                records.append({"year": year, "table": kind, "resource_id": r["id"],
                                "url": r["url"], "catalog_checksum": r.get("checksum"),
                                "catalog_size": r.get("filesize"),
                                "resource_modified": r.get("last_modified"),
                                "path": f"data/raw/research_v2/{kind}-{year}.csv"})
        dictionaries = [r for r in catalog["resources"] if r["id"] in
                        ["8ef4c2a3-91a0-4d98-ae3a-989bde87b62a",
                         "21e46f4e-fa29-40bb-9ec8-905e41e041aa"]]
        for r in dictionaries:
            records.append({"table": "dictionary", "resource_id": r["id"], "url": r["url"],
                            "catalog_checksum": r.get("checksum"),
                            "path": f"data/raw/research_v2/dictionary-{r['id']}.pdf"})
        manifest = {"catalog": CATALOG, "license_catalog": catalog["license"],
                    "original_download_date_coursework": "inconnue",
                    "files": records}
    for record in manifest["files"]:
        path = ROOT / record["path"]
        if not path.exists():
            with urlopen(record["url"], timeout=180) as response, path.open("wb") as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    output.write(chunk)
            record.setdefault("downloaded_utc", datetime.now(timezone.utc).isoformat())
        actual = digest(path)
        if record.get("sha256") and actual != record["sha256"]:
            raise ValueError(f"SHA-256 modifié : {path.name}")
        checksum = record.get("catalog_checksum") or {}
        if checksum.get("type") and checksum.get("value"):
            if digest(path, checksum["type"]) != checksum["value"]:
                raise ValueError(f"Empreinte du catalogue incorrecte : {path.name}")
            record["catalog_checksum_verified"] = True
        else:
            record["catalog_checksum_verified"] = False
        record.update(sha256=actual, bytes=path.stat().st_size)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path.name, record["bytes"], flush=True)


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    acquire()
