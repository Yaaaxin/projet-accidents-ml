"""Tableaux, figures et rapport français à partir des résultats agrégés."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import BASE, RESULTS, write_json
from .download import digest

FIGURES = RESULTS / "figures"
METRICS = ["coverage", "fatal_coverage", "mean_size", "singleton_rate", "empty_rate",
           "average_precision", "brier", "macro_department_coverage", "min_department_coverage",
           "departments_below_90", "fatal_cells_infinite"]
LABELS = {"proportional": "Proportionnelle", "uniform": "Uniforme",
          "pilot_variance": "Pilot–variance", "source_pooled": "Source pooled",
          "source_class": "Source par classe", "source_weighted": "Source pondérée"}
COLORS = {"proportional": "#4472C4", "uniform": "#ED7D31", "pilot_variance": "#70AD47"}


def f(value, digits=3):
    return f"{value:.{digits}f}".replace(".", ",")


def method_row(frame, method, budget):
    row = frame[(frame.method == method) & (frame.budget == budget)]
    return {name: row[name].mean() for name in METRICS if name in row}


def paired(frame, phase):
    keys = ["year", "split", "model", "budget", "seed"]
    candidate = frame[(frame.method == "pilot_variance") & (frame.budget > 0)]
    rows = []
    for reference in ["uniform", "proportional"]:
        merged = candidate.merge(frame[frame.method == reference], on=keys, suffixes=("_candidate", "_reference"))
        for budget in sorted(merged.budget.unique()):
            part = merged[merged.budget == budget]
            for metric in ["coverage", "fatal_coverage", "mean_size", "singleton_rate",
                           "fatal_cells_infinite", "departments_below_90"]:
                delta = part[metric + "_candidate"] - part[metric + "_reference"]
                rows.append({"phase": phase, "reference": reference, "budget": budget, "metric": metric,
                             "n_paires": len(delta), "difference_moyenne": delta.mean(),
                             "difference_mediane": delta.median(), "minimum": delta.min(), "maximum": delta.max(),
                             "difference_positive_n": int((delta > 0).sum())})
    return rows


def aggregate(frame, phase):
    rows = []
    for (model, method, budget), part in frame.groupby(["model", "method", "budget"]):
        record = {"phase": phase, "model": model, "method": method, "budget": budget, "n": len(part)}
        for metric in METRICS:
            if metric in part:
                record.update({metric + "_mean": part[metric].mean(), metric + "_std": part[metric].std(),
                               metric + "_min": part[metric].min(), metric + "_max": part[metric].max()})
        rows.append(record)
    return rows


def figures(final):
    FIGURES.mkdir(parents=True, exist_ok=True)
    local = final[final.budget > 0]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    specs = [("fatal_coverage", "Couverture mortelle", (.88, 1.01)),
             ("mean_size", "Taille moyenne", (1.45, 2.0)),
             ("singleton_rate", "Part d'ensembles singleton", (0, .55))]
    classwise = final[final.method == "source_class"]
    for ax, (metric, title, ylim) in zip(axes, specs):
        for policy in ["proportional", "uniform", "pilot_variance"]:
            stats = local[local.method == policy].groupby("budget")[metric].agg(["mean", "min", "max"])
            ax.plot(stats.index, stats["mean"], marker="o", color=COLORS[policy], label=LABELS[policy])
            ax.fill_between(stats.index, stats["min"], stats["max"], color=COLORS[policy], alpha=.12)
        ax.axhline(classwise[metric].mean(), color="#555555", linestyle="--", label="Source par classe")
        ax.set(title=title, xlabel="Budget total d'étiquettes", ylim=ylim)
        ax.grid(alpha=.25)
    axes[0].set_ylabel("Moyenne sur modèles, découpages et tirages")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("BAAC 2025 — budget, couverture et pouvoir discriminant")
    fig.tight_layout(rect=(0, .12, 1, .94))
    for suffix in ["png", "pdf"]:
        fig.savefig(FIGURES / f"budget_tradeoff.{suffix}", dpi=180, bbox_inches="tight")
    plt.close(fig)

    baselines = final[final.budget == 0].groupby("method")[["coverage", "fatal_coverage", "mean_size"]].mean()
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.8))
    order = ["source_pooled", "source_weighted", "source_class"]
    for ax, metric, title in zip(axes, ["coverage", "fatal_coverage", "mean_size"],
                                 ["Couverture globale", "Couverture mortelle", "Taille moyenne"]):
        values = baselines.reindex(order)[metric]
        ax.bar(range(3), values, color=["#A5A5A5", "#5B9BD5", "#70AD47"])
        ax.set_xticks(range(3), ["Pooled", "Pondérée", "Par classe"], rotation=18)
        ax.set_title(title)
        ax.grid(axis="y", alpha=.25)
        for i, value in enumerate(values):
            ax.text(i, value + .02, f(value, 2), ha="center", fontsize=9)
    axes[0].set_ylim(0, 1.05); axes[1].set_ylim(0, 1.05); axes[2].set_ylim(0, 1.75)
    fig.suptitle("BAAC 2025 — références sans étiquette cible")
    fig.tight_layout(rect=(0, 0, 1, .92))
    for suffix in ["png", "pdf"]:
        fig.savefig(FIGURES / f"source_baselines.{suffix}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def simulation_clean():
    trials = pd.read_csv(RESULTS / "simulation_trials.csv")
    measures = ["coverage", "fatal_coverage", "mean_size", "singleton_rate", "fatal_cells_infinite"]
    summary = trials.groupby(["condition", "method", "budget"])[measures].agg(["mean", "std"]).reset_index()
    summary.columns = ["_".join(filter(None, map(str, col))) for col in summary.columns]
    summary.to_csv(RESULTS / "simulation_summary_clean.csv", index=False)
    return summary


def markdown(dev, final, pair):
    source = {m: method_row(final, m, 0) for m in ["source_pooled", "source_weighted", "source_class"]}
    local = {(m, b): method_row(final, m, b) for m in ["proportional", "uniform", "pilot_variance"]
             for b in [500, 1000, 2000]}
    dev_pair = pair[(pair.phase == "development") & (pair.reference == "uniform")]
    fin_pair = pair[(pair.phase == "final") & (pair.reference == "uniform")]
    def all_budget_delta(frame, metric):
        return frame.groupby("metric").get_group(metric).difference_moyenne.mean()
    regions = pd.read_csv(RESULTS / "final/departments.csv")
    populations = regions[(regions.method == "source_class") & (regions.model == "logistic")].drop_duplicates(["split", "department"])
    unknown = final[["split", "unknown_test_excluded"]].drop_duplicates().unknown_test_excluded.sum()
    lines = [
        "# Rapport research-v2", "",
        "## Question et protocole", "",
        "Cette extension étudie la classification d'un accident corporel enregistré comme mortel, sous transfert vers une nouvelle année et des départements absents de l'apprentissage. Elle demande comment répartir un budget d'étiquettes locales entre départements pour couvrir la classe mortelle et les régions tout en conservant des ensembles discriminants. Elle combine des méthodes connues ; elle ne revendique pas d'innovation algorithmique.", "",
        "Le protocole a été fixé avec les années 2019–2024, puis gelé avant l'ouverture des étiquettes 2025. Trois découpages de vingt départements, deux modèles et trois graines d'acquisition sont conservés. Les résultats locaux ci-dessous moyennent donc 18 essais par budget et politique (3 découpages × 2 modèles × 3 graines).", "",
        "## Résultats 2025", "",
        "### Sans étiquette cible", "",
        "| Méthode | Couverture | Couverture mortelle | Taille moyenne | Singleton | PR-AUC | Brier |", "|---|---:|---:|---:|---:|---:|---:|"
    ]
    for method in ["source_pooled", "source_weighted", "source_class"]:
        r = source[method]
        lines.append(f"| {LABELS[method]} | {f(r['coverage'])} | {f(r['fatal_coverage'])} | {f(r['mean_size'])} | {f(r['singleton_rate'])} | {f(r['average_precision'])} | {f(r['brier'])} |")
    lines += ["", "Les méthodes pooled et pondérée atteignent une couverture globale proche de 0,9 mais une couverture mortelle nulle dans les six scénarios modèle × découpage. Cette défaillance est compatible avec une garantie marginale dominée par la classe non mortelle. L'utilisation des seules caractéristiques cibles pour estimer des poids ne corrige pas le problème. La calibration source par classe atteint une couverture mortelle moyenne de " + f(source['source_class']['fatal_coverage']) + " avec une taille moyenne de " + f(source['source_class']['mean_size']) + ".", "",
              "### Étiquettes locales limitées", "",
              "| Allocation | Budget | Couverture | Couverture mortelle | Taille moyenne | Singleton | Cellules mortelles à seuil infini |", "|---|---:|---:|---:|---:|---:|---:|"]
    for budget in [500, 1000, 2000]:
        for method in ["proportional", "uniform", "pilot_variance"]:
            r = local[(method, budget)]
            lines.append(f"| {LABELS[method]} | {budget} | {f(r['coverage'])} | {f(r['fatal_coverage'])} | {f(r['mean_size'])} | {f(r['singleton_rate'])} | {f(r['fatal_cells_infinite'], 1)} |")
    lines += ["", "À budget 500, la couverture mortelle vaut 1, mais presque toutes les cellules régionales mortelles ont un seuil infini : la classe mortelle est incluse par défaut et les ensembles sont proches de deux étiquettes. À budget 2000, la taille moyenne tombe entre " + f(min(local[(m, 2000)]['mean_size'] for m in ['proportional','uniform','pilot_variance'])) + " et " + f(max(local[(m, 2000)]['mean_size'] for m in ['proportional','uniform','pilot_variance'])) + ", tandis que la couverture mortelle reste entre " + f(min(local[(m, 2000)]['fatal_coverage'] for m in ['proportional','uniform','pilot_variance'])) + " et " + f(max(local[(m, 2000)]['fatal_coverage'] for m in ['proportional','uniform','pilot_variance'])) + ". Ce gain de couverture sur la référence source par classe est payé par des ensembles nettement plus grands.", "",
              "![Compromis budget–couverture–taille](figures/budget_tradeoff.png)", "",
              "### Hypothèse d'allocation", "",
              "Sur 2019–2024, la règle pilot–variance comparée à l'uniforme donne en moyenne " + f(all_budget_delta(dev_pair, 'coverage'), 4) + " de couverture, " + f(all_budget_delta(dev_pair, 'fatal_coverage'), 4) + " de couverture mortelle et " + f(all_budget_delta(dev_pair, 'mean_size'), 4) + " de taille. En 2025, les différences correspondantes sont " + f(all_budget_delta(fin_pair, 'coverage'), 4) + ", " + f(all_budget_delta(fin_pair, 'fatal_coverage'), 4) + " et " + f(all_budget_delta(fin_pair, 'mean_size'), 4) + ". Elles changent de signe selon les budgets, modèles, régions et tirages. La règle candidate n'apporte donc pas de gain stable.", "",
              "Par rapport à l'allocation proportionnelle en 2025, la règle candidate réduit en moyenne d'une unité le nombre de cellules mortelles à seuil infini, mais sa couverture mortelle diminue de 0,0046 et sa taille augmente de 0,0092. Ce compromis n'établit pas une amélioration.", "",
              "## Hétérogénéité régionale et stabilité", "",
              f"Les trois découpages 2025 comprennent {len(populations)} couples découpage–département. {int((populations.fatal_n < 20).sum())} ont moins de vingt accidents mortels dans le test et {int((populations.fatal_n == 0).sum())} n'en a aucun. Les couvertures mortelles départementales de ces petites cellules sont descriptives. Les intervalles de chaque essai rééchantillonnent les départements entiers, mais les trois découpages se recouvrent.", "",
              f"Aucune étiquette test 2025 n'était indéterminée dans les départements évalués ({int(unknown)} exclusions sur les trois découpages). Les étiquettes indéterminées restent possibles dans les pools d'adaptation et leur acquisition est comptée dans le budget.", "",
              "Le modèle de gradient boosting a une PR-AUC moyenne légèrement supérieure à la logistique en 2025. Ces valeurs dépassent la prévalence de la classe mortelle, mais restent faibles en valeur absolue : les probabilités discriminent modestement la classe rare. L'étude des ensembles porte sur la couverture ; elle ne transforme pas ce niveau de discrimination en prédiction causale ou opérationnelle.", "",
              "## Simulation contrôlée", "",
              "Sous échangeabilité, les méthodes conformes atteignent en moyenne le niveau visé ou deviennent conservatrices dans les petites cellules. Le scénario de rupture entre pool d'adaptation et test fait chuter la couverture locale à mesure que les seuils deviennent moins conservateurs : la grande taille des ensembles à faible budget peut masquer cette rupture. Les effets régionaux communs augmentent aussi la variabilité. Ces expériences valident les cas limites de l'implémentation ; elles ne prouvent pas les hypothèses sur BAAC.", "",
              "## Conclusion", "",
              "La question pratique n'est pas résolue par une allocation sophistiquée dans ce régime. Les cellules département × décès sont trop rares pour qu'un budget de 500 ou 1000 produise souvent des seuils informatifs. À 2000, les ensembles commencent à se contracter, mais la règle issue du pilot ne surpasse ni l'uniforme ni la proportionnelle de façon stable. La calibration source par classe offre ici le compromis le plus compact, avec une couverture mortelle proche de la cible plutôt qu'excessivement conservatrice.", "",
              "Ces conclusions valent pour un partage rétrospectif au sein de BAAC 2025 et pour les départements fixés. Elles supposent une stabilité intradépartement entre adaptation et test qui n'est pas démontrée, ignorent les décès ou usagers non enregistrés, et ne généralisent pas automatiquement à 2026. Les variables décrivent des associations prédictives ; aucune importance de modèle n'est interprétée comme cause d'un décès.", "",
              "## Fichiers de preuve", "",
              "- [Protocole gelé](../protocol.md), [gel et empreintes](../freeze.json), [théorie](../theory.md) et [comparaison bibliographique](../literature.md).",
              "- [Métriques 2025](final/metrics.csv), [résultats régionaux](final/departments.csv), [validation 2019–2024](development/metrics.csv), [comparaisons appariées](paired_allocation.csv) et [simulation](simulation_summary_clean.csv).",
              "- [Audit des données avant gel](data_audit_before_freeze.json), [manifeste](../data_manifest.json), [partitions sans identifiants](../partitions.json) et [preuve d'ouverture finale](final_access_receipt.json).", ""]
    (RESULTS / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    phases = {name: pd.read_csv(RESULTS / name / "metrics.csv") for name in ["development", "final"]}
    summaries, pairs = [], []
    for phase, frame in phases.items():
        frame.insert(0, "phase", phase)
        summaries.extend(aggregate(frame, phase))
        pairs.extend(paired(frame, phase))
    pd.DataFrame(summaries).to_csv(RESULTS / "method_summary.csv", index=False)
    pair = pd.DataFrame(pairs)
    pair.to_csv(RESULTS / "paired_allocation.csv", index=False)
    simulation_clean()
    figures(phases["final"])
    markdown(phases["development"], phases["final"], pair)
    write_json(RESULTS / "report_metadata.json", {"inputs_sha256": {
        str(p.relative_to(BASE)): digest(p) for p in [RESULTS / "development/metrics.csv",
        RESULTS / "final/metrics.csv", RESULTS / "final/departments.csv", RESULTS / "simulation_trials.csv"]},
        "reported_trials": sum(len(frame) for frame in phases.values()), "individual_predictions_published": False})
    print("Rapport, tableaux et figures créés.")


if __name__ == "__main__":
    main()
