CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SEQUENCE IF NOT EXISTS service_order_number_seq START 1;
CREATE SEQUENCE IF NOT EXISTS mechanic_application_number_seq START 1;

CREATE TABLE IF NOT EXISTS customers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    wa_number text UNIQUE NOT NULL,
    name text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS technician_applications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    application_no text UNIQUE NOT NULL,
    wa_number text UNIQUE NOT NULL,
    name text,
    domicile text,
    base_lat double precision,
    base_lon double precision,
    base_address text,
    service_radius_km double precision NOT NULL DEFAULT 25,
    years_experience integer,
    vehicle text,
    profile_photo_path text,
    top_skills text[] NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'DRAFT',
    submitted_at timestamptz,
    reviewed_at timestamptz,
    review_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_technician_applications_status
    ON technician_applications(status, created_at DESC);

CREATE TABLE IF NOT EXISTS technician_application_skills (
    application_id uuid NOT NULL REFERENCES technician_applications(id) ON DELETE CASCADE,
    skill_code text NOT NULL,
    skill_name text NOT NULL,
    self_level integer NOT NULL CHECK (self_level BETWEEN 0 AND 5),
    is_top_skill boolean NOT NULL DEFAULT false,
    PRIMARY KEY(application_id, skill_code)
);

CREATE TABLE IF NOT EXISTS technician_skill_answers (
    id bigserial PRIMARY KEY,
    application_id uuid NOT NULL REFERENCES technician_applications(id) ON DELETE CASCADE,
    skill_code text NOT NULL,
    question_no integer NOT NULL,
    question_text text NOT NULL,
    answer_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(application_id, skill_code, question_no)
);

