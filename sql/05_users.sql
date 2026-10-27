-- =====================================================================
-- 05 Users: who watches, and how concentrated is watch time?
-- Business question: how do activity level, tenure and social ties relate to engagement?
-- =====================================================================

-- @name build_user_stats
DROP TABLE IF EXISTS user_stats;
CREATE TABLE user_stats AS
WITH u AS (
    SELECT user_id,
           COUNT(DISTINCT day)        AS active_days,
           COUNT(*)                   AS views,
           SUM(play_s) / 60.0         AS watch_min,
           AVG(complete * 1.0)        AS completion_rate,
           AVG(wr)                    AS avg_watch_ratio
    FROM inter
    GROUP BY user_id
)
SELECT u.*,
       u.watch_min / CASE WHEN u.active_days = 0 THEN 1 ELSE u.active_days END AS watch_min_per_active_day,
       f.user_active_degree, f.register_days, f.register_days_range,
       f.friend_user_num, f.is_video_author
FROM u
LEFT JOIN users f ON u.user_id = f.user_id;

-- @name user_stats_export
SELECT user_id, active_days, views, ROUND(watch_min, 1) AS watch_min,
       ROUND(watch_min_per_active_day, 2) AS watch_min_per_active_day,
       ROUND(completion_rate, 4) AS completion_rate, user_active_degree, friend_user_num, register_days
FROM user_stats;

-- @name by_activity_degree
SELECT COALESCE(user_active_degree, 'UNKNOWN')         AS user_active_degree,
       COUNT(*)                                       AS users,
       ROUND(AVG(active_days * 1.0), 1)               AS avg_active_days,
       ROUND(AVG(watch_min_per_active_day), 1)        AS watch_min_per_active_day,
       ROUND(AVG(completion_rate), 4)                 AS completion_rate,
       ROUND(SUM(watch_min) / (SELECT SUM(watch_min) FROM user_stats), 4) AS watch_time_share
FROM user_stats
GROUP BY COALESCE(user_active_degree, 'UNKNOWN')
ORDER BY watch_min_per_active_day DESC;

-- @name by_tenure
SELECT COALESCE(register_days_range, 'unknown')        AS register_days_range,
       MIN(register_days)                             AS min_days,
       COUNT(*)                                       AS users,
       ROUND(AVG(watch_min_per_active_day), 1)        AS watch_min_per_active_day,
       ROUND(AVG(completion_rate), 4)                 AS completion_rate
FROM user_stats
GROUP BY COALESCE(register_days_range, 'unknown')
ORDER BY min_days;

-- @name by_friends
SELECT CASE WHEN friend_user_num IS NULL THEN '0_unknown'
            WHEN friend_user_num = 0 THEN '1_none'
            WHEN friend_user_num < 5 THEN '2_1-4'
            WHEN friend_user_num < 30 THEN '3_5-29'
            ELSE '4_30+' END                          AS friends,
       COUNT(*)                                       AS users,
       ROUND(AVG(watch_min_per_active_day), 1)        AS watch_min_per_active_day,
       ROUND(AVG(active_days * 1.0), 1)               AS avg_active_days
FROM user_stats
GROUP BY 1
ORDER BY 1;

-- @name user_pareto
-- Users ranked by total watch time with cumulative share (for the concentration curve)
SELECT ROW_NUMBER() OVER (ORDER BY watch_min DESC)        AS rk,
       COUNT(*) OVER ()                                    AS n_users,
       ROUND(SUM(watch_min) OVER (ORDER BY watch_min DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(watch_min) OVER (), 5)                  AS cum_watch_share
FROM user_stats
ORDER BY rk;

-- @name week_retention
-- Of users active in the first 7 core days, how many are still active in the last 7 core days?
WITH days AS (
    SELECT day, ROW_NUMBER() OVER (ORDER BY day) AS n, COUNT(*) OVER () AS total
    FROM core_days x
),
w AS (
    SELECT DISTINCT i.user_id,
           CASE WHEN d.n <= 7 THEN 'first' WHEN d.n > d.total - 7 THEN 'last' END AS wk
    FROM inter i JOIN days d ON i.day = d.day
)
SELECT SUM(CASE WHEN wk = 'first' THEN 1 ELSE 0 END)                                  AS first_week_users,
       (SELECT COUNT(*) FROM (SELECT user_id FROM w GROUP BY user_id
                              HAVING SUM(CASE WHEN wk = 'first' THEN 1 ELSE 0 END) > 0
                                 AND SUM(CASE WHEN wk = 'last' THEN 1 ELSE 0 END) > 0) z) AS retained_users
FROM w;
