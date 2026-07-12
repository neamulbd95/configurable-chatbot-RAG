-- Seed schema/data for the source RDBMS, matching config/tables.example.yaml
-- and config/eval_set.example.yaml so the pipeline has real data to ingest
-- and query out of the box. Runs once, automatically, on first container
-- startup (standard postgres image behavior for /docker-entrypoint-initdb.d).

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL,
    in_stock BOOLEAN NOT NULL DEFAULT true,
    internal_notes TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL,
    total NUMERIC(10, 2) NOT NULL,
    internal_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- products:1 and products:5 line up with config/eval_set.example.yaml's
-- expected_record_ids, so scripts/eval_retrieval.py works unmodified too.
INSERT INTO products (id, name, price, in_stock, internal_notes) VALUES
    (1, 'Widget', 19.50, true, 'Top seller, restock weekly'),
    (2, 'Gadget', 45.00, false, 'Supplier delayed'),
    (3, 'Gizmo', 12.99, true, NULL),
    (4, 'Doohickey', 8.25, true, 'Discontinuing next quarter'),
    (5, 'Thingamajig', 99.99, false, 'Awaiting new shipment');
SELECT setval('products_id_seq', (SELECT max(id) FROM products));

INSERT INTO orders (product_id, quantity, total, internal_notes) VALUES
    (1, 3, 58.50, NULL),
    (1, 1, 19.50, 'Rush order'),
    (3, 5, 64.95, NULL);
