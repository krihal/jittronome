
CREATE TABLE measurements (
	id			bigserial PRIMARY KEY,
	tick			bigint NOT NULL,
	description		text NOT NULL,
	timestamp_tx		decimal,
	timestamp_rx		decimal,
	timestamp_db		timestamp with time zone DEFAULT NOW()
);

CREATE INDEX measurements_idx ON measurements (id);
