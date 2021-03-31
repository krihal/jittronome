
CREATE TABLE measurements (
	id			bigserial PRIMARY KEY,
	tick			bigint NOT NULL,
	description		text NOT NULL,
	timestamp_ms		decimal NOT NULL,
	timestamp_insert	timestamp with time zone DEFAULT NOW()
);

CREATE INDEX measurements_idx ON measurements (id);
