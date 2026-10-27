-- =====================================================================
-- 03 Content: which videos hold attention?
-- Business question: how do video length and category affect completion and watch time,
--                    and how concentrated are views among videos?
-- =====================================================================

-- @name duration_buckets
SELECT dur_bucket,
       COUNT(DISTINCT video_id)                     AS videos,
       COUNT(*)                                     AS views,
       ROUND(COUNT(*) * 1.0 / (SELECT COUNT(*) FROM inter), 4) AS view_share,
       ROUND(AVG(complete * 1.0), 4)                AS completion_rate,
       ROUND(AVG(skip * 1.0), 4)                    AS skip_rate,
       ROUND(AVG(wr), 3)                            AS avg_watch_ratio,
       ROUND(AVG(play_s), 1)                        AS avg_watch_seconds
FROM inter
GROUP BY dur_bucket
ORDER BY dur_bucket;

-- @name category_perf
SELECT COALESCE(c.category, 'unknown')               AS category,
       COUNT(DISTINCT i.video_id)                    AS videos,
       COUNT(*)                                      AS views,
       ROUND(COUNT(*) * 1.0 / (SELECT COUNT(*) FROM inter), 4) AS view_share,
       ROUND(AVG(i.complete * 1.0), 4)               AS completion_rate,
       ROUND(AVG(i.skip * 1.0), 4)                   AS skip_rate,
       ROUND(AVG(i.wr), 3)                           AS avg_watch_ratio,
       ROUND(AVG(i.play_s), 1)                       AS avg_watch_seconds,
       ROUND(AVG(i.dur_s), 1)                        AS avg_video_seconds
FROM inter i
LEFT JOIN video_cat c ON i.video_id = c.video_id
GROUP BY COALESCE(c.category, 'unknown')
ORDER BY views DESC;

-- @name build_video_stats
DROP TABLE IF EXISTS video_stats;
CREATE TABLE video_stats AS
SELECT i.video_id,
       MAX(i.dur_s)                    AS dur_s,
       MAX(i.dur_bucket)               AS dur_bucket,
       COUNT(*)                        AS views,
       SUM(i.play_s)                   AS watch_s,
       AVG(i.complete * 1.0)           AS completion_rate,
       AVG(i.wr)                       AS avg_watch_ratio
FROM inter i
GROUP BY i.video_id;

-- @name video_stats_export
-- Video-level table for the statistical tests (videos with 30+ views)
SELECT v.video_id, ROUND(v.dur_s, 1) AS dur_s, v.dur_bucket, v.views,
       ROUND(v.completion_rate, 4) AS completion_rate, ROUND(v.avg_watch_ratio, 3) AS avg_watch_ratio,
       COALESCE(c.category, 'unknown') AS category
FROM video_stats v
LEFT JOIN video_cat c ON v.video_id = c.video_id
WHERE v.views >= 30;

-- @name video_concentration
WITH r AS (
    SELECT views, watch_s,
           ROW_NUMBER() OVER (ORDER BY views DESC) AS rk,
           COUNT(*) OVER ()                        AS n
    FROM video_stats
)
SELECT MAX(n)                                                                      AS videos,
       ROUND(SUM(CASE WHEN rk <= n * 0.01 THEN views ELSE 0 END) * 1.0 / SUM(views), 4) AS top1pct_view_share,
       ROUND(SUM(CASE WHEN rk <= n * 0.10 THEN views ELSE 0 END) * 1.0 / SUM(views), 4) AS top10pct_view_share,
       ROUND(SUM(CASE WHEN rk <= n * 0.50 THEN views ELSE 0 END) * 1.0 / SUM(views), 4) AS top50pct_view_share
FROM r;
