-- VR Academy — Schema SQLite
-- Criado automaticamente pelo init_db()

-- Usuarios do sistema
CREATE TABLE IF NOT EXISTS users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    name              TEXT NOT NULL,
    email             TEXT NOT NULL UNIQUE,
    password_hash     TEXT NOT NULL,
    role              TEXT NOT NULL CHECK(role IN ('admin','gestor','colaborador')),
    is_active         INTEGER NOT NULL DEFAULT 1,
    pipedrive_user_id INTEGER,
    phone             TEXT,
    discord_id        TEXT,
    hire_date         TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Trilhas de aprendizado
CREATE TABLE IF NOT EXISTS tracks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    description   TEXT,
    is_required   INTEGER NOT NULL DEFAULT 1,
    due_in_days   INTEGER NOT NULL DEFAULT 30,
    "order"       INTEGER NOT NULL DEFAULT 0,
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Modulos dentro de uma trilha
CREATE TABLE IF NOT EXISTS modules (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id           INTEGER NOT NULL REFERENCES tracks(id),
    name               TEXT NOT NULL,
    description        TEXT,
    "order"            INTEGER NOT NULL DEFAULT 0,
    points_value       INTEGER NOT NULL DEFAULT 50,
    is_required        INTEGER NOT NULL DEFAULT 1,
    estimated_minutes  INTEGER NOT NULL DEFAULT 30,
    crivo_area         TEXT,  -- area do crivo: abertura|qualificacao|apresentacao|objecoes|fechamento|postura
    is_active          INTEGER NOT NULL DEFAULT 1,
    prerequisite_module_id INTEGER REFERENCES modules(id)  -- modulo que precisa ser concluido antes
);

-- Licoes dentro de um modulo
CREATE TABLE IF NOT EXISTS lessons (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id        INTEGER NOT NULL REFERENCES modules(id),
    name             TEXT NOT NULL,
    description      TEXT,
    content_type     TEXT NOT NULL CHECK(content_type IN ('video','pdf','quiz','texto','audio')),
    content_url      TEXT,
    duration_minutes INTEGER NOT NULL DEFAULT 10,
    points_value     INTEGER NOT NULL DEFAULT 10,
    "order"          INTEGER NOT NULL DEFAULT 0,
    is_required      INTEGER NOT NULL DEFAULT 1,
    passing_score    INTEGER NOT NULL DEFAULT 70  -- % minimo para aprovacao em quizzes
);

-- Matriculas de usuarios em trilhas
CREATE TABLE IF NOT EXISTS enrollments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    track_id      INTEGER NOT NULL REFERENCES tracks(id),
    status        TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente','em_andamento','concluida','atrasada')),
    progress_pct  REAL NOT NULL DEFAULT 0.0,
    started_at    TEXT,
    due_date      TEXT,
    completed_at  TEXT,
    points_earned INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, track_id)
);

-- Progresso por licao
CREATE TABLE IF NOT EXISTS lesson_progress (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    lesson_id       INTEGER NOT NULL REFERENCES lessons(id),
    module_id       INTEGER NOT NULL REFERENCES modules(id),
    status          TEXT NOT NULL DEFAULT 'nao_iniciada' CHECK(status IN ('nao_iniciada','em_andamento','concluida','reprovada')),
    score           REAL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    started_at      TEXT,
    completed_at    TEXT,
    time_spent_min  REAL NOT NULL DEFAULT 0,
    points_earned   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(user_id, lesson_id)
);

-- Certificacoes emitidas
CREATE TABLE IF NOT EXISTS certifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT NOT NULL,
    score       REAL NOT NULL DEFAULT 0,
    issued_at   TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT,
    revoked_at  TEXT
);

-- Pontos acumulados por usuario
CREATE TABLE IF NOT EXISTS user_points (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL UNIQUE REFERENCES users(id),
    total_points  INTEGER NOT NULL DEFAULT 0,
    week_points   INTEGER NOT NULL DEFAULT 0,
    month_points  INTEGER NOT NULL DEFAULT 0,
    level         INTEGER NOT NULL DEFAULT 1
);

