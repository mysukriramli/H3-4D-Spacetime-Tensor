CREATE SEQUENCE IF NOT EXISTS seq_commit_id START 1;

CREATE TABLE IF NOT EXISTS spacetime_tensor (
    tensor_coord VARCHAR PRIMARY KEY,
    h3_index VARCHAR,
    resolution INTEGER,
    latitude DOUBLE,
    longitude DOUBLE,
    depth_altitude_layer VARCHAR,
    time_bucket_utc VARCHAR,
    event_type VARCHAR,
    magnitude DOUBLE,
    feature_vector_json VARCHAR,
    content_hash VARCHAR,
    observed_at_utc VARCHAR
);

CREATE TABLE IF NOT EXISTS tensor_ledger (
    commit_id BIGINT PRIMARY KEY,
    timestamp_utc VARCHAR,
    operation VARCHAR,
    tensor_coord VARCHAR,
    h3_index VARCHAR,
    detail VARCHAR
);
