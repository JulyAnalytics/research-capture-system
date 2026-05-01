SELECT CASE
    WHEN (SELECT COUNT(*) FROM observation_images) > 0
    THEN 1/0
END;

DELETE FROM inbox WHERE routed_to_setup_id IS NOT NULL OR routed_to_observation_id IS NOT NULL;

DROP TABLE IF EXISTS observation_new;

CREATE TABLE observation_new (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL DEFAULT '',
    instrument         TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'watching'
                           CHECK(status IN ('watching', 'taken', 'passed')),
    note               TEXT NOT NULL DEFAULT '',
    passed_reason      TEXT,
    passed_reason_type TEXT CHECK(passed_reason_type IN ('psychological', 'analytical')),
    date               TEXT NOT NULL,
    created_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

INSERT INTO observation_new (id, name, instrument, status, note, date, created_at)
SELECT id,
       instrument,
       instrument,
       'watching',
       observation,
       date,
       created_at
FROM observation;

DROP TABLE observation;

ALTER TABLE observation_new RENAME TO observation;

DROP TABLE IF EXISTS setup_new;

CREATE TABLE setup_new (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL DEFAULT '',
    instrument TEXT NOT NULL,
    type       TEXT NOT NULL DEFAULT 'technical'
                   CHECK(type IN ('technical', 'vol', 'flow')),
    timeframe  TEXT NOT NULL DEFAULT '',
    setup_note TEXT NOT NULL DEFAULT '',
    date       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

INSERT INTO setup_new (id, name, instrument, type, timeframe, setup_note, date, created_at)
SELECT id,
       instrument,
       instrument,
       'technical',
       '',
       note,
       date,
       created_at
FROM setup;

DROP TABLE setup;

ALTER TABLE setup_new RENAME TO setup;

DROP TABLE IF EXISTS observation_thesis_links;

CREATE TABLE observation_thesis_links (
    observation_id TEXT NOT NULL REFERENCES observation(id),
    thesis_id      TEXT NOT NULL REFERENCES thesis(id),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (observation_id, thesis_id)
);

INSERT INTO observation_thesis_links (observation_id, thesis_id, created_at)
SELECT setup_id, thesis_id, created_at
FROM setup_thesis_links;

DROP TABLE setup_thesis_links;

DROP TABLE IF EXISTS observation_setup_links;

CREATE TABLE observation_setup_links (
    observation_id TEXT NOT NULL REFERENCES observation(id),
    setup_id       TEXT NOT NULL REFERENCES setup(id),
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (observation_id, setup_id)
);

INSERT INTO observation_setup_links (observation_id, setup_id, created_at)
SELECT observation_id, setup_id, created_at
FROM setup_observation_links;

DROP TABLE setup_observation_links;

DROP TABLE IF EXISTS setup_linked_canvases;

CREATE TABLE setup_linked_canvases (
    setup_id   TEXT NOT NULL REFERENCES setup(id),
    canvas_id  TEXT NOT NULL REFERENCES canvas(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (setup_id, canvas_id)
);

INSERT INTO setup_linked_canvases (setup_id, canvas_id, created_at)
SELECT observation_id, canvas_id, created_at
FROM observation_linked_canvases;

DROP TABLE observation_linked_canvases;

DROP TABLE IF EXISTS setup_thesis_links;

CREATE TABLE setup_thesis_links (
    setup_id   TEXT NOT NULL REFERENCES setup(id),
    thesis_id  TEXT NOT NULL REFERENCES thesis(id),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (setup_id, thesis_id)
);

DROP TABLE observation_images;
