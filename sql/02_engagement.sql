-- =====================================================================
-- 02 Engagement: how much do people watch, and when?
-- Business question: what does a typical user day look like, and how does engagement move over time?
-- =====================================================================

-- @name overview
WITH ud AS (
    SELECT user_id, day, COUNT(*) AS views, SUM(play_s) AS watch_s
    FROM inter WHERE day IS NOT NULL
    GROUP BY user_id, day
)
SELECT (SELECT COUNT(*) FROM inter)                         AS views,
       (SELECT COUNT(DISTINCT user_id) FROM inter)          AS users,
       (SELECT COUNT(DISTINCT video_id) FROM inter)         AS videos,
       ROUND(AVG(views * 1.0), 1)                           AS views_per_user_day,
       ROUND(AVG(watch_s) / 60.0, 1)                        AS watch_min_per_user_day,
       (SELECT ROUND(AVG(wr), 3) FROM inter)                AS avg_watch_ratio,
       (SELECT ROUND(AVG(complete * 1.0), 4) FROM inter)    AS completion_rate,
       (SELECT ROUND(AVG(skip * 1.0), 4) FROM inter)        AS skip_rate,
       (SELECT ROUND(AVG(dur_s), 1) FROM inter)             AS avg_video_seconds
FROM ud;

-- @name build_core_days
-- The logs contain a few early days with only a handful of users. Trend and retention analysis
-- uses "core" days: days with at least half of the busiest day's active users.
DROP TABLE IF EXISTS core_days;
CREATE TABLE core_days AS
WITH d AS (SELECT day, COUNT(DISTINCT user_id) AS dau FROM inter WHERE day IS NOT NULL GROUP BY day)
SELECT day, dau FROM d WHERE dau >= 0.5 * (SELECT MAX(dau) FROM d);

-- @name core_window
SELECT MIN(day) AS first_core_day, MAX(day) AS last_core_day, COUNT(*) AS core_days FROM core_days;

-- @name daily
SELECT day,
       COUNT(DISTINCT user_id)                         AS dau,
       COUNT(*)                                        AS views,
       ROUND(SUM(play_s) / 60.0 / COUNT(DISTINCT user_id), 1) AS watch_min_per_dau,
       ROUND(COUNT(*) * 1.0 / COUNT(DISTINCT user_id), 1)     AS views_per_dau,
       ROUND(AVG(complete * 1.0), 4)                   AS completion_rate,
       ROUND(AVG(skip * 1.0), 4)                       AS skip_rate
FROM inter
WHERE day IN (SELECT day FROM core_days)
GROUP BY day
ORDER BY day;

-- @name hourly
SELECT hr,
       COUNT(*)                                                    AS views,
       ROUND(COUNT(*) * 1.0 / (SELECT COUNT(*) FROM inter WHERE hr IS NOT NULL), 4) AS view_share,
       ROUND(AVG(complete * 1.0), 4)                               AS completion_rate,
       ROUND(AVG(skip * 1.0), 4)                                   AS skip_rate,
       ROUND(AVG(wr), 3)                                           AS avg_watch_ratio
FROM inter
WHERE hr IS NOT NULL
GROUP BY hr
ORDER BY hr;
