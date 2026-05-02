-- Migration: drop inbox table
-- The inbox was the original capture intermediary. The direct-mode
-- /ritual/evening path and /entity/new pages made the inbound write path
-- dead. This migration removes the table. Existing inbox rows (if any)
-- are discarded — this system is pre-production and any inbox rows are
-- test data only.
--
-- The inbox FK columns on other tables (routed_to_observation_id etc.)
-- go away with the table itself. No other table has a FK to inbox.

DROP TABLE IF EXISTS inbox
