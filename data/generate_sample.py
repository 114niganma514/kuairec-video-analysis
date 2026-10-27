"""
Generates SYNTHETIC files with the same names and columns as the KuaiRec dataset, so the pipeline
can be tested without the 432 MB download. Numbers from this data are meaningless.
Usage: python data/generate_sample.py --users 400 --videos 1200 --out data/sample
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

CAT_IDS = [28, 8, 34, 5, 33, 11, 12, 6, 1, 9, 7, 25, 15, 13, 19, 20, 17, 26, 2, 32, 18, 10, 3, -124]


def main(n_users, n_videos, out, seed):
    rng = np.random.default_rng(seed)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    # videos: duration (ms), category, quality
    dur = np.clip(rng.lognormal(np.log(14000), .7, n_videos), 2000, 300000).round()
    cat = rng.choice(CAT_IDS, n_videos, p=np.r_[np.linspace(3, 1, len(CAT_IDS) - 1), .3] /
                     np.r_[np.linspace(3, 1, len(CAT_IDS) - 1), .3].sum())
    quality = rng.lognormal(0, .35, n_videos)
    pop = rng.pareto(1.3, n_videos) + 1
    pop /= pop.sum()

    # users
    degree = rng.choice(["full_active", "high_active", "middle_active", "UNKNOWN"], n_users, p=[.6, .25, .13, .02])
    act = {"full_active": 1.4, "high_active": 1.0, "middle_active": .55, "UNKNOWN": .5}
    user_act = np.array([act[x] for x in degree]) * rng.lognormal(0, .4, n_users)

    days = pd.date_range("2020-07-05", "2020-09-05", freq="D")
    rows = []
    for u in range(n_users):
        n = int(rng.poisson(user_act[u] * 250)) + 20
        v = rng.choice(n_videos, n, p=pop)
        d = rng.integers(0, len(days), n)
        rows.append(np.column_stack([np.full(n, u), v, d]))
    r = np.vstack(rows)
    u, v, d = r[:, 0], r[:, 1], r[:, 2]
    hw = np.array([3, 2, 1, .6, .4, .4, .8, 1.5, 2.5, 3, 3.2, 3.5, 4, 3.6, 3.4, 3.4, 3.5, 3.8, 4.2, 4.8, 5.4, 5.8, 5.2, 4])
    hour = rng.choice(24, len(r), p=hw / hw.sum())
    secs = rng.integers(0, 3600, len(r))
    ts = pd.to_datetime(days[d]) + pd.to_timedelta(hour * 3600 + secs, unit="s")
    vd = dur[v]
    # watch ratio: shorter + better videos are watched more completely
    mean_wr = quality[v] * np.clip(1.6 - np.log10(vd / 1000) * .45, .2, 2)
    wr = np.clip(rng.gamma(1.4, mean_wr / 1.4), 0, 40)
    play = (wr * vd).round()
    big = pd.DataFrame({"user_id": u, "video_id": v, "play_duration": play.astype(int), "video_duration": vd.astype(int),
                        "time": ts.strftime("%Y-%m-%d %H:%M:%S.000"), "date": ts.strftime("%Y%m%d").astype(int),
                        "timestamp": (ts - pd.Timedelta(hours=8) - pd.Timestamp("1970-01-01")) / pd.Timedelta(seconds=1), "watch_ratio": play / vd})
    big.loc[rng.random(len(big)) < .002, ["time", "date", "timestamp"]] = np.nan
    big.to_csv(out / "big_matrix.csv", index=False)

    # small matrix: a fully observed block (first 30% users x 30% videos); exposure is random,
    # so watch ratios are lower than in the recommender-chosen big matrix
    su, sv = np.arange(int(n_users * .3)), np.arange(int(n_videos * .3))
    uu, vv = np.meshgrid(su, sv, indexing="ij")
    uu, vv = uu.ravel(), vv.ravel()
    vd2 = dur[vv]
    wr2 = np.clip(rng.gamma(1.2, quality[vv] * .75 * np.clip(1.6 - np.log10(vd2 / 1000) * .45, .2, 2) / 1.2), 0, 40)
    ts2 = pd.to_datetime("2020-07-05") + pd.to_timedelta(rng.integers(0, 62 * 86400, len(uu)), unit="s")
    small = pd.DataFrame({"user_id": uu, "video_id": vv, "play_duration": (wr2 * vd2).round().astype(int),
                          "video_duration": vd2.astype(int), "time": ts2.strftime("%Y-%m-%d %H:%M:%S.000"),
                          "date": ts2.strftime("%Y%m%d").astype(int),
                          "timestamp": (ts2 - pd.Timedelta(hours=8) - pd.Timestamp("1970-01-01")) / pd.Timedelta(seconds=1), "watch_ratio": wr2})
    small.to_csv(out / "small_matrix.csv", index=False)

    reg = rng.integers(15, 900, n_users)
    friends = rng.poisson(user_act * 6)
    pd.DataFrame({
        "user_id": np.arange(n_users), "user_active_degree": degree,
        "is_lowactive_period": (rng.random(n_users) < .05).astype(int),
        "is_live_streamer": (rng.random(n_users) < .05).astype(int),
        "is_video_author": (rng.random(n_users) < .2).astype(int),
        "follow_user_num": rng.poisson(30, n_users), "follow_user_num_range": "(10,50]",
        "fans_user_num": rng.poisson(5, n_users), "fans_user_num_range": "[1,10)",
        "friend_user_num": friends, "friend_user_num_range": "[1,5)",
        "register_days": reg,
        "register_days_range": pd.cut(reg, [0, 30, 60, 90, 180, 365, 730, 10000],
                                      labels=["15-30", "31-60", "61-90", "91-180", "181-365", "366-730", "730+"]).astype(str),
        **{f"onehot_feat{i}": rng.integers(0, 3, n_users) for i in range(18)},
    }).to_csv(out / "user_features.csv", index=False)

    # daily video stats
    recs = []
    for vid in range(n_videos):
        for day in days[::3]:
            shows = int(pop[vid] * 4e6 * rng.lognormal(0, .3)) + 5
            plays = int(shows * min(.99, .9 * rng.uniform(.9, 1.05)))
            comp = int(plays * min(.95, .35 * quality[vid] * (15000 / dur[vid]) ** .4))
            recs.append((vid, int(day.strftime("%Y%m%d")), vid % 500, "AD" if vid % 25 == 0 else "NORMAL",
                         "2020-07-01", "ShortImport", "public", dur[vid], shows, int(shows * .7), plays, int(plays * .7),
                         plays * dur[vid] * .6, comp, int(plays * .6 * quality[vid] / 2), int(plays * .4),
                         int(plays * .05 * quality[vid] * (.5 if vid % 25 == 0 else 1)),
                         int(plays * .004), int(plays * .006 * quality[vid]), int(plays * .002), int(plays * .001)))
    cols = ["video_id", "date", "author_id", "video_type", "upload_dt", "upload_type", "visible_status",
            "video_duration", "show_cnt", "show_user_num", "play_cnt", "play_user_num", "play_duration",
            "complete_play_cnt", "valid_play_cnt", "long_time_play_cnt", "like_cnt", "comment_cnt",
            "follow_cnt", "share_cnt", "collect_cnt"]
    idf = pd.DataFrame(recs, columns=cols)
    idf["video_tag_name"] = "tag"
    idf.to_csv(out / "item_daily_features.csv", index=False)

    # caption/category file: messy like the real one (extra commas inside free text)
    with open(out / "kuairec_caption_category.csv", "w", encoding="utf-8") as f:
        f.write("video_id,manual_cover_text,caption,topic_tag,first_level_category_id,first_level_category_name,"
                "second_level_category_id,second_level_category_name,third_level_category_id,third_level_category_name\n")
        for vid in range(n_videos):
            cap = "some caption, with commas, inside" if vid % 3 == 0 else "caption"
            f.write(f"{vid},UNKNOWN,{cap},[],{cat[vid]},name_{cat[vid]},-124,UNKNOWN,-124,UNKNOWN\n")
    print(f"wrote {len(big):,} big-matrix rows, {len(small):,} small-matrix rows -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=400)
    ap.add_argument("--videos", type=int, default=1200)
    ap.add_argument("--out", default="data/sample")
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    main(a.users, a.videos, a.out, a.seed)
