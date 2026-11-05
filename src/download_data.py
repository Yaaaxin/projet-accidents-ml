"""Télécharger les ressources officielles sans remplacer un fichier local existant."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download(data_dir=ROOT / "data"):
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    receipt = []
    for record in manifest["files"]:
        target = data_dir / Path(record["path"]).name
        if target.exists():
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != record["sha256"]:
                raise ValueError(f"{target.name} existe avec un SHA-256 différent ; aucun écrasement.")
            print(f"{target.name} : fichier local conforme, conservé.")
            receipt.append({"file": target.name, "sha256": actual, "status": "existing_verified"})
            continue
        request = urllib.request.Request(record["resource_url"], headers={"User-Agent": "projet-accidents-ml/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            content = response.read()
        actual = hashlib.sha256(content).hexdigest()
        if actual != record["sha256"]:
            raise ValueError(f"La ressource {target.name} a changé ; vérifier la version avant utilisation.")
        # Création exclusive : ne pas écraser un fichier apparu pendant le téléchargement.
        with target.open("xb") as output:
            output.write(content)
        receipt.append({"file": target.name, "sha256": actual, "status": "downloaded_verified",
                        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(), "url": record["resource_url"]})
        print(f"{target.name} : téléchargement et SHA-256 vérifiés.")
    (data_dir / "download_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    download(parser.parse_args().data_dir)