-- Historico de transacoes de pontos
CREATE TABLE IF NOT EXISTS point_transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    amount       INTEGER NOT NULL,
    reason       TEXT NOT NULL,
    reference_id INTEGER,
    description  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Badges disponiveis
CREATE TABLE IF NOT EXISTS badges (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,
    description    TEXT NOT NULL,
    image_url      TEXT,
    category       TEXT NOT NULL CHECK(category IN ('streak','modulo','trilha','performance','especial')),
    condition_json TEXT NOT NULL DEFAULT '{}',
    points_value   INTEGER NOT NULL DEFAULT 25,
    is_secret      INTEGER NOT NULL DEFAULT 0
);

-- Badges conquistados por usuario
CREATE TABLE IF NOT EXISTS user_badges (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(id),
    badge_id  INTEGER NOT NULL REFERENCES badges(id),
    earned_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, badge_id)
);

-- Streaks de estudo
CREATE TABLE IF NOT EXISTS streaks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL UNIQUE REFERENCES users(id),
    current_streak     INTEGER NOT NULL DEFAULT 0,
    longest_streak     INTEGER NOT NULL DEFAULT 0,
    last_activity_date TEXT
);

-- Alertas e notificacoes
CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    type        TEXT NOT NULL,   -- inatividade|certificacao_vencendo|trilha_atrasada|bloqueio_leads
    severity    TEXT NOT NULL CHECK(severity IN ('verde','amarelo','vermelho')),
    title       TEXT NOT NULL,
    message     TEXT NOT NULL,
    channels    TEXT NOT NULL DEFAULT 'discord',  -- discord|email|whatsapp
    sent_at     TEXT NOT NULL DEFAULT (datetime('now')),
    read_at     TEXT,
    resolved_at TEXT
);

-- Bloqueios de leads por nao completar trilha obrigatoria
CREATE TABLE IF NOT EXISTS lead_blocks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    reason       TEXT NOT NULL,
    track_id     INTEGER REFERENCES tracks(id),
    is_active    INTEGER NOT NULL DEFAULT 1,
    blocked_at   TEXT NOT NULL DEFAULT (datetime('now')),
    unlocked_at  TEXT,
    unlocked_by  INTEGER REFERENCES users(id)
);

-- Scores do Crivo de qualidade por chamada
CREATE TABLE IF NOT EXISTS crivo_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    call_id       TEXT,
    call_date     TEXT NOT NULL,
    total_score   REAL NOT NULL DEFAULT 0,
    abertura      REAL NOT NULL DEFAULT 0,
    qualificacao  REAL NOT NULL DEFAULT 0,
    apresentacao  REAL NOT NULL DEFAULT 0,
    objecoes      REAL NOT NULL DEFAULT 0,
    fechamento    REAL NOT NULL DEFAULT 0,
    postura       REAL NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Prescricoes de aprendizado baseadas no Crivo
CREATE TABLE IF NOT EXISTS learning_prescriptions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    crivo_id     INTEGER REFERENCES crivo_scores(id),
    module_id    INTEGER NOT NULL REFERENCES modules(id),
    reason       TEXT NOT NULL,
    priority     INTEGER NOT NULL DEFAULT 1 CHECK(priority IN (1,2,3)),  -- 1=alta 2=media 3=baixa
    status       TEXT NOT NULL DEFAULT 'pendente' CHECK(status IN ('pendente','visualizada','concluida')),
    viewed_at    TEXT,
    completed_at TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Log de acessos para tracking
CREATE TABLE IF NOT EXISTS access_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    action     TEXT NOT NULL,
    metadata   TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indices para performance
CREATE INDEX IF NOT EXISTS idx_enrollments_user ON enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_track ON enrollments(track_id);
CREATE INDEX IF NOT EXISTS idx_lesson_progress_user ON lesson_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_lesson_progress_lesson ON lesson_progress(lesson_id);
CREATE INDEX IF NOT EXISTS idx_point_transactions_user ON point_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved_at);
CREATE INDEX IF NOT EXISTS idx_crivo_user ON crivo_scores(user_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_user ON learning_prescriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_access_log_user ON access_log(user_id);
CREATE INDEX IF NOT EXISTS idx_access_log_created ON access_log(created_at);
