CREATE TABLE IF NOT EXISTS users (
  id            SERIAL PRIMARY KEY,
  name          VARCHAR(80)  NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_name_lower ON users (lower(name));

CREATE TABLE IF NOT EXISTS profiles (
  user_id              INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  age                  SMALLINT CONSTRAINT ck_profiles_age CHECK (age BETWEEN 1 AND 120),
  allergies            TEXT NOT NULL DEFAULT '',
  food_likes           TEXT NOT NULL DEFAULT '',
  food_dislikes        TEXT NOT NULL DEFAULT '',
  dietary_restrictions TEXT NOT NULL DEFAULT '',
  notes                TEXT NOT NULL DEFAULT '',
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reports (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  filename   VARCHAR(255) NOT NULL,
  pdf_text   TEXT NOT NULL DEFAULT '',
  plan       JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_reports_user_id ON reports (user_id, created_at DESC);
