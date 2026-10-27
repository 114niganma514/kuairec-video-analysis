-- =====================================================================
-- 01 Clean and model
-- Input tables (loaded by src/run_analysis.py):
--   big     = big_matrix.csv    : 12.5M views chosen by Kuaishou's recommender (7,176 users x 10,728 videos)
--   small   = small_matrix.csv  : 4.7M views, fully observed block (1,411 users each saw all 3,327 videos)
--   users   = user_features.csv, daily = item_daily_features.csv
--   video_cat = video_id -> English first-level category (built in Python from the caption file)
-- Standard SQL only, so it runs on DuckDB, SQLite, MySQL 8, Hive or Spark SQL.
-- =====================================================================

-- @name build_inter
-- One row per view in the big matrix.
--   watch ratio = play time / video length; capped at 5 for averages (loops of very short videos
--                 produce ratios above 100 that would dominate a mean)
--   complete    = watched to the end at least once
--   skip        = left within 3 seconds (Kuaishou's "short time play")
DROP TABLE IF EXISTS inter;
CREATE TABLE inter AS
SELECT user_id, video_id,
       play_duration / 1000.0                                               AS play_s,
       video_duration / 1000.0                                              AS dur_s,
       CASE WHEN watch_ratio > 5 THEN 5.0 ELSE watch_ratio END              AS wr,
       CASE WHEN play_duration >= video_duration THEN 1 ELSE 0 END          AS complete,
       CASE WHEN play_duration < 3000 AND play_duration < video_duration THEN 1 ELSE 0 END AS skip,
       substr("time", 1, 10)                                                AS day,
       CAST(substr("time", 12, 2) AS INTEGER)                               AS hr,
       CASE WHEN video_duration <= 7000  THEN '1_0-7s'
            WHEN video_duration <= 15000 THEN '2_7-15s'
            WHEN video_duration <= 30000 THEN '3_15-30s'
            WHEN video_duration <= 60000 THEN '4_30-60s'
            ELSE '5_over 60s' END                                           AS dur_bucket
FROM big
WHERE video_duration > 0 AND watch_ratio IS NOT NULL;

-- @name build_small_inter
DROP TABLE IF EXISTS small_inter;
CREATE TABLE small_inter AS
SELECT user_id, video_id,
       CASE WHEN watch_ratio > 5 THEN 5.0 ELSE watch_ratio END              AS wr,
       CASE WHEN play_duration >= video_duration THEN 1 ELSE 0 END          AS complete,
       CASE WHEN play_duration < 3000 AND play_duration < video_duration THEN 1 ELSE 0 END AS skip
FROM small
WHERE video_duration > 0 AND watch_ratio IS NOT NULL;

-- @name clean_log
SELECT (SELECT COUNT(*) FROM big)                                          AS raw_views,
       (SELECT COUNT(*) FROM inter)                                        AS clean_views,
       (SELECT COUNT(*) FROM big WHERE video_duration <= 0 OR watch_ratio IS NULL) AS dropped_views,
       (SELECT COUNT(*) FROM inter WHERE day IS NULL)                      AS views_without_time,
       (SELECT COUNT(*) FROM big WHERE watch_ratio > 5)                    AS views_ratio_capped,
       (SELECT COUNT(*) FROM (SELECT user_id, video_id FROM inter
                              GROUP BY user_id, video_id HAVING COUNT(*) > 1) d) AS repeated_user_video_pairs,
       (SELECT COUNT(DISTINCT user_id) FROM inter)                         AS users,
       (SELECT COUNT(DISTINCT video_id) FROM inter)                        AS videos,
       (SELECT MIN(day) FROM inter)                                        AS first_day,
       (SELECT MAX(day) FROM inter)                                        AS last_day,
       (SELECT COUNT(*) FROM small_inter)                                  AS small_views,
       (SELECT COUNT(DISTINCT user_id) FROM small_inter)                   AS small_users,
       (SELECT COUNT(DISTINCT video_id) FROM small_inter)                  AS small_videos,
       (SELECT COUNT(*) FROM video_cat WHERE category <> 'unknown')        AS videos_with_category;
