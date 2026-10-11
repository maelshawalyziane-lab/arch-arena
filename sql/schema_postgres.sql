-- =====================================================================
--  arch-olympiad · PostgreSQL schema (deliverable 1b)
-- =====================================================================
--  This is the hand-written equivalent of Django migration
--  `problems/migrations/0001_initial.py`.  Two supported workflows:
--
--    (A) Django owns the schema (recommended)
--        python manage.py migrate
--        # regenerate this file at any time with:
--        # python manage.py sqlmigrate problems 0001
--
--    (B) an external migration tool owns the schema
--        psql "$DATABASE_URL" -f sql/schema_postgres.sql
--        python manage.py migrate --fake-initial
--
--  Table names use Django's default <app>_<model> convention, so either way
--  the ORM maps onto exactly these relations.
--
--  Required companion tables: Django's own apps (auth_user, django_session,
--  django_admin_log, django_content_type, auth_permission, ...) must exist;
--  run `manage.py migrate auth contenttypes admin sessions` before this file
--  if you apply it to an empty database.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Problem: one olympiad problem, keyed by a human readable PUID.
-- ---------------------------------------------------------------------
CREATE TABLE problems_problem (
    id               bigserial    PRIMARY KEY,
    puid             varchar(120) NOT NULL UNIQUE,          -- "IMO 2016/4"
    legacy_puid      varchar(20)  NOT NULL DEFAULT '',      -- ARCH 6-char code, e.g. "XKPFMI"
    statement_tex    text         NOT NULL,                 -- Markdown-flavoured TeX
    category         varchar(20)  NOT NULL,                 -- algebra|combinatorics|geometry|number_theory|misc
    difficulty_track varchar(20)  NOT NULL,                 -- foundation|olympiad|hard
    source_url       varchar(200) NOT NULL DEFAULT '',
    answer_tex       varchar(255) NOT NULL DEFAULT '',      -- revealed only together with the solution
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now()
);

CREATE INDEX problems_problem_legacy_puid_idx  ON problems_problem (legacy_puid);
CREATE INDEX problems_problem_category_idx     ON problems_problem (category);
CREATE INDEX problems_problem_track_idx        ON problems_problem (difficulty_track);
CREATE INDEX problem_puid_idx                  ON problems_problem (puid);

COMMENT ON COLUMN problems_problem.answer_tex IS
    'Compact canonical answer. Spoiler: the application only serialises it once UserProgress.is_solved is true.';
COMMENT ON COLUMN problems_problem.legacy_puid IS
    'Original ARCH code from otis-web fixtures; keeps re-imports idempotent.';

-- ---------------------------------------------------------------------
-- Hint: tiered hints, revealed strictly in order_index order.
-- ---------------------------------------------------------------------
CREATE TABLE problems_hint (
    id          bigserial    PRIMARY KEY,
    order_index integer      NOT NULL CHECK (order_index >= 0),
    content_md  text         NOT NULL,
    keywords    varchar(255) NOT NULL DEFAULT '',
    created_at  timestamptz  NOT NULL DEFAULT now(),
    problem_id  bigint       NOT NULL REFERENCES problems_problem (id) ON DELETE CASCADE,
    CONSTRAINT unique_hint_order_per_problem UNIQUE (problem_id, order_index)
);

CREATE INDEX problems_hint_problem_id_idx ON problems_hint (problem_id);

COMMENT ON COLUMN problems_hint.order_index IS
    '1-based reveal tier. The server refuses to serve a hint until every lower tier has a HintReveal row.';

-- ---------------------------------------------------------------------
-- Solution: the OFFICIAL ground truth (answer key + grading reference).
-- ---------------------------------------------------------------------
CREATE TABLE problems_solution (
    id           bigserial    PRIMARY KEY,
    official_tex text         NOT NULL,
    attribution  varchar(255) NOT NULL DEFAULT '',
    updated_at   timestamptz  NOT NULL DEFAULT now(),
    problem_id   bigint       NOT NULL UNIQUE REFERENCES problems_problem (id) ON DELETE CASCADE
);

COMMENT ON TABLE problems_solution IS
    'Answer key. Read by the grader in-process and rendered only after unlock; never included in a locked page payload.';

-- ---------------------------------------------------------------------
-- UserProgress: the unlock flag the whole gate hinges on.
-- ---------------------------------------------------------------------
CREATE TABLE problems_userprogress (
    id          bigserial   PRIMARY KEY,
    is_solved   boolean     NOT NULL DEFAULT false,
    unlocked_at timestamptz NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    problem_id  bigint      NOT NULL REFERENCES problems_problem (id) ON DELETE CASCADE,
    user_id     integer     NOT NULL REFERENCES auth_user (id)      ON DELETE CASCADE,
    CONSTRAINT unique_progress_per_user UNIQUE (user_id, problem_id)
);

CREATE INDEX problems_userprogress_user_problem_idx ON problems_userprogress (user_id, problem_id);
CREATE INDEX progress_user_solved_idx               ON problems_userprogress (user_id, is_solved);
CREATE INDEX problems_userprogress_is_solved_idx    ON problems_userprogress (is_solved);

