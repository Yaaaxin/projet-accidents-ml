"""Tableaux et figures publics à partir des résultats agrégés sauvegardés."""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import ROOT

SPLITS = {"random_accident": "Aléatoire par accident", "geographic": "Départements réservés"}
FEATURES = {"all": "Toutes", "road_only": "vma + catr", "without_road": "Sans vma/catr"}
MODELS = {"majority": "Majorité", "logistic": "Régression logistique", "forest": "Forêt aléatoire"}


def markdown_table(headers, rows):
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
                     + ["| " + " | ".join(map(str, row)) + " |" for row in rows])


def interval(row, metric):
    return f"{row[metric]:.4f} [{row[metric + '_low']:.4f} ; {row[metric + '_high']:.4f}]"


def render(results_dir=ROOT / "results"):
    results_dir = Path(results_dir)
    metrics = pd.read_csv(results_dir / "metrics.csv")
    differences = pd.read_csv(results_dir / "paired_differences.csv")
    metadata = json.loads((results_dir / "run_metadata.json").read_text(encoding="utf-8"))
    if len(metrics) != 18 or metadata["completed_evaluations"] != 18:
        raise ValueError("Le rapport exige les 18 évaluations terminées")
    figures = results_dir / "figures"
    figures.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharey="row", layout="constrained")
    for col, (split, label) in enumerate(SPLITS.items()):
        for row, (metric, ylabel) in enumerate([("balanced_accuracy", "Balanced accuracy"), ("roc_auc", "ROC-AUC")]):
            ax = axes[row, col]
            for model, offset, color in [("logistic", -0.08, "#0072B2"), ("forest", 0.08, "#D55E00")]:
                subset = metrics[(metrics.split == split) & (metrics.model == model)].set_index("features").loc[list(FEATURES)]
                values = subset[metric].to_numpy()
                errors = np.vstack([values - subset[metric + "_low"], subset[metric + "_high"] - values])
                ax.errorbar(np.arange(3) + offset, values, yerr=errors, fmt="o", color=color,
                            capsize=4, label=MODELS[model])
            ax.axhline(0.5, color="#666666", linestyle="--", linewidth=1, label="Classe majoritaire")
            ax.set_xticks(np.arange(3), list(FEATURES.values()))
            ax.set_ylim(0.47, 1.0)
            ax.set_ylabel(ylabel)
            ax.grid(axis="y", alpha=0.2)
            if row == 0:
                ax.set_title(label)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=3)
    fig.suptitle("Classification par accident — intervalles bootstrap à 95 %")
    fig.savefig(figures / "performance.png", dpi=180)
    fig.savefig(figures / "performance.pdf", metadata={"CreationDate": None})
    plt.close(fig)

    matrices = []
    for _, record in metrics.iterrows():
        matrices.append({"split": record.split, "features": record.features, "model": record.model,
                         "labels": [0, 1], "rows": "observed", "columns": "predicted",
                         "matrix": [[int(record.tn), int(record.fp)], [int(record.fn), int(record.tp)]]})
    (results_dir / "confusion_matrices.json").write_text(json.dumps(matrices, indent=2) + "\n", encoding="utf-8")
    fig, axes = plt.subplots(2, 2, figsize=(9, 7), layout="constrained")
    for i, (split, split_label) in enumerate(SPLITS.items()):
        for j, model in enumerate(["logistic", "forest"]):
            record = metrics[(metrics.split == split) & (metrics.model == model) & (metrics.features == "all")].iloc[0]
            matrix = np.array([[record.tn, record.fp], [record.fn, record.tp]], dtype=int)
            ax = axes[i, j]
            ax.imshow(matrix / matrix.sum(axis=1, keepdims=True), vmin=0, vmax=1, cmap="Blues")
            for (r, c), count in np.ndenumerate(matrix):
                ax.text(c, r, str(count), ha="center", va="center",
                        color="white" if count / matrix[r].sum() > 0.5 else "black")
            ax.set_xticks([0, 1], ["Hors agglo.", "En agglo."])
            ax.set_yticks([0, 1], ["Hors agglo.", "En agglo."])
            ax.set_xlabel("Classe prédite")
            ax.set_ylabel("Classe observée")
            ax.set_title(split_label + "\n" + MODELS[model])
    fig.suptitle("Toutes les variables — effectifs par accident")
    fig.savefig(figures / "confusion.png", dpi=180)
    plt.close(fig)

    sections = ["# Résultats détaillés", "\nRésultats mesurés sur BAAC 2024, avec une observation par accident. "
                f"IC percentile à 95 %, {metadata['config']['bootstrap_replicates']} rééchantillonnages appariés des accidents de test ; modèles fixés."]
    for split, label in SPLITS.items():
        subset = metrics[metrics.split == split]
        rows = [[FEATURES[r.features], MODELS[r.model], interval(r, "balanced_accuracy"),
                 interval(r, "macro_f1"), interval(r, "roc_auc")] for _, r in subset.iterrows()]
        sections.extend(["\n## " + label,
                         f"\nApprentissage : {int(subset.iloc[0].n_train):,} accidents ; test : {int(subset.iloc[0].n_test):,} accidents. Intersection des identifiants : zéro.",
                         "\n" + markdown_table(["Variables", "Modèle", "Balanced accuracy [IC]", "Macro-F1 [IC]", "ROC-AUC [IC]"], rows)])
    selected = differences[differences.comparison.isin(["all/forest - all/logistic", "all/forest - without_road/forest", "all/forest - road_only/forest"])]
    sections += ["\n## Différences appariées", "\nDifférence = premier modèle moins second, sans ajustement pour comparaisons multiples.",
                 "\n" + markdown_table(["Test", "Comparaison", "Métrique", "Différence", "IC à 95 %"],
                     [[SPLITS[r.split], r.comparison, r.metric, f"{r.difference:+.4f}", f"[{r.low:+.4f} ; {r.high:+.4f}]"] for _, r in selected.iterrows()]),
                 "\nVoir `paired_differences.csv` pour toutes les comparaisons, `confusion_matrices.json` pour les 18 matrices et `run_metadata.json` pour l’environnement et les empreintes.",
                 "\nLes IC conditionnent sur les modèles ajustés et le découpage retenu. Ils ne couvrent pas la variabilité du réentraînement ni celle d’autres départements réservés ; les accidents peuvent rester spatialement dépendants."]
    (results_dir / "summary.md").write_text("\n".join(sections) + "\n", encoding="utf-8")
    print("Tableaux, matrices et figures enregistrés dans results/.")


if __name__ == "__main__":
    render()
