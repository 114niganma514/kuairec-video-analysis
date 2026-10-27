"""
Reads output/tables/*.csv -> writes output/charts/*.png and output/report.md
Can be run on its own after the SQL step: python src/make_report.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.sans-serif": ["Segoe UI", "Helvetica", "Arial", "DejaVu Sans"],
    "axes.unicode_minus": False, "figure.dpi": 150, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#8a8984", "axes.labelcolor": "#52514e",
    "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.grid": True, "grid.color": "#e6e5e0", "grid.linewidth": .6, "axes.axisbelow": True,
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": "#0b0b0b",
})
BLUE, ORANGE, MUTED, INK = "#2a78d6", "#eb6834", "#b9b8b2", "#0b0b0b"
pct = lambda x, d=1: f"{x * 100:.{d}f}%"


def big(v, ref):
    if ref >= 1e6:
        return f"{v / 1e6:,.1f}M"
    if ref >= 1e4:
        return f"{v / 1e3:,.0f}K"
    return f"{v:,.0f}"


def build(out: Path):
    T = lambda n: pd.read_csv(out / "tables" / f"{n}.csv")
    save = lambda fig, name: (fig.savefig(out / "charts" / name, facecolor=fig.get_facecolor()), plt.close(fig))
    (out / "charts").mkdir(exist_ok=True)

    cl, ov = T("clean_log").iloc[0], T("overview").iloc[0]
    dl, hr = T("daily"), T("hourly")
    db, cp, vc = T("duration_buckets"), T("category_perf"), T("video_concentration").iloc[0]
    fo, ft, fc = T("funnel_overall").iloc[0], T("funnel_by_type"), T("funnel_by_category")
    ad, fr, ten, up, wr_ = T("by_activity_degree"), T("by_friends"), T("by_tenure"), T("user_pareto"), T("week_retention").iloc[0]
    lo, cl_lift, st = T("lift_overall"), T("category_lift"), T("stats_tests")
    src = T("data_source").source.iloc[0]
    cw, olap = T("core_window").iloc[0], T("overlap").iloc[0]

    # 1 Daily DAU and watch minutes
    dl["d"] = pd.to_datetime(dl.day)
    fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    ax[0].plot(dl.d, dl.dau, color=BLUE, lw=1.8)
    ax[0].set_ylim(0, dl.dau.max() * 1.1)
    ax[0].yaxis.set_major_formatter(lambda v, _: big(v, dl.dau.max()))
    ax[0].set_title("Daily active users (sampled users)")
    ax[1].plot(dl.d, dl.watch_min_per_dau, color=BLUE, lw=1.8)
    ax[1].set_ylim(0, dl.watch_min_per_dau.max() * 1.15)
    ax[1].set_title("Watch minutes per active user per day")
    import matplotlib.dates as mdates
    ax[1].xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0, interval=1))
    ax[1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax[1].tick_params(axis="x", labelsize=8)
    save(fig, "01_daily.png")

    # 2 Hour of day
    fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
    ax[0].bar(hr.hr, hr.view_share, color=BLUE, width=.7)
    ax[0].yaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax[0].set_title("Share of views by hour of day")
    ax[1].plot(hr.hr, hr.completion_rate, color=BLUE, lw=2, marker="o", ms=4)
    ax[1].yaxis.set_major_formatter(lambda v, _: pct(v, 1))
    ax[1].set_title("Completion rate by hour of day")
    ax[1].set_xticks(range(0, 24, 2))
    ax[1].set_xlabel("Hour (Beijing time)")
    save(fig, "02_hourly.png")

    # 3 Video length trade-off
    db["label"] = db.dur_bucket.str.split("_", n=1).str[1]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    ax[0].bar(db.label, db.completion_rate, color=BLUE, width=.6)
    ax[0].yaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax[0].set_title("Completion rate")
    ax[1].bar(db.label, db.avg_watch_seconds, color=ORANGE, width=.6)
    ax[1].set_title("Seconds watched per view")
    for a in ax:
        a.grid(axis="x", visible=False)
        a.set_xlabel("Video length")
    fig.suptitle("Completion and seconds watched by video length", fontsize=11, fontweight="bold", y=1.03)
    save(fig, "03_video_length.png")

    # 4 Category quadrant
    c = cp[(cp.category != "unknown") & (cp.views >= cp.views.sum() * .002)].copy()
    med_s, med_c = c.view_share.median(), c.completion_rate.median()
    under = c[(c.completion_rate > med_c) & (c.view_share < med_s)]
    over = c[(c.completion_rate < med_c) & (c.view_share > med_s)]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    col = np.where(c.index.isin(under.index), ORANGE, np.where(c.index.isin(over.index), MUTED, BLUE))
    ax.scatter(c.view_share, c.completion_rate, s=40, color=col, alpha=.85, linewidths=0)
    for r in c.itertuples():
        ax.annotate(r.category, (r.view_share, r.completion_rate), xytext=(4, 3), textcoords="offset points",
                    fontsize=7, color=INK)
    ax.axvline(med_s, color="#8a8984", lw=1, ls="--")
    ax.axhline(med_c, color="#8a8984", lw=1, ls="--")
    ax.xaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.yaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.set_xlabel("Share of views")
    ax.set_ylabel("Completion rate")
    ax.set_title("Categories: exposure vs completion (orange = under-exposed, grey = over-exposed)")
    save(fig, "04_category_quadrant.png")

    # 5 Funnel and ads
    steps = [("Plays", fo.plays), ("Valid plays", fo.valid_plays), ("Complete plays", fo.complete_plays),
             ("Likes", fo.likes), ("Follows", fo.follows), ("Comments", fo.comments), ("Shares", fo.shares)]
    per_k = [(n, v * 1000 / fo.shows) for n, v in steps]
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1.2, 1]})
    names, vals = zip(*per_k[::-1])
    ax[0].barh(names, vals, color=BLUE, height=.6)
    ax[0].set_xscale("log")
    for i, v in enumerate(vals):
        ax[0].text(v, i, f" {v:,.1f}", va="center", fontsize=8, color=INK)
    ax[0].set_title("Per 1,000 times a video is shown")
    ax[0].grid(axis="y", visible=False)
    if {"AD", "NORMAL"} <= set(ft.video_type):
        f2 = ft.set_index("video_type").loc[["NORMAL", "AD"]]
        metrics = ["likes_per_1k", "follows_per_1k", "comments_per_1k", "shares_per_1k"]
        x = np.arange(len(metrics))
        ax[1].bar(x - .2, f2.loc["NORMAL", metrics], .38, color=BLUE, label="Normal videos")
        ax[1].bar(x + .2, f2.loc["AD", metrics], .38, color=ORANGE, label="Ads")
        ax[1].set_xticks(x, ["Likes", "Follows", "Comments", "Shares"])
        ax[1].legend(frameon=False)
        ax[1].grid(axis="x", visible=False)
        ax[1].set_title("Per 1,000 plays: normal videos vs ads")
    save(fig, "05_funnel_ads.png")

    # 6 Users
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
    a2 = ad[ad.user_active_degree != "UNKNOWN"]
    ax[0].bar(a2.user_active_degree.str.replace("_", " "), a2.watch_min_per_active_day, color=BLUE, width=.6)
    ax[0].set_title("Watch minutes per active day, by activity level")
    fr2 = fr[fr.friends != "0_unknown"].copy()
    ax[1].bar(fr2.friends.str.split("_", n=1).str[1], fr2.watch_min_per_active_day, color=BLUE, width=.6)
    ax[1].set_title("Watch minutes per active day, by number of friends")
    for a in ax:
        a.grid(axis="x", visible=False)
    save(fig, "06_users.png")

    # 7 Concentration
    up["pct_users"] = up.rk / up.n_users
    top10u = up.loc[up.pct_users <= .10, "cum_watch_share"].max()
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.plot(up.pct_users, up.cum_watch_share, color=BLUE, lw=2)
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls="--")
    ax.scatter([.1], [top10u], color=ORANGE, zorder=3, s=25)
    ax.annotate(f"Top 10% of users = {pct(top10u, 0)} of watch time", (.1, top10u), xytext=(8, -12),
                textcoords="offset points", fontsize=8, color=INK)
    ax.xaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.yaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.set_xlabel("Users ranked by watch time")
    ax.set_ylabel("Cumulative share of watch time")
    ax.set_title("How concentrated is watch time?")
    save(fig, "07_user_concentration.png")

    # 8 Recommender lift
    lo2 = lo.set_index("exposure")
    rec, rnd = lo2.iloc[0], lo2.iloc[1]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1, 1.3]})
    m = ["avg_watch_ratio", "completion_rate", "skip_rate"]
    x = np.arange(3)
    ax[0].bar(x - .2, [rec[k] for k in m], .38, color=BLUE, label="Recommended (big matrix)")
    ax[0].bar(x + .2, [rnd[k] for k in m], .38, color=MUTED, label="Every video shown (small matrix)")
    ax[0].set_xticks(x, ["Watch ratio", "Completion", "Skip (<3s)"])
    ax[0].legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(.5, -.12), ncol=1)
    ax[0].grid(axis="x", visible=False)
    ax[0].set_title("Same users: own feed vs every video")
    cc = cl_lift.sort_values("lift")
    ax[1].barh(cc.category, cc.lift, color=np.where(cc.lift >= cc.lift.median(), BLUE, ORANGE), height=.65)
    ax[1].xaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax[1].tick_params(axis="y", labelsize=7)
    ax[1].grid(axis="y", visible=False)
    ax[1].set_title("Watch-ratio lift from recommendation, by category")
    save(fig, "08_recommender_lift.png")

    # ---------------- numbers for the report ----------------
    peak_h = int(hr.loc[hr.views.idxmax(), "hr"])
    evening = hr[hr.hr.between(18, 23)].view_share.sum()
    best_c_h = int(hr.loc[hr.completion_rate.idxmax(), "hr"])
    short, long_ = db.iloc[0], db.iloc[-1]
    wd = dl.assign(wd=dl.d.dt.dayofweek)
    we_ratio = wd[wd.wd >= 5].watch_min_per_dau.mean() / wd[wd.wd < 5].watch_min_per_dau.mean()
    lift = rec.avg_watch_ratio / rnd.avg_watch_ratio - 1
    s = lambda key: st[st.test.str.startswith(key)].iloc[0] if (st.test.str.startswith(key)).any() else None
    s_lift, s_len, s_act, s_fr, s_ad = (s("Recommended"), s("Video length vs"), s("Daily watch minutes"),
                                         s("Friends"), s("Likes per play"))
    # content-mix sizing: move 1pp of all views from over-exposed to under-exposed categories
    if len(under) and len(over):
        c_under = np.average(under.completion_rate, weights=under.views)
        c_over = np.average(over.completion_rate, weights=over.views)
        mix_gain = .01 * (c_under - c_over)
        extra_completes = mix_gain * ov.views
    else:
        c_under = c_over = mix_gain = extra_completes = np.nan
    fn = ft.set_index("video_type")
    ad_line = ""
    if {"AD", "NORMAL"} <= set(fn.index):
        ad_line = (f"Ads get {fn.likes_per_1k['AD']:.1f} likes and {fn.follows_per_1k['AD']:.1f} follows per 1,000 plays "
                   f"vs {fn.likes_per_1k['NORMAL']:.1f} and {fn.follows_per_1k['NORMAL']:.1f} for normal videos "
                   f"({fn.likes_per_1k['AD'] / fn.likes_per_1k['NORMAL']:.2f}x the like rate); completion "
                   f"{pct(fn.completion_rate['AD'])} vs {pct(fn.completion_rate['NORMAL'])}.")
    low_lift = cl_lift.sort_values("lift").head(3)
    high_lift = cl_lift.sort_values("lift", ascending=False).head(3)
    full = ad.set_index("user_active_degree")
    ret = wr_.retained_users / max(wr_.first_week_users, 1)
    is_real = cl.raw_views > 1_000_000
    sec_ratio = long_.avg_watch_seconds / max(short.avg_watch_seconds, 1e-9)
    flat_seconds = sec_ratio < 1.5
    avg_sec = db.avg_watch_seconds.mean()
    if flat_seconds:
        length_interp = (f"Users give each video about {avg_sec:.0f} seconds whatever its length, so long videos "
                         f"are mostly abandoned rather than watched longer")
        length_bullet = (f"Seconds watched per view barely change with length ({short.avg_watch_seconds:.1f} s for "
                         f"{short.label} vs {long_.avg_watch_seconds:.1f} s for {long_.label}), while completion collapses. "
                         f"Viewers decide within a few seconds; for long videos the opening seconds matter most, and "
                         f"creators should front-load the hook. Ranking on completion would push toward very short clips "
                         f"without losing watch time, so completion is a reasonable target here.")
    else:
        length_interp = "Completion rate alone would push the feed toward ever-shorter videos"
        length_bullet = ("Short videos are finished more often but give fewer seconds per view. A feed ranked only on "
                         "completion would favour very short clips and lose total watch time, so ranking should optimise "
                         "**expected watch time** (or a blend), not completion rate alone.")
    fr_rho = float(str(s_fr.effect).split("=")[-1]) if s_fr is not None else 0
    if s_fr is not None and s_fr.p_value < .05 and fr_rho > .1:
        friends_txt = ("Users with more friends watch more, which supports friend-graph features (following feed, "
                       "friend recommendations), though the direction of cause is not established.")
    elif s_fr is not None and abs(fr_rho) <= .1:
        friends_txt = (f"The correlation is negligible (rho = {fr_rho:.2f}): social ties do not explain how much people "
                       f"watch, so friend-graph features are unlikely to move watch time on their own.")
    else:
        friends_txt = "Users with more friends watch slightly less; social ties are not a driver of watch time here."
    has_lift = not np.isnan(rec.avg_watch_ratio)

    def tline(row):
        return f"{row.compared}, p = {row.p_value:.2g}, {row.effect}" if row is not None else "n/a"

    md = f"""# Kuaishou Short-Video Engagement Analysis (KuaiRec)

