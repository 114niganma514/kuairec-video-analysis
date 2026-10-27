-- =====================================================================
-- 04 Engagement funnel (platform-wide daily video statistics)
-- Business question: of the times a video is shown, how often is it played, finished, liked,
--                    commented on, followed and shared? Do ads behave differently from normal videos?
-- Note: item_daily_features counts ALL Kuaishou users, not only the sampled users of the matrices.
-- =====================================================================

-- @name funnel_overall
SELECT SUM(show_cnt)            AS shows,
       SUM(play_cnt)            AS plays,
       SUM(valid_play_cnt)      AS valid_plays,
       SUM(complete_play_cnt)   AS complete_plays,
       SUM(like_cnt)            AS likes,
       SUM(comment_cnt)         AS comments,
       SUM(follow_cnt)          AS follows,
       SUM(share_cnt)           AS shares,
       SUM(collect_cnt)         AS collects
FROM daily;

-- @name funnel_by_type
-- Rates per 1,000 plays
SELECT video_type,
       COUNT(DISTINCT video_id)                                   AS videos,
       SUM(play_cnt)                                              AS plays,
       ROUND(SUM(play_cnt) * 1.0 / SUM(show_cnt), 4)              AS play_rate,
       ROUND(SUM(complete_play_cnt) * 1.0 / SUM(play_cnt), 4)    AS completion_rate,
       ROUND(SUM(like_cnt) * 1000.0 / SUM(play_cnt), 2)           AS likes_per_1k,
       ROUND(SUM(comment_cnt) * 1000.0 / SUM(play_cnt), 2)        AS comments_per_1k,
       ROUND(SUM(follow_cnt) * 1000.0 / SUM(play_cnt), 2)         AS follows_per_1k,
       ROUND(SUM(share_cnt) * 1000.0 / SUM(play_cnt), 2)          AS shares_per_1k,
       SUM(like_cnt)                                              AS likes
FROM daily
WHERE play_cnt > 0
GROUP BY video_type
ORDER BY plays DESC;

-- @name funnel_by_category
SELECT COALESCE(c.category, 'unknown')                             AS category,
       SUM(d.show_cnt)                                            AS shows,
       ROUND(SUM(d.play_cnt) * 1.0 / SUM(d.show_cnt), 4)          AS play_rate,
       ROUND(SUM(d.complete_play_cnt) * 1.0 / SUM(d.play_cnt), 4) AS completion_rate,
       ROUND(SUM(d.like_cnt) * 1000.0 / SUM(d.play_cnt), 2)       AS likes_per_1k,
       ROUND(SUM(d.follow_cnt) * 1000.0 / SUM(d.play_cnt), 2)     AS follows_per_1k,
       ROUND(SUM(d.share_cnt) * 1000.0 / SUM(d.play_cnt), 2)      AS shares_per_1k
FROM daily d
LEFT JOIN video_cat c ON d.video_id = c.video_id
WHERE d.play_cnt > 0
GROUP BY COALESCE(c.category, 'unknown')
ORDER BY shows DESC;
