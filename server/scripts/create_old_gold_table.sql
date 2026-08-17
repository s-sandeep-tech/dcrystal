-- DDL for location_wise_old_gold_settlement_transfer_snapshot
CREATE TABLE IF NOT EXISTS location_wise_old_gold_settlement_transfer_snapshot (
    id BIGSERIAL PRIMARY KEY,
    transdate DATE,
    locationname VARCHAR(200),
    office VARCHAR(100),
    division VARCHAR(100),
    groupname VARCHAR(100),
    purity VARCHAR(50),
    grwt NUMERIC(18, 4) DEFAULT 0.0,
    stwt NUMERIC(18, 4) DEFAULT 0.0,
    netwt NUMERIC(18, 4) DEFAULT 0.0,
    settlementmode VARCHAR(100),
    transfer_grwt NUMERIC(18, 4) DEFAULT 0.0,
    transfer_stwt NUMERIC(18, 4) DEFAULT 0.0,
    transfer_netwt NUMERIC(18, 4) DEFAULT 0.0,
    locationtype VARCHAR(100),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_old_gold_transdate ON location_wise_old_gold_settlement_transfer_snapshot (transdate);
CREATE INDEX IF NOT EXISTS ix_old_gold_office ON location_wise_old_gold_settlement_transfer_snapshot (office);
CREATE INDEX IF NOT EXISTS ix_old_gold_locationname ON location_wise_old_gold_settlement_transfer_snapshot (locationname);
CREATE INDEX IF NOT EXISTS ix_old_gold_division ON location_wise_old_gold_settlement_transfer_snapshot (division);
CREATE INDEX IF NOT EXISTS ix_old_gold_groupname ON location_wise_old_gold_settlement_transfer_snapshot (groupname);
CREATE INDEX IF NOT EXISTS ix_old_gold_purity ON location_wise_old_gold_settlement_transfer_snapshot (purity);