> Data: {"KuaiRec, Kuaishou short-video app, July-September 2020 (" + src + ")" if is_real else "WARNING: synthetic sample for testing only. Re-run on the real data before quoting any number."}
> {int(cl.raw_views):,} recommended views by {int(cl.users):,} users on {int(cl.videos):,} videos ({cl.first_day} to {cl.last_day}),
> plus a fully observed block of {int(cl.small_views):,} views ({int(cl.small_users):,} users x {int(cl.small_videos):,} videos) and platform-wide daily video statistics.
> Watch ratio = play time / video length, capped at 5 for averages ({int(cl.views_ratio_capped):,} views were above 5, mostly loops of very short videos).

## 0. Executive summary

| Area | Key numbers | Interpretation |
|---|---|---|
| Engagement | {ov.views_per_user_day} views and {ov.watch_min_per_user_day} minutes per user per active day; completion {pct(ov.completion_rate)}, skip within 3 s {pct(ov.skip_rate)} | Average video is {ov.avg_video_seconds:.0f} s |
| Timing | Views peak at {peak_h}:00; 18:00-24:00 holds {pct(evening, 0)} of views | {"Evening is prime time" if evening > .3 else "Viewing is spread through the day"} |
| Video length | Completion falls from {pct(short.completion_rate, 0)} ({short.label}) to {pct(long_.completion_rate, 0)} ({long_.label}); seconds watched per view {short.avg_watch_seconds:.1f} vs {long_.avg_watch_seconds:.1f} | {length_interp} |
| Content mix | {len(under)} categories are under-exposed (above-median completion, below-median share of views) | Re-allocating exposure is a cheap lever |
| Social actions | Per 1,000 shows: {fo.likes * 1000 / fo.shows:.1f} likes, {fo.follows * 1000 / fo.shows:.1f} follows, {fo.shares * 1000 / fo.shows:.2f} shares | Sharing and following are rare, so they are sparse ranking signals on their own |
| Ads | {"Ads get " + f"{fn.likes_per_1k['AD'] / fn.likes_per_1k['NORMAL']:.2f}x" + " the like rate of normal videos" if ad_line else "n/a"} | {"Ad load has a measurable engagement cost" if ad_line and fn.likes_per_1k["AD"] < fn.likes_per_1k["NORMAL"] else "Ads engage as well as normal videos"} |
| Users | Top 10% of users = {pct(top10u, 0)} of watch time | {"Heavy users drive a large share of watch time" if top10u > .25 else "Watch time is fairly evenly spread across sampled users"} |
| Recommender | {f"Watch ratio in users' own recommended feed is {lift:+.0%} vs when they were shown every video" if has_lift else "n/a"} | {("Personalisation adds engagement, but unevenly by category" if lift > 0 else "The recommended feed does not beat showing every video") if has_lift else ""} |

