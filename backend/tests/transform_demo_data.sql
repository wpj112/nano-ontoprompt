-- Test data for transform engine demo cases
-- Run inside the nano-ontoprompt-db-1 container or via psql

-- ── Suppliers table ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    code        VARCHAR(50) PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    credit_level VARCHAR(20),
    score       INTEGER DEFAULT 0,
    location    VARCHAR(200),
    phone       VARCHAR(50),
    status      VARCHAR(20) DEFAULT 'active',
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW()
);

-- ── Quality checks table ─────────────────────────────────
CREATE TABLE IF NOT EXISTS quality_checks (
    id          SERIAL PRIMARY KEY,
    supplier_code VARCHAR(50) NOT NULL,
    score       INTEGER NOT NULL,
    inspector   VARCHAR(100),
    check_date  DATE NOT NULL,
    result      VARCHAR(20) NOT NULL,   -- pass / fail
    remarks     TEXT
);

-- ── Test data ────────────────────────────────────────────

DELETE FROM quality_checks;
DELETE FROM suppliers;

INSERT INTO suppliers (code, name, credit_level, score, location, phone, status, created_at, updated_at)
VALUES
  ('SUP-001', '  东方钢铁有限公司  ', 'A+', 92, '上海市宝山区', '021-12345678  ', 'active',   '2024-01-15 10:00:00', '2026-07-01 14:00:00'),
  ('SUP-002', '华兴电子   ',            'B',  78, '深圳市龙岗区', '0755-88889999', 'active',   '2024-03-20 10:00:00', '2026-06-28 09:00:00'),
  ('SUP-003', 'BLUE TECH INC.',         'A',  85, 'NEW YORK, USA', '+1-212-555-0188', 'inactive', '2024-06-01 10:00:00', '2026-05-10 10:00:00'),
  ('SUP-004', '天山矿业集团',           'C',  45, '乌鲁木齐市新市区', '0991-66668888', 'active', '2025-01-01 10:00:00', '2026-07-01 08:00:00');

INSERT INTO quality_checks (supplier_code, score, inspector, check_date, result, remarks)
VALUES
  ('SUP-001', 95, '张工', '2026-01-10', 'pass', 'excellent'),
  ('SUP-001', 88, '李工', '2026-03-15', 'pass', 'good'),
  ('SUP-001', 92, '张工', '2026-06-20', 'pass', 'normal'),
  ('SUP-002', 72, '王工', '2026-02-10', 'pass', 'ok'),
  ('SUP-002', 68, '李工', '2026-05-05', 'pass', 'marginal'),
  ('SUP-003', 80, '张工', '2026-01-20', 'pass', 'good'),
  ('SUP-003', 55, '王工', '2026-04-10', 'fail', 'quality issue'),
  ('SUP-004', 60, '张工', '2026-01-05', 'pass', 'basic'),
  ('SUP-004', 40, '李工', '2026-03-01', 'fail', 'critical'),
  ('SUP-004', 50, '王工', '2026-06-15', 'fail', 'unacceptable');
