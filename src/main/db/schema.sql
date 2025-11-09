create table if not exists trades (
    ts timestamptz primary key,
    price double precision not null,
    size double precision not null
);