## 1. Engagement and timing
![daily](charts/01_daily.png)
- Trend analysis uses the {int(cw.core_days)} core days from {cw.first_core_day} to {cw.last_core_day} (days with at least half of the peak daily users; the logs start earlier with only a few users per day). Daily active sampled users ranged from {int(dl.dau.min()):,} to {int(dl.dau.max()):,}; weekend watch minutes per user are {we_ratio:.2f}x weekdays.
- {pct(ret, 0)} of the {int(wr_.first_week_users):,} users active in the first core week were still active in the last core week (sampled users are a panel, so this is high by design).

![hourly](charts/02_hourly.png)
- Views peak at {peak_h}:00 and completion peaks at {best_c_h}:00.

## 2. Content: length and category
![length](charts/03_video_length.png)
- {s_len.test if s_len is not None else ""}: {tline(s_len)}.
- {length_bullet}

![categories](charts/04_category_quadrant.png)
- Under-exposed winners: {", ".join(f"{r.category} ({pct(r.completion_rate, 0)} completion, {pct(r.view_share)} of views)" for r in under.sort_values("completion_rate", ascending=False).head(5).itertuples())}.
- Over-exposed: {", ".join(f"{r.category} ({pct(r.completion_rate, 0)}, {pct(r.view_share)})" for r in over.sort_values("view_share", ascending=False).head(5).itertuples())}.
- Views are concentrated: the top 1% of videos get {pct(vc.top1pct_view_share)} of views and the top 10% get {pct(vc.top10pct_view_share)}.

