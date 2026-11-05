"""Produire les tableaux et figures de l'amendement à partir des CSV publics."""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .data import RESULTS

AUDIT = RESULTS / "audit"
TABLES = AUDIT / "tables"
FIGURES = AUDIT / "figures"
MEASURES = ["coverage", "fatal_coverage", "macro_fatal_department_coverage",
            "mean_size", "singleton_rate"]


def read_metrics(period):
    path = AUDIT / period / "metrics.csv"
    frame = pd.read_csv(path if path.exists() else path.with_suffix(".csv.gz"))
    frame["period"] = period
    return frame


def mean_table(frame, keys, measures=MEASURES):
    return frame.groupby(keys, dropna=False)[measures].mean().reset_index()


def build_tables(development, final):
    both = pd.concat([development, final], ignore_index=True)
    mean_table(both, ["period", "method", "budget"]).to_csv(TABLES / "method_summary.csv", index=False)

    regional = both.groupby(["period", "method", "budget"], dropna=False)[[
        "fatal_department_coverage_q10", "fatal_department_coverage_median",
        "fatal_department_coverage_q90", "fatal_department_n_min",
        "fatal_department_n_median", "fatal_department_n_max"]].mean().reset_index()
    regional.to_csv(TABLES / "regional_fatal_summary.csv", index=False)

    rows = []
    for period, original_name, corrected_name in [
        ("development", "source_weighted", "source_weighted_aligned"),
        ("corrected_2025", "source_weighted", "source_weighted_aligned")]:
        original_path = RESULTS / ("development" if period == "development" else "final") / "metrics.csv"
        original = pd.read_csv(original_path)
        corrected = development if period == "development" else final
        old = original[original.method == original_name][MEASURES[0:2] + MEASURES[3:]].mean()
        new = corrected[corrected.method == corrected_name][MEASURES[0:2] + MEASURES[3:]].mean()
        for measure in old.index:
            rows.append({"period": period, "measure": measure, "original": old[measure],
                         "aligned": new[measure], "difference": new[measure] - old[measure]})
    pd.DataFrame(rows).to_csv(TABLES / "density_correction.csv", index=False)

    pilot = pd.read_csv(AUDIT / "development" / "pilot_diagnostics.csv")
    pd.DataFrame([{
        "department_draws": len(pilot),
        "pilot_labels_per_department": pilot.pilot_n.mean(),
        "mean_fatal_labels": pilot.pilot_fatal_n.mean(),
        "zero_fatal_rate": pilot.pilot_zero_fatal.mean(),
        "posterior_absolute_error_raw": pilot.posterior_abs_error_raw.mean(),
        "posterior_absolute_error_smoothed": pilot.posterior_abs_error_smoothed.mean(),
    }]).to_csv(TABLES / "pilot_identification.csv", index=False)

    simulation = pd.read_csv(AUDIT / "simulation" / "summary.csv")
    focus = simulation[
        simulation.condition.isin(["shared_region_effect", "changed_region_effect"])
        & simulation.method.isin(["uniform__department_class", "pilot_variance__department_class",
                                  "oracle_true_variance", "oracle_true_equal_fatal"])
    ]
    focus.to_csv(TABLES / "simulation_mechanisms.csv", index=False)


def plot_tradeoff(final):
    methods = ["uniform__class", "uniform__department_class",
               "pilot_variance__department_class", "proportional__department_class"]
    labels = {"uniform__class": "Classe, uniforme",
              "uniform__department_class": "Département × classe, uniforme",
              "pilot_variance__department_class": "Département × classe, pilot",
              "proportional__department_class": "Département × classe, proportionnelle"}
    colors = ["#3b6fb6", "#009e73", "#d55e00", "#7b4ab5"]
    summary = mean_table(final[final.method.isin(methods)], ["method", "budget"])
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    specifications = [("macro_fatal_department_coverage", "Couverture mortelle\nmacro-départementale"),
                      ("mean_size", "Taille moyenne"), ("singleton_rate", "Proportion de singletons")]
    for axis, (measure, title) in zip(axes, specifications):
        for method, color in zip(methods, colors):
            data = summary[summary.method == method]
            axis.plot(data.budget, data[measure], marker="o", color=color, label=labels[method])
        axis.set_xlabel("Budget total d'étiquettes")
        axis.set_ylabel(title)
        axis.grid(alpha=.25)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="lower center", ncol=2, frameon=False)
    fig.suptitle("BAAC 2025 — analyse corrective postérieure à la publication", fontweight="bold")
    fig.tight_layout(rect=(0, .16, 1, .94))
    fig.savefig(FIGURES / "tradeoff_2025_corrected.png", dpi=180)
    plt.close(fig)


def plot_simulation():
    path = AUDIT / "simulation" / "trials.csv"
    trials = pd.read_csv(path if path.exists() else path.with_suffix(".csv.gz"))
    data = trials[trials.method == "uniform__department_class"]
    conditions = ["shared_region_effect", "changed_region_effect"]
    labels = {"shared_region_effect": "Effet régional partagé",
              "changed_region_effect": "Effet régional changeant"}
    summary = data.groupby(["condition", "budget"])[[
        "macro_fatal_department_coverage", "fatal_department_coverage_min", "mean_size"]].mean().reset_index()
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.5))
    for condition, color in zip(conditions, ["#0072b2", "#d55e00"]):
        part = summary[summary.condition == condition]
        for axis, measure in zip(axes, ["macro_fatal_department_coverage",
                                        "fatal_department_coverage_min", "mean_size"]):
            axis.plot(part.budget, part[measure], marker="o", color=color, label=labels[condition])
    for axis, title in zip(axes, ["Couverture mortelle macro", "Minimum régional mortel", "Taille moyenne"]):
        axis.set_xlabel("Budget simulé")
        axis.set_ylabel(title)
        axis.grid(alpha=.25)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="lower center", ncol=2, frameon=False)
    fig.suptitle("Simulation — stabilité ou changement des effets régionaux", fontweight="bold")
    fig.tight_layout(rect=(0, .12, 1, .93))
    fig.savefig(FIGURES / "simulation_region_effects.png", dpi=180)
    plt.close(fig)


def run():
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    development, final = read_metrics("development"), read_metrics("corrected_2025")
    build_tables(development, final)
    plot_tradeoff(final)
    plot_simulation()


if __name__ == "__main__":
    run()
