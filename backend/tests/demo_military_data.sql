-- Military Air Defense Demo — test data
-- =========================================

-- ── Radar stations ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS radars (
    code        VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    position    VARCHAR(200),
    max_range   INTEGER DEFAULT 400,
    frequency   VARCHAR(20),
    scan_mode   VARCHAR(20) DEFAULT 'normal',
    status      VARCHAR(20) DEFAULT 'active',
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- ── Missile launchers ────────────────────────────────────
CREATE TABLE IF NOT EXISTS launchers (
    code        VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    position    VARCHAR(200),
    missiles    INTEGER DEFAULT 8,
    missile_type VARCHAR(20) DEFAULT 'HQ-9B',
    command_center VARCHAR(50),
    status      VARCHAR(20) DEFAULT 'standby',
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- ── Threats ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS threats (
    code        VARCHAR(20) PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    threat_type VARCHAR(30),
    speed       INTEGER DEFAULT 800,
    altitude    INTEGER DEFAULT 5000,
    heading     INTEGER DEFAULT 0,
    distance    INTEGER DEFAULT 300,
    detected_by VARCHAR(20),
    status      VARCHAR(20) DEFAULT 'tracking',
    detected_at TIMESTAMP DEFAULT NOW()
);

-- ── Clear existing ───────────────────────────────────────
DELETE FROM threats;
DELETE FROM launchers;
DELETE FROM radars;

-- ── Radars ──────────────────────────────────────────────
INSERT INTO radars (code, name, position, max_range, frequency, scan_mode, status, updated_at) VALUES
  ('R-001', '   东海前哨雷达站  ', '浙江舟山', 450, 'S波段', 'tracking', 'active', '2026-07-14 08:00:00'),
  ('R-002', '南海礁岛雷达',       '南沙群岛', 400, 'X波段', 'normal',   'active', '2026-07-14 08:00:00'),
  ('R-003', '西部防空雷达',       '新疆喀什', 500, 'L波段', 'scanning', 'active', '2026-07-14 07:30:00');

-- ── Missile launchers ───────────────────────────────────
INSERT INTO launchers (code, name, position, missiles, missile_type, command_center, status, updated_at) VALUES
  ('M-001', '红旗-9B 一连', '浙江宁波', 8, 'HQ-9B',  '东部战区指挥中心', 'standby', '2026-07-14 08:00:00'),
  ('M-002', '红旗-9B 二连', '上海崇明', 6, 'HQ-9B',  '东部战区指挥中心', 'standby', '2026-07-14 08:00:00'),
  ('M-003', '红旗-16 一连', '南沙永暑', 12,'HQ-16',  '南部战区指挥中心', 'standby', '2026-07-14 08:00:00');

-- ── Threats ──────────────────────────────────────────────
INSERT INTO threats (code, name, threat_type, speed, altitude, heading, distance, detected_by, status, detected_at) VALUES
  ('T-001', '不明飞行器 A', 'UAV',      650,  3000, 180, 280, 'R-001', 'tracking', '2026-07-14 09:00:00'),
  ('T-002', '不明飞行器 B', 'fighter',  1200, 8000, 270, 150, 'R-001', 'tracking', '2026-07-14 09:15:00'),
  ('T-003', '不明飞行器 C', 'UAV',      450,  2000,  90, 350, 'R-002', 'tracking', '2026-07-14 09:30:00'),
  ('T-004', '不明飞行器 D', 'fighter',  1500, 1000, 315,  80, 'R-003', 'warning', '2026-07-14 09:45:00'),
  ('T-005', '不明飞行器 E', 'UAV',      500,  2500,   0, 420, 'R-003', 'tracking', '2026-07-14 10:00:00');

-- ── Engagement records ───────────────────────────────────
CREATE TABLE IF NOT EXISTS engagements (
    id          SERIAL PRIMARY KEY,
    launcher_code VARCHAR(20),
    threat_code   VARCHAR(20),
    engagement_status VARCHAR(20) DEFAULT 'assigned',
    assigned_at    TIMESTAMP DEFAULT NOW(),
    completed_at   TIMESTAMP
);

DELETE FROM engagements;
INSERT INTO engagements (launcher_code, threat_code, engagement_status, assigned_at) VALUES
  ('M-001', 'T-002', 'assigned', '2026-07-14 10:30:00'),
  ('M-002', 'T-004', 'assigned', '2026-07-14 10:35:00');
