# Kuaishou Short-Video Engagement Analysis (KuaiRec, 12.5M views)

Analysis of real viewing logs from Kuaishou, China's second-largest short-video app. The project measures engagement, finds which content holds attention, sizes the engagement cost of ads, and estimates **how much the recommender adds over showing videos at random**, using KuaiRec's unique fully observed matrix.

## 1. Business questions

| # | Question | Method | File |
|---|---|---|---|
| Q1 | How much do users watch, and when? | Views and minutes per user-day, completion, quick-skip rate, daily and hourly patterns | `sql/02_engagement.sql` |
| Q2 | Which videos hold attention? | Length buckets (completion vs seconds watched), category exposure vs completion quadrant, view concentration | `sql/03_content.sql` |
| Q3 | How do shows turn into plays, likes, follows and shares? Do ads cost engagement? | Platform-wide funnel per 1,000 shows; ads vs normal videos | `sql/04_funnel.sql` |
| Q4 | Who are the heavy users? | Activity level, tenure, friend count, watch-time concentration, panel retention | `sql/05_users.sql` |
| Q5 | How much does the recommender add? | Same users and same video pool: recommended views (big matrix) vs every video shown (small matrix) | `sql/06_recommender.sql` |

Statistical tests (`src/stats_tests.py`): Wilcoxon signed-rank with bootstrap CI for recommender lift, Spearman and Kruskal-Wallis for video length, Mann-Whitney U for activity level, Spearman for friends, chi-square for ads.

## 2. Data

- Source: [KuaiRec](https://kuairec.com/) (Gao et al., CIKM 2022), official release on [Zenodo](https://zenodo.org/records/18164998), CC BY 4.0. The runner downloads it automatically (432 MB, first run only).
- Files used: `big_matrix.csv` (12.5M views chosen by the recommender, 7,176 users x 10,728 videos), `small_matrix.csv` (4.7M views: 1,411 users who were each shown all 3,327 videos), `user_features.csv`, `item_daily_features.csv` (platform-wide daily stats per video), `kuairec_caption_category.csv` (video categories)
- Cleaning and modelling (`sql/01_clean.sql`):
  - watch ratio = play time / video length, capped at 5 for averages (auto-replayed short clips reach ratios above 100)
  - complete = watched to the end; skip = left within 3 seconds (Kuaishou's own "short play" definition)
  - views with zero video length are dropped; views without a timestamp are kept but excluded from time analysis
  - first-level categories are mapped from Chinese to English in `src/run_analysis.py`; captions and free-text tags are not used
  - the caption file has unquoted commas inside free text, so it is parsed field-by-field instead of with a CSV reader

## 3. How to run

**Windows:** double-click `run_windows.bat`. It finds Anaconda, installs DuckDB if missing, downloads and unzips the data, and runs everything (about 1-3 minutes after the download).

**Command line:**
```bash
pip install duckdb pandas matplotlib scipy
python src/run_analysis.py                          # downloads data if needed
python data/generate_sample.py && python src/run_analysis.py --data data/sample --engine sqlite   # synthetic test
```

Outputs: `output/tables/*.csv` (one per query), `output/charts/*.png` (8 charts), `output/report.md`.

## 4. Project structure

```
data/generate_sample.py     synthetic data with the KuaiRec schema (testing only)
sql/01_clean.sql            interaction model, cleaning log
sql/02_engagement.sql       engagement and timing
sql/03_content.sql          video length, categories, concentration
sql/04_funnel.sql           show -> play -> like/follow/share funnel, ads vs normal
sql/05_users.sql            user segments, concentration, panel retention
sql/06_recommender.sql      recommender lift (big vs small matrix)
src/run_analysis.py         download, load, run SQL, export
src/stats_tests.py          statistical tests
src/make_report.py          charts and report
run_windows.bat             one-click runner for Windows
```

## 5. Metric definitions

- **Watch ratio** = play time / video length (capped at 5); **completion rate** = share of views watched to the end
- **Skip rate** = share of views left within 3 seconds (and before the end)
- **Watch minutes per active day** = total play time / days with at least one view
- **Funnel rates** = event counts per 1,000 shows or plays, from platform-wide daily statistics
- **Recommender lift** = watch ratio of recommended views / watch ratio when every video is shown - 1, for the same users and video pool

## 6. Key findings (real data; full numbers in `output/report.md`)

1. **The recommender adds about 12% watch ratio.** For the same 1,411 users, their recommended feed had a watch ratio of 0.975 vs 0.876 when shown every video (Wilcoxon signed-rank p < 0.001, 95% bootstrap CI +11.6% to +13.2%; 79% of users higher). The lift ranges from +147% (Finance) to -30% (Education).
2. **Viewers decide in about 9 seconds.** Completion falls from 65% for clips under 7 s to 1% for videos over 60 s (Spearman rho = -0.96), while seconds watched per view barely move (8.4 s vs 10.5 s): long videos are abandoned rather than watched longer.
3. **Ads carry a large engagement cost.** Ads get 4.6 likes per 1,000 plays vs 29.6 for normal videos (0.16x) and 5.5% completion vs 54%.
4. **Exposure is mis-allocated across categories.** Five categories (e.g. Current affairs, Fitness) have above-median completion but below-median exposure; moving 1% of views to them is worth about +12.9k completed views in this sample.
5. Users watch about 66 videos and 10 minutes per active day; social ties barely relate to watch time (rho = -0.05).

## 7. Limitations
- Sampled users over about two months in 2020; the daily video statistics cover all users
- The small matrix was collected in a special forced-exposure setting, so the lift is an estimate
- Correlations (e.g. friends and watch time) are not causal; recommendations need A/B tests