CREATE TABLE IF NOT EXISTS technicians (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    wa_number text UNIQUE NOT NULL,
    domicile text,
    base_lat double precision NOT NULL,
    base_lon double precision NOT NULL,
    base_address text,
    current_lat double precision,
    current_lon double precision,
    current_location_at timestamptz,
    service_radius_km double precision NOT NULL DEFAULT 25,
    years_experience integer NOT NULL DEFAULT 0,
    vehicle text,
    profile_photo_path text,
    is_active boolean NOT NULL DEFAULT true,
    is_available boolean NOT NULL DEFAULT true,
    jobs_completed integer NOT NULL DEFAULT 0,
    jobs_cancelled integer NOT NULL DEFAULT 0,
    rating numeric(3,2) NOT NULL DEFAULT 5.00,
    source_application_id uuid REFERENCES technician_applications(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS technician_skill_matrix (
    technician_id uuid NOT NULL REFERENCES technicians(id) ON DELETE CASCADE,
    skill_code text NOT NULL,
    skill_name text NOT NULL,
    level integer NOT NULL CHECK (level BETWEEN 0 AND 5),
    verified boolean NOT NULL DEFAULT false,
    source_application_id uuid REFERENCES technician_applications(id),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(technician_id, skill_code)
);

CREATE INDEX IF NOT EXISTS idx_technician_skill_matrix_match
    ON technician_skill_matrix(skill_code, level DESC);

CREATE TABLE IF NOT EXISTS service_orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_no text UNIQUE NOT NULL,
    customer_id uuid NOT NULL REFERENCES customers(id),
    status text NOT NULL DEFAULT 'COLLECTING_INFORMATION',
    location_lat double precision,
    location_lon double precision,
    location_name text,
    location_address text,
    location_landmark text,
    location_source text,
    location_confirmed boolean NOT NULL DEFAULT false,
    assigned_technician_id uuid REFERENCES technicians(id),
    selected_distance_km numeric(10,2),
    booking_fee bigint NOT NULL DEFAULT 0,
    booking_payment_status text NOT NULL DEFAULT 'UNPAID',
    final_payment_status text NOT NULL DEFAULT 'NOT_DUE',
    final_amount_due bigint NOT NULL DEFAULT 0,
    close_reason text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_service_orders_customer ON service_orders(customer_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_service_orders_status ON service_orders(status, created_at DESC);

CREATE TABLE IF NOT EXISTS service_order_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    item_no integer NOT NULL,
    machine_category_code text,
    machine_category_name text,
    machine_text text NOT NULL,
    complaint text NOT NULL DEFAULT '',
    declared_by text NOT NULL DEFAULT 'CUSTOMER',
    status text NOT NULL DEFAULT 'DECLARED',
    difficulty text,
    diagnosis text,
    inspection_fee bigint NOT NULL DEFAULT 0,
    repair_fee bigint NOT NULL DEFAULT 0,
    parts_fee bigint NOT NULL DEFAULT 0,
    customer_approved boolean,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(order_id, item_no)
);

CREATE TABLE IF NOT EXISTS service_order_status_history (
    id bigserial PRIMARY KEY,
    order_id uuid NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    old_status text,
    new_status text NOT NULL,
    actor_type text NOT NULL,
    actor_ref text,
    note text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS job_offers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    technician_id uuid NOT NULL REFERENCES technicians(id),
    status text NOT NULL DEFAULT 'PENDING',
    distance_km numeric(10,2) NOT NULL,
    coverage numeric(5,2) NOT NULL DEFAULT 0,
    average_skill numeric(5,2) NOT NULL DEFAULT 0,
    customer_rank integer,
    offered_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    responded_at timestamptz,
    UNIQUE(order_id, technician_id)
);

CREATE INDEX IF NOT EXISTS idx_job_offers_pending ON job_offers(status, expires_at);

CREATE TABLE IF NOT EXISTS payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid NOT NULL REFERENCES service_orders(id) ON DELETE CASCADE,
    kind text NOT NULL,
    amount bigint NOT NULL,
    status text NOT NULL DEFAULT 'PENDING',
    provider text NOT NULL DEFAULT 'MANUAL',
    proof_path text,
    external_ref text,
    created_at timestamptz NOT NULL DEFAULT now(),
    proof_submitted_at timestamptz,
    paid_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_payments_order ON payments(order_id, kind, created_at DESC);

CREATE TABLE IF NOT EXISTS attachments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid REFERENCES service_orders(id) ON DELETE CASCADE,
    item_id uuid REFERENCES service_order_items(id) ON DELETE CASCADE,
    actor_type text NOT NULL,
    actor_ref text,
    purpose text NOT NULL,
    media_type text NOT NULL,
    local_path text,
    message_id text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS conversation_states (
    wa_number text PRIMARY KEY,
    state text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    expires_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS service_price_matrix (
    skill_code text PRIMARY KEY,
    skill_name text NOT NULL,
    inspection_fee bigint NOT NULL DEFAULT 0,
    light_fee bigint NOT NULL DEFAULT 0,
    medium_fee bigint NOT NULL DEFAULT 0,
    heavy_fee bigint NOT NULL DEFAULT 0,
    special_requires_quote boolean NOT NULL DEFAULT true,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS settlements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid NOT NULL UNIQUE REFERENCES service_orders(id) ON DELETE CASCADE,
    outcome text NOT NULL,
    gross_amount bigint NOT NULL DEFAULT 0,
    customer_refund bigint NOT NULL DEFAULT 0,
    technician_payout bigint NOT NULL DEFAULT 0,
    platform_fee bigint NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'PENDING_OWNER',
    approved_at timestamptz,
    paid_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id bigserial PRIMARY KEY,
    actor_type text NOT NULL,
    actor_ref text,
    action text NOT NULL,
    object_type text,
    object_ref text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS processed_messages (
    message_id text PRIMARY KEY,
    sender text,
    processed_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO service_price_matrix(skill_code, skill_name) VALUES
('JARUM_1','Jarum 1'),
('JARUM_2','Jarum 2'),
('OBRAS','Obras'),
('OVERDECK','Overdeck'),
('KANSAI','Kansai'),
('BARTACK','Bartack'),
('LUBANG_KANCING','Lubang Kancing'),
('PASANG_KANCING','Pasang Kancing'),
('WALKINGFOOT','Walkingfoot'),
('ZIGZAG','Zigzag'),
('DIE_CUTTING','Die Cutting'),
('AUTO_CUTTER','Auto Cutter'),
('AUTO_SPREADING','Auto Spreading'),
('ELEKTRONIK_SERVO','Elektronik Servo'),
('LUBANG_RIS','Lubang Ris'),
('BOBOK_KANTONG','Bobok Kantong'),
('AUTO_TEMPLATE','Auto Template'),
('SOFTWARE_DESIGN','Software Design')
ON CONFLICT(skill_code) DO NOTHING;
