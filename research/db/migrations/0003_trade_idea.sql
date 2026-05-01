CREATE TABLE trade_new (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL DEFAULT '',
    instrument         TEXT,
    idea_note          TEXT,
    thesis_id          TEXT REFERENCES thesis(id),
    instrument_type    TEXT NOT NULL DEFAULT 'equity'
                           CHECK(instrument_type IN ('equity', 'option', 'future', 'fx', 'other')),
    entry_rules_stated TEXT,
    exit_rules_stated  TEXT,
    thesis_snapshot    TEXT,
    status             TEXT NOT NULL DEFAULT 'idea'
                           CHECK(status IN ('idea', 'active', 'closed', 'discarded')),
    review_id          TEXT,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    closed_at          TEXT
);

INSERT INTO trade_new (
    id, name, instrument, idea_note,
    thesis_id, instrument_type,
    entry_rules_stated, exit_rules_stated, thesis_snapshot,
    status, review_id, created_at, closed_at
)
SELECT
    id,
    '',
    NULL,
    NULL,
    thesis_id,
    instrument_type,
    entry_rules_stated,
    exit_rules_stated,
    thesis_snapshot,
    CASE status
        WHEN 'open'   THEN 'active'
        WHEN 'closed' THEN 'closed'
        ELSE status
    END,
    review_id,
    created_at,
    closed_at
FROM trade;

DROP TABLE trade;

ALTER TABLE trade_new RENAME TO trade
