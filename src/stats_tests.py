"""
Statistical tests on the SQL outputs (writes output/tables/stats_tests.csv).

1. Recommender lift: Wilcoxon signed-rank on per-user watch ratio (recommended vs every video shown),
   plus a bootstrap 95% CI for the mean relative lift
2. Video length vs completion: Spearman correlation at video level and Kruskal-Wallis across length buckets
3. Activity level: Mann-Whitney U on daily watch minutes, full_active vs middle_active users
4. Social ties: Spearman correlation between number of friends and daily watch minutes
5. Ads vs normal videos: chi-square on likes per play
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def run_tests(out: Path):
    t = lambda n: pd.read_csv(out / "tables" / f"{n}.csv")
    rows = []

    ul = t("user_lift").dropna()
    if len(ul) >= 10:
        w = stats.wilcoxon(ul.rec_wr, ul.all_wr)  # two-sided
        rng = np.random.default_rng(0)
        rel = ul.rec_wr.to_numpy() / ul.all_wr.to_numpy() - 1
        boots = [rng.choice(rel, len(rel)).mean() for _ in range(2000)]
        lo, hi = np.percentile(boots, [2.5, 97.5])
        rows.append(("Recommended feed vs every-video watch ratio, same users (Wilcoxon signed-rank, two-sided)",
                     f"{ul.rec_wr.mean():.3f} vs {ul.all_wr.mean():.3f} ({len(ul)} users)", w.pvalue,
                     f"mean lift {rel.mean():+.1%} (95% CI {lo:+.1%} to {hi:+.1%}); "
                     f"{(rel > 0).mean():.0%} of users higher"))

    vs = t("video_stats_export")
    rho, p = stats.spearmanr(vs.dur_s, vs.completion_rate)
    rows.append(("Video length vs completion rate, per video (Spearman)", f"{len(vs):,} videos", p, f"rho = {rho:.2f}"))
    groups = [g.completion_rate.to_numpy() for _, g in vs.groupby("dur_bucket") if len(g) >= 5]
    if len(groups) >= 2:
        h, p = stats.kruskal(*groups)
        rows.append(("Completion rate differs across length buckets (Kruskal-Wallis)", f"{len(groups)} buckets", p,
                     f"H = {h:.0f}"))

    us = t("user_stats_export")
    a = us[us.user_active_degree == "full_active"].watch_min_per_active_day
    b = us[us.user_active_degree == "middle_active"].watch_min_per_active_day
    if len(a) >= 5 and len(b) >= 5:
        u = stats.mannwhitneyu(a, b, alternative="two-sided")
        rows.append(("Daily watch minutes: full_active vs middle_active users (Mann-Whitney U, two-sided)",
                     f"median {a.median():.1f} vs {b.median():.1f} min", u.pvalue,
                     f"rank-biserial r = {2 * u.statistic / (len(a) * len(b)) - 1:.2f}"))
    f = us.dropna(subset=["friend_user_num"])
    rho, p = stats.spearmanr(f.friend_user_num, f.watch_min_per_active_day)
    rows.append(("Friends vs daily watch minutes, per user (Spearman)", f"{len(f):,} users", p, f"rho = {rho:.2f}"))

    ft = t("funnel_by_type").set_index("video_type")
    if {"AD", "NORMAL"} <= set(ft.index):
        table = [[ft.likes["AD"], ft.plays["AD"] - ft.likes["AD"]],
                 [ft.likes["NORMAL"], ft.plays["NORMAL"] - ft.likes["NORMAL"]]]
        chi2, p, _, _ = stats.chi2_contingency(table)
        rows.append(("Likes per play: ads vs normal videos (chi-square)",
                     f"{ft.likes_per_1k['AD']:.1f} vs {ft.likes_per_1k['NORMAL']:.1f} per 1k plays", p,
                     f"ratio {ft.likes_per_1k['AD'] / ft.likes_per_1k['NORMAL']:.2f}x"))

    res = pd.DataFrame(rows, columns=["test", "compared", "p_value", "effect"])
    res["significant_at_5pct"] = res.p_value < .05
    res.to_csv(out / "tables" / "stats_tests.csv", index=False, encoding="utf-8")
    for r in res.itertuples():
        print(f"  {r.test[:70]:<70} p={r.p_value:.2g}")
    return res


if __name__ == "__main__":
    run_tests(Path(__file__).resolve().parents[1] / "output")