-- ---------------------------------------------------------------------
-- UserSubmission: immutable audit trail of every grading attempt.
-- ---------------------------------------------------------------------
CREATE TABLE problems_usersubmission (
    id             bigserial   PRIMARY KEY,
    submitted_text text        NOT NULL,
    status         varchar(10) NOT NULL DEFAULT 'PENDING',  -- PENDING|PASSED|REJECTED
    ai_feedback    text        NOT NULL DEFAULT '',
    engine         varchar(32) NOT NULL DEFAULT '',         -- "openai:gpt-4o", "offline-heuristic", ...
    latency_ms     integer     NULL CHECK (latency_ms >= 0),
    raw_response   jsonb       NULL,                        -- staff-only grader payload
    is_demo        boolean     NOT NULL DEFAULT false,
    created_at     timestamptz NOT NULL DEFAULT now(),
    problem_id     bigint      NOT NULL REFERENCES problems_problem (id) ON DELETE CASCADE,
    user_id        integer     NOT NULL REFERENCES auth_user (id)        ON DELETE CASCADE
);

CREATE INDEX problems_usersubmission_created_at_idx ON problems_usersubmission (created_at);
CREATE INDEX problems_usersubmission_problem_id_idx ON problems_usersubmission (problem_id);
CREATE INDEX problems_usersubmission_user_id_idx    ON problems_usersubmission (user_id);
CREATE INDEX submission_lookup_idx                  ON problems_usersubmission (user_id, problem_id, created_at DESC);

COMMENT ON COLUMN problems_usersubmission.status IS
    'PASSED flips UserProgress.is_solved; PENDING means the grader was unreachable and the attempt is retryable.';
COMMENT ON COLUMN problems_usersubmission.raw_response IS
    'Raw model payload for auditing. Staff-only: the public API never serialises this column.';

-- ---------------------------------------------------------------------
-- HintReveal: server-side record of opened hints (one per user+hint).
-- ---------------------------------------------------------------------
CREATE TABLE problems_hintreveal (
    id          bigserial   PRIMARY KEY,
    revealed_at timestamptz NOT NULL DEFAULT now(),
    hint_id     bigint      NOT NULL REFERENCES problems_hint (id) ON DELETE CASCADE,
    user_id     integer     NOT NULL REFERENCES auth_user (id)     ON DELETE CASCADE,
    CONSTRAINT unique_reveal_per_user_hint UNIQUE (user_id, hint_id)
);

CREATE INDEX problems_hintreveal_hint_id_idx ON problems_hintreveal (hint_id);
CREATE INDEX problems_hintreveal_user_id_idx ON problems_hintreveal (user_id);

COMMIT;

-- =====================================================================
--  OPTIONAL HARDENING (not created by Django migrations)
--  Apply these if PostgreSQL is your last line of defence. Django's
--  model choices are not enforced in the database by default.
-- =====================================================================

BEGIN;

-- 1. Enum-like guards ------------------------------------------------
ALTER TABLE problems_problem
    ADD CONSTRAINT problem_category_valid
    CHECK (category IN ('algebra', 'combinatorics', 'geometry', 'number_theory', 'misc'));

ALTER TABLE problems_problem
    ADD CONSTRAINT problem_track_valid
    CHECK (difficulty_track IN ('foundation', 'olympiad', 'hard'));

ALTER TABLE problems_usersubmission
    ADD CONSTRAINT submission_status_valid
    CHECK (status IN ('PENDING', 'PASSED', 'REJECTED'));

-- 2. An unlock must always carry a timestamp -------------------------
ALTER TABLE problems_userprogress
    ADD CONSTRAINT progress_unlock_consistent
    CHECK ((is_solved = false AND unlocked_at IS NULL) OR (is_solved = true AND unlocked_at IS NOT NULL));

-- 3. Full-text search acceleration for the statement/hint search box -
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS problem_statement_trgm
    ON problems_problem USING gin (statement_tex gin_trgm_ops);
CREATE INDEX IF NOT EXISTS hint_content_trgm
    ON problems_hint USING gin (content_md gin_trgm_ops);

-- 4. Least-privilege role for the application -----------------------
--    (run as a superuser; adjust the password)
-- CREATE ROLE arch_app LOGIN PASSWORD 'change-me';
-- GRANT CONNECT ON DATABASE arch_olympiad TO arch_app;
-- GRANT USAGE ON SCHEMA public TO arch_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO arch_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO arch_app;
-- -- Answer keys are only ever read/written by the app, never by reporting users:
-- REVOKE ALL ON problems_solution FROM PUBLIC;

COMMIT;

-- =====================================================================
--  Verifying parity with the ORM
-- =====================================================================
--  After applying this file run:
--      python manage.py migrate --fake-initial
--      python manage.py check
--      python manage.py test problems            # 39 tests, includes schema usage
--  To confirm nothing drifted, compare:
--      python manage.py sqlmigrate problems 0001 | grep 'CREATE TABLE'
--  with the table list above.
-- =====================================================================