**Recommendation 1: rebalance exposure toward high-completion categories.** Moving just 1% of all views from the over-exposed to the under-exposed group ({pct(c_over)} vs {pct(c_under)} completion) would add about **{extra_completes:,.0f} completed views** in this sample ({mix_gain * 100:+.2f} pp completion). Test as an A/B experiment on the ranking boost, with watch time as a guardrail metric.

## 3. Engagement funnel and ads (platform-wide daily statistics)
![funnel](charts/05_funnel_ads.png)
- {ad_line}
- {s_ad.test if s_ad is not None else ""}: {tline(s_ad)}.

**Recommendation 2: price the engagement cost of ads.** Every slot given to an ad trades away likes and follows. Cap ad frequency for low-tenure users and A/B test ad load, measuring session length and next-day return alongside ad revenue.

## 4. Users
![users](charts/06_users.png)
""" + "\n".join(f"- {r.user_active_degree.replace('_', ' ')}: {int(r.users):,} users{' (small group, interpret with care)' if r.users < 100 else ''}, {r.watch_min_per_active_day} min per active day, {pct(r.watch_time_share)} of all watch time"
                for r in ad.itertuples()) + f"""
- {s_act.test if s_act is not None else ""}: {tline(s_act)}.
- {s_fr.test if s_fr is not None else ""}: {tline(s_fr)}. {friends_txt}

