-- Verity persistence schema.
--
-- Hybrid shape: the pydantic JSON `payload` is authoritative for every record, and the
-- adjacent columns are *derived indexes* rebuilt on every write. Loading always goes
-- through `payload`, so the two can never disagree about content -- the columns exist
-- only so the queries M5 and M8 depend on are indexed rather than full scans:
--
--   facts(key_type, key_value)          exact-key grounding lookup      (M5-T1)
--   facts(statement_hash)               statement dedup                 (M5-T1)
--   graph_groundings(fact_id)           which graphs a fact holds up    (M8-T2, M1-T3)
--   justification_antecedents(fact_id)  JTMS propagation                (M8-T2)

CREATE TABLE IF NOT EXISTS claim_graphs (
    id             TEXT PRIMARY KEY,
    root_claim_id  TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    run_id         TEXT,
    created_at     TEXT NOT NULL,
    payload        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_claim_graphs_root ON claim_graphs(root_claim_id);
CREATE INDEX IF NOT EXISTS ix_claim_graphs_run ON claim_graphs(run_id);

CREATE TABLE IF NOT EXISTS graph_premises (
    graph_id          TEXT NOT NULL REFERENCES claim_graphs(id) ON DELETE CASCADE,
    premise_id        TEXT NOT NULL,
    depth             INTEGER NOT NULL,
    bound_key_type    TEXT,
    bound_key_value   TEXT,
    evidence_state    TEXT NOT NULL,
    termination_reason TEXT,
    PRIMARY KEY (graph_id, premise_id)
);
CREATE INDEX IF NOT EXISTS ix_graph_premises_key
    ON graph_premises(bound_key_type, bound_key_value);

CREATE TABLE IF NOT EXISTS graph_groundings (
    graph_id   TEXT NOT NULL REFERENCES claim_graphs(id) ON DELETE CASCADE,
    premise_id TEXT NOT NULL,
    fact_id    TEXT NOT NULL,
    PRIMARY KEY (graph_id, premise_id, fact_id)
);
CREATE INDEX IF NOT EXISTS ix_graph_groundings_fact ON graph_groundings(fact_id);

CREATE TABLE IF NOT EXISTS facts (
    id             TEXT PRIMARY KEY,
    key_type       TEXT NOT NULL,
    key_value      TEXT NOT NULL,
    statement_hash TEXT NOT NULL,
    tier           TEXT NOT NULL,
    status         TEXT NOT NULL,
    revalidated_at TEXT,
    payload        TEXT NOT NULL
);
-- Redundant with the primary key while ids are derived from (key, statement) -- which is
-- enforced in `Fact` -- and that is the point: it turns a digest collision between two
-- different facts into an error instead of a silent overwrite.
CREATE UNIQUE INDEX IF NOT EXISTS ux_facts_key_statement
    ON facts(key_type, key_value, statement_hash);
CREATE INDEX IF NOT EXISTS ix_facts_key ON facts(key_type, key_value);
CREATE INDEX IF NOT EXISTS ix_facts_statement ON facts(statement_hash);

CREATE TABLE IF NOT EXISTS justifications (
    id                 TEXT PRIMARY KEY,
    consequent_fact_id TEXT NOT NULL,
    payload            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_justifications_consequent
    ON justifications(consequent_fact_id);

CREATE TABLE IF NOT EXISTS justification_antecedents (
    justification_id TEXT NOT NULL REFERENCES justifications(id) ON DELETE CASCADE,
    fact_id          TEXT NOT NULL,
    PRIMARY KEY (justification_id, fact_id)
);
CREATE INDEX IF NOT EXISTS ix_justification_antecedents_fact
    ON justification_antecedents(fact_id);

CREATE TABLE IF NOT EXISTS run_manifests (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    payload     TEXT NOT NULL
);
