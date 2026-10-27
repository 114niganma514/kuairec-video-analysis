-- =====================================================================
-- 06 Recommender lift: chosen exposure vs full exposure
-- KuaiRec's small matrix was collected by showing EVERY one of 3,327 videos to each of 1,411 users,
-- so it shows how users react to content they did not choose. The big matrix holds the views the
-- production recommender chose. In the released data the two matrices do not share user-video pairs,
-- so the comparison is made per user: each small-matrix user's recommended feed (big matrix, any video)
-- vs the same user's reaction to every video in the 3,327-video pool.
-- =====================================================================

-- @name overlap
SELECT (SELECT COUNT(DISTINCT user_id) FROM small_inter)                                   AS small_users,
       (SELECT COUNT(DISTINCT user_id) FROM inter
         WHERE user_id IN (SELECT DISTINCT user_id FROM small_inter))                     AS small_users_in_big,
       (SELECT COUNT(DISTINCT video_id) FROM small_inter)                                  AS small_videos,
       (SELECT COUNT(DISTINCT video_id) FROM inter
         WHERE video_id IN (SELECT DISTINCT video_id FROM small_inter))                   AS small_videos_in_big,
       (SELECT COUNT(*) FROM inter
         WHERE user_id IN (SELECT DISTINCT user_id FROM small_inter)
           AND video_id IN (SELECT DISTINCT video_id FROM small_inter))                   AS shared_user_video_views;

-- @name build_rec_pairs
DROP TABLE IF EXISTS rec_pool;
CREATE TABLE rec_pool AS
SELECT i.user_id, i.video_id, i.wr, i.complete, i.skip
FROM inter i
WHERE i.user_id IN (SELECT DISTINCT user_id FROM small_inter);

-- @name lift_overall
SELECT 'recommended feed (big matrix)'     AS exposure,
       COUNT(*)                            AS views,
       ROUND(AVG(wr), 4)                   AS avg_watch_ratio,
       ROUND(AVG(complete * 1.0), 4)       AS completion_rate,
       ROUND(AVG(skip * 1.0), 4)           AS skip_rate
FROM rec_pool
UNION ALL
SELECT 'every video shown (small matrix)',
       COUNT(*), ROUND(AVG(wr), 4), ROUND(AVG(complete * 1.0), 4), ROUND(AVG(skip * 1.0), 4)
FROM small_inter;

-- @name user_lift
-- Per user: recommended feed vs every-video average watch ratio (paired test in stats_tests.py)
WITH b AS (SELECT user_id, COUNT(*) AS rec_views, AVG(wr) AS rec_wr, AVG(complete * 1.0) AS rec_comp
           FROM rec_pool GROUP BY user_id),
s AS (SELECT user_id, AVG(wr) AS all_wr, AVG(complete * 1.0) AS all_comp FROM small_inter GROUP BY user_id)
SELECT s.user_id, b.rec_views,
       ROUND(b.rec_wr, 4) AS rec_wr, ROUND(s.all_wr, 4) AS all_wr,
       ROUND(b.rec_comp, 4) AS rec_comp, ROUND(s.all_comp, 4) AS all_comp
FROM s JOIN b ON s.user_id = b.user_id
WHERE b.rec_views >= 20;

-- @name category_lift
WITH b AS (SELECT c.category, AVG(r.wr) AS rec_wr, COUNT(*) AS rec_views
           FROM rec_pool r JOIN video_cat c ON r.video_id = c.video_id GROUP BY c.category),
s AS (SELECT c.category, AVG(m.wr) AS all_wr, COUNT(*) AS all_views
      FROM small_inter m JOIN video_cat c ON m.video_id = c.video_id GROUP BY c.category)
SELECT s.category, b.rec_views, s.all_views,
       ROUND(b.rec_wr, 4) AS rec_wr, ROUND(s.all_wr, 4) AS all_wr,
       ROUND(b.rec_wr / s.all_wr - 1, 4) AS lift
FROM s JOIN b ON s.category = b.category
WHERE b.rec_views >= 200 AND s.category <> 'unknown'
ORDER BY lift DESC;
