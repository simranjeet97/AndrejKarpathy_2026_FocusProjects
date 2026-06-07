-- SQLite3 Schema for QueryForge

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    segment VARCHAR(50) NOT NULL,
    mrr_cents INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    cancelled_at TEXT
);

CREATE TABLE IF NOT EXISTS churn_events (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    segment TEXT NOT NULL,
    churned_at TEXT NOT NULL,
    reason VARCHAR(200),
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    paid_at TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customers(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_customers_segment ON customers(segment);
CREATE INDEX IF NOT EXISTS idx_customers_cancelled_at ON customers(cancelled_at);
CREATE INDEX IF NOT EXISTS idx_customers_created_at ON customers(created_at);

CREATE INDEX IF NOT EXISTS idx_churn_events_customer_id ON churn_events(customer_id);
CREATE INDEX IF NOT EXISTS idx_churn_events_churned_at ON churn_events(churned_at);
CREATE INDEX IF NOT EXISTS idx_churn_events_segment ON churn_events(segment);

CREATE INDEX IF NOT EXISTS idx_payments_customer_id ON payments(customer_id);
CREATE INDEX IF NOT EXISTS idx_payments_paid_at ON payments(paid_at);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);

-- Seed Data (100 Customers across 5 segments with realistic churn rates)
-- Segments: enterprise, smb, startup, individual, nonprofit

-- 1. Enterprise Customers (10 total, MRR: $5000 = 500000 cents, Churn target: ~2% / none)
INSERT INTO customers VALUES ('cust-ent-001', 'acme@enterprise.com', 'enterprise', 500000, '2026-01-15 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-002', 'globex@enterprise.com', 'enterprise', 500000, '2026-01-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-003', 'initech@enterprise.com', 'enterprise', 500000, '2026-02-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-004', 'hooli@enterprise.com', 'enterprise', 500000, '2026-02-15 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-005', 'vehement@enterprise.com', 'enterprise', 500000, '2026-03-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-006', 'massive-dynamic@enterprise.com', 'enterprise', 500000, '2026-03-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-007', 'umbrella@enterprise.com', 'enterprise', 500000, '2026-04-05 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-008', 'tyrell@enterprise.com', 'enterprise', 500000, '2026-04-12 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-009', 'cyberdyne@enterprise.com', 'enterprise', 500000, '2026-05-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ent-010', 'wonka@enterprise.com', 'enterprise', 500000, '2026-05-10 00:00:00', '2026-05-30 00:00:00');

-- 2. SMB Customers (20 total, MRR: $1000 = 100000 cents, Churn target: ~4% = 1 churned)
INSERT INTO customers VALUES ('cust-smb-001', 'bakery@smb.com', 'smb', 100000, '2026-01-05 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-002', 'florist@smb.com', 'smb', 100000, '2026-01-12 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-003', 'dentist@smb.com', 'smb', 100000, '2026-01-18 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-004', 'lawyer@smb.com', 'smb', 100000, '2026-01-22 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-005', 'plumber@smb.com', 'smb', 100000, '2026-02-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-006', 'electrician@smb.com', 'smb', 100000, '2026-02-05 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-007', 'accounting@smb.com', 'smb', 100000, '2026-02-12 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-008', 'gym@smb.com', 'smb', 100000, '2026-02-19 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-009', 'salon@smb.com', 'smb', 100000, '2026-02-25 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-010', 'cafe@smb.com', 'smb', 100000, '2026-03-04 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-011', 'boutique@smb.com', 'smb', 100000, '2026-03-12 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-012', 'consulting@smb.com', 'smb', 100000, '2026-03-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-013', 'clinic@smb.com', 'smb', 100000, '2026-03-27 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-014', 'agency@smb.com', 'smb', 100000, '2026-04-02 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-015', 'workshop@smb.com', 'smb', 100000, '2026-04-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-016', 'catering@smb.com', 'smb', 100000, '2026-04-18 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-017', 'design@smb.com', 'smb', 100000, '2026-04-26 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-018', 'architecture@smb.com', 'smb', 100000, '2026-05-02 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-019', 'marketing@smb.com', 'smb', 100000, '2026-05-15 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-smb-020', 'printing@smb.com', 'smb', 100000, '2026-05-22 00:00:00', '2026-05-31 00:00:00');

-- 3. Startup Customers (30 total, MRR: $500 = 50000 cents, Churn target: ~8% = 2-3 churned)
INSERT INTO customers VALUES ('cust-str-001', 'fintech@startup.com', 'startup', 50000, '2026-01-02 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-002', 'biotech@startup.com', 'startup', 50000, '2026-01-08 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-003', 'edtech@startup.com', 'startup', 50000, '2026-01-14 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-004', 'healthtech@startup.com', 'startup', 50000, '2026-01-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-005', 'proptech@startup.com', 'startup', 50000, '2026-01-26 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-006', 'cleantech@startup.com', 'startup', 50000, '2026-02-02 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-007', 'insurtech@startup.com', 'startup', 50000, '2026-02-08 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-008', 'civictech@startup.com', 'startup', 50000, '2026-02-14 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-009', 'legaltech@startup.com', 'startup', 50000, '2026-02-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-010', 'hrtech@startup.com', 'startup', 50000, '2026-02-26 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-011', 'adtech@startup.com', 'startup', 50000, '2026-03-02 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-012', 'retailtech@startup.com', 'startup', 50000, '2026-03-08 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-013', 'martech@startup.com', 'startup', 50000, '2026-03-14 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-014', 'foodtech@startup.com', 'startup', 50000, '2026-03-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-015', 'agritech@startup.com', 'startup', 50000, '2026-03-26 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-016', 'spacetech@startup.com', 'startup', 50000, '2026-04-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-017', 'deeptech@startup.com', 'startup', 50000, '2026-04-07 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-018', 'nanotech@startup.com', 'startup', 50000, '2026-04-13 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-019', 'robotics@startup.com', 'startup', 50000, '2026-04-19 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-020', 'drones@startup.com', 'startup', 50000, '2026-04-25 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-021', 'ai@startup.com', 'startup', 50000, '2026-05-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-022', 'quantum@startup.com', 'startup', 50000, '2026-05-06 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-023', 'vr@startup.com', 'startup', 50000, '2026-05-12 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-024', 'ar@startup.com', 'startup', 50000, '2026-05-18 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-025', 'gaming@startup.com', 'startup', 50000, '2026-05-24 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-str-026', 'crypto@startup.com', 'startup', 50000, '2026-05-28 00:00:00', NULL);
-- Churned Startups
INSERT INTO customers VALUES ('cust-str-027', 'wearables@startup.com', 'startup', 50000, '2026-01-10 00:00:00', '2026-05-15 00:00:00');
INSERT INTO customers VALUES ('cust-str-028', 'web3@startup.com', 'startup', 50000, '2026-02-15 00:00:00', '2026-05-20 00:00:00');
INSERT INTO customers VALUES ('cust-str-029', 'metaverse@startup.com', 'startup', 50000, '2026-03-01 00:00:00', '2026-05-25 00:00:00');
INSERT INTO customers VALUES ('cust-str-030', 'nft@startup.com', 'startup', 50000, '2026-04-10 00:00:00', NULL);

-- 4. Individual Customers (30 total, MRR: $50 = 5000 cents, Churn target: ~12% = 3-4 churned)
INSERT INTO customers VALUES ('cust-ind-001', 'alice@gmail.com', 'individual', 5000, '2026-01-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-002', 'bob@gmail.com', 'individual', 5000, '2026-01-05 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-003', 'charlie@gmail.com', 'individual', 5000, '2026-01-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-004', 'dave@gmail.com', 'individual', 5000, '2026-01-15 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-005', 'eve@gmail.com', 'individual', 5000, '2026-01-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-006', 'frank@gmail.com', 'individual', 5000, '2026-01-25 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-007', 'grace@gmail.com', 'individual', 5000, '2026-02-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-008', 'heidi@gmail.com', 'individual', 5000, '2026-02-05 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-009', 'ivan@gmail.com', 'individual', 5000, '2026-02-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-010', 'judy@gmail.com', 'individual', 5000, '2026-02-15 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-011', 'mallory@gmail.com', 'individual', 5000, '2026-02-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-012', 'oscar@gmail.com', 'individual', 5000, '2026-02-25 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-013', 'peggy@gmail.com', 'individual', 5000, '2026-03-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-014', 'rupert@gmail.com', 'individual', 5000, '2026-03-05 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-015', 'sybil@gmail.com', 'individual', 5000, '2026-03-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-016', 'trent@gmail.com', 'individual', 5000, '2026-03-15 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-017', 'victor@gmail.com', 'individual', 5000, '2026-03-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-018', 'walter@gmail.com', 'individual', 5000, '2026-03-25 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-019', 'zoe@gmail.com', 'individual', 5000, '2026-04-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-020', 'arthur@gmail.com', 'individual', 5000, '2026-04-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-021', 'clara@gmail.com', 'individual', 5000, '2026-04-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-022', 'george@gmail.com', 'individual', 5000, '2026-05-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-023', 'harriet@gmail.com', 'individual', 5000, '2026-05-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-024', 'leo@gmail.com', 'individual', 5000, '2026-05-18 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-025', 'max@gmail.com', 'individual', 5000, '2026-05-24 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-ind-026', 'norman@gmail.com', 'individual', 5000, '2026-05-29 00:00:00', NULL);
-- Churned Individuals
INSERT INTO customers VALUES ('cust-ind-027', 'charlotte@gmail.com', 'individual', 5000, '2026-01-02 00:00:00', '2026-05-10 00:00:00');
INSERT INTO customers VALUES ('cust-ind-028', 'dennis@gmail.com', 'individual', 5000, '2026-02-04 00:00:00', '2026-05-15 00:00:00');
INSERT INTO customers VALUES ('cust-ind-029', 'fiona@gmail.com', 'individual', 5000, '2026-03-06 00:00:00', '2026-05-22 00:00:00');
INSERT INTO customers VALUES ('cust-ind-030', 'ian@gmail.com', 'individual', 5000, '2026-04-12 00:00:00', '2026-05-28 00:00:00');

-- 5. Nonprofit Customers (10 total, MRR: $100 = 10000 cents, Churn target: ~3% = none/low)
INSERT INTO customers VALUES ('cust-npo-001', 'redcross@nonprofit.org', 'nonprofit', 10000, '2026-01-10 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-002', 'greenpeace@nonprofit.org', 'nonprofit', 10000, '2026-01-15 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-003', 'unicef@nonprofit.org', 'nonprofit', 10000, '2026-02-05 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-004', 'wwf@nonprofit.org', 'nonprofit', 10000, '2026-02-20 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-005', 'doctors@nonprofit.org', 'nonprofit', 10000, '2026-03-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-006', 'amnesty@nonprofit.org', 'nonprofit', 10000, '2026-03-15 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-007', 'oxfam@nonprofit.org', 'nonprofit', 10000, '2026-04-05 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-008', 'habitat@nonprofit.org', 'nonprofit', 10000, '2026-04-18 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-009', 'salvation@nonprofit.org', 'nonprofit', 10000, '2026-05-01 00:00:00', NULL);
INSERT INTO customers VALUES ('cust-npo-010', 'goodwill@nonprofit.org', 'nonprofit', 10000, '2026-05-15 00:00:00', '2026-05-30 00:00:00');


-- Churn Events (Corresponding to cancelled_at timestamps)
INSERT INTO churn_events VALUES ('churn-ent-010', 'cust-ent-010', 'enterprise', '2026-05-30 00:00:00', 'Pricing issues');
INSERT INTO churn_events VALUES ('churn-smb-020', 'cust-smb-020', 'smb', '2026-05-31 00:00:00', 'Competitor features');
INSERT INTO churn_events VALUES ('churn-str-027', 'cust-str-027', 'startup', '2026-05-15 00:00:00', 'Out of business');
INSERT INTO churn_events VALUES ('churn-str-028', 'cust-str-028', 'startup', '2026-05-20 00:00:00', 'Product dissatisfaction');
INSERT INTO churn_events VALUES ('churn-str-029', 'cust-str-029', 'startup', '2026-05-25 00:00:00', 'Budget cuts');
INSERT INTO churn_events VALUES ('churn-ind-027', 'cust-ind-027', 'individual', '2026-05-10 00:00:00', 'No longer needed');
INSERT INTO churn_events VALUES ('churn-ind-028', 'cust-ind-028', 'individual', '2026-05-15 00:00:00', 'Found alternative');
INSERT INTO churn_events VALUES ('churn-ind-029', 'cust-ind-029', 'individual', '2026-05-22 00:00:00', 'Too expensive');
INSERT INTO churn_events VALUES ('churn-ind-030', 'cust-ind-030', 'individual', '2026-05-28 00:00:00', 'Unstable service');
INSERT INTO churn_events VALUES ('churn-npo-010', 'cust-npo-010', 'nonprofit', '2026-05-30 00:00:00', 'Grant expired');


-- Payments (Historic successful monthly payments)
-- Enterprise payments
INSERT INTO payments VALUES ('pay-ent-101', 'cust-ent-001', 500000, '2026-02-15 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-102', 'cust-ent-001', 500000, '2026-03-15 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-103', 'cust-ent-001', 500000, '2026-04-15 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-104', 'cust-ent-001', 500000, '2026-05-15 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-201', 'cust-ent-002', 500000, '2026-02-20 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-202', 'cust-ent-002', 500000, '2026-03-20 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-203', 'cust-ent-002', 500000, '2026-04-20 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-204', 'cust-ent-002', 500000, '2026-05-20 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-301', 'cust-ent-003', 500000, '2026-03-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-302', 'cust-ent-003', 500000, '2026-04-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-303', 'cust-ent-003', 500000, '2026-05-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ent-401', 'cust-ent-010', 500000, '2026-05-10 00:00:00', 'succeeded');

-- SMB payments
INSERT INTO payments VALUES ('pay-smb-101', 'cust-smb-001', 100000, '2026-02-05 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-smb-102', 'cust-smb-001', 100000, '2026-03-05 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-smb-103', 'cust-smb-001', 100000, '2026-04-05 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-smb-104', 'cust-smb-001', 100000, '2026-05-05 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-smb-201', 'cust-smb-002', 100000, '2026-02-12 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-smb-202', 'cust-smb-002', 100000, '2026-03-12 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-smb-203', 'cust-smb-002', 100000, '2026-04-12 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-smb-204', 'cust-smb-002', 100000, '2026-05-12 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-smb-301', 'cust-smb-020', 100000, '2026-05-22 00:00:00', 'succeeded');

-- Startup payments
INSERT INTO payments VALUES ('pay-str-101', 'cust-str-001', 50000, '2026-02-02 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-102', 'cust-str-001', 50000, '2026-03-02 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-103', 'cust-str-001', 50000, '2026-04-02 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-104', 'cust-str-001', 50000, '2026-05-02 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-201', 'cust-str-027', 50000, '2026-02-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-202', 'cust-str-027', 50000, '2026-03-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-203', 'cust-str-027', 50000, '2026-04-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-204', 'cust-str-027', 50000, '2026-05-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-301', 'cust-str-028', 50000, '2026-03-15 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-302', 'cust-str-028', 50000, '2026-04-15 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-303', 'cust-str-028', 50000, '2026-05-15 00:00:00', 'failed');
INSERT INTO payments VALUES ('pay-str-401', 'cust-str-029', 50000, '2026-04-01 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-str-402', 'cust-str-029', 50000, '2026-05-01 00:00:00', 'succeeded');

-- Individual payments
INSERT INTO payments VALUES ('pay-ind-101', 'cust-ind-001', 5000, '2026-02-01 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-102', 'cust-ind-001', 5000, '2026-03-01 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-103', 'cust-ind-001', 5000, '2026-04-01 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-104', 'cust-ind-001', 5000, '2026-05-01 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-201', 'cust-ind-027', 5000, '2026-02-02 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-202', 'cust-ind-027', 5000, '2026-03-02 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-203', 'cust-ind-027', 5000, '2026-04-02 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-204', 'cust-ind-027', 5000, '2026-05-02 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-301', 'cust-ind-028', 5000, '2026-03-04 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-302', 'cust-ind-028', 5000, '2026-04-04 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-303', 'cust-ind-028', 5000, '2026-05-04 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-401', 'cust-ind-029', 5000, '2026-04-06 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-402', 'cust-ind-029', 5000, '2026-05-06 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-ind-501', 'cust-ind-030', 5000, '2026-05-12 00:00:00', 'succeeded');

-- Nonprofit payments
INSERT INTO payments VALUES ('pay-npo-101', 'cust-npo-001', 10000, '2026-02-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-npo-102', 'cust-npo-001', 10000, '2026-03-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-npo-103', 'cust-npo-001', 10000, '2026-04-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-npo-104', 'cust-npo-001', 10000, '2026-05-10 00:00:00', 'succeeded');
INSERT INTO payments VALUES ('pay-npo-201', 'cust-npo-010', 10000, '2026-05-15 00:00:00', 'succeeded');