![concentration](charts/07_user_concentration.png)

## 5. How much does the recommender add?
![recommender](charts/08_recommender_lift.png)
- Design: {int(olap.small_users_in_big):,} of the {int(olap.small_users):,} fully observed users also appear in the recommender logs. The two matrices share {int(olap.shared_user_video_views):,} user-video views, so each user's own recommended feed (any video) is compared with the same user's reaction to every video in the {int(olap.small_videos):,}-video pool.
- Recommended feed: watch ratio {rec.avg_watch_ratio:.3f}, completion {pct(rec.completion_rate)}, quick skips {pct(rec.skip_rate)}. Every video shown: {rnd.avg_watch_ratio:.3f}, {pct(rnd.completion_rate)}, {pct(rnd.skip_rate)}.
- {s_lift.test if s_lift is not None else ""}: {tline(s_lift)}.
- Lift is highest for {", ".join(f"{r.category} ({r.lift:+.0%})" for r in high_lift.itertuples())} and lowest for {", ".join(f"{r.category} ({r.lift:+.0%})" for r in low_lift.itertuples())}.

**Recommendation 3: focus model work on low-lift categories.** Where recommendation barely beats showing everything, the model has not learned user taste; add category-specific features or more exploration traffic there.

## 6. Limitations
1. Users are a sample of Kuaishou users over about two months in 2020; daily video statistics cover all users, so funnel rates and matrix metrics describe different populations.
2. Watch ratio is capped at 5 for averages; very short videos replay automatically, so their ratios are not comparable with long videos without the cap.
3. The small matrix forced exposure in a special collection setting; users may behave differently than in their normal feed, so the lift is an estimate.
4. Category names are translated from Chinese first-level categories; free-text captions and tags are not used.
5. All recommendations are sized from observational data and need A/B tests.
"""
    (out / "report.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    build(Path(__file__).resolve().parents[1] / "output")
