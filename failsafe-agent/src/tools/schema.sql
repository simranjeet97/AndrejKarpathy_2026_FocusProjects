-- Migration and Schema file for Customer & Order system

CREATE TABLE IF NOT EXISTS customers (
    id VARCHAR(50) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    tier VARCHAR(50) NOT NULL DEFAULT 'standard',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES customers(id) ON DELETE CASCADE,
    stripe_charge_id VARCHAR(100) UNIQUE,
    status VARCHAR(50) NOT NULL,
    amount_cents INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tickets (
    id VARCHAR(50) PRIMARY KEY,
    conversation_id VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'open',
    priority VARCHAR(50) NOT NULL,
    context_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS refunds (
    id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES customers(id) ON DELETE CASCADE,
    charge_id VARCHAR(100) NOT NULL,
    amount_cents INTEGER NOT NULL,
    reason VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id VARCHAR(50) PRIMARY KEY,
    conversation_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    actor VARCHAR(50) NOT NULL DEFAULT 'agent',
    payload JSONB NOT NULL,
    hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed Data (3 customers with varied order history)
INSERT INTO customers (id, email, tier) VALUES
('cust_01', 'alice@example.com', 'vip'),
('cust_02', 'bob@example.com', 'standard'),
('cust_03', 'charlie@example.com', 'standard')
ON CONFLICT (id) DO NOTHING;

INSERT INTO orders (id, customer_id, stripe_charge_id, status, amount_cents, created_at) VALUES
('ord_101', 'cust_01', 'ch_stripe_101', 'succeeded', 5000, NOW() - INTERVAL '5 days'),
('ord_102', 'cust_01', 'ch_stripe_102', 'failed', 12000, NOW() - INTERVAL '2 days'),
('ord_103', 'cust_01', 'ch_stripe_103', 'succeeded', 7500, NOW() - INTERVAL '40 days'),
('ord_104', 'cust_02', 'ch_stripe_104', 'succeeded', 2500, NOW() - INTERVAL '10 days'),
('ord_105', 'cust_03', 'ch_stripe_105', 'succeeded', 1500, NOW() - INTERVAL '1 day')
ON CONFLICT (id) DO NOTHING;
