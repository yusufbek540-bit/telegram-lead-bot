-- 019_bookings_and_intake.sql
-- Cal.com bookings table + intake field columns on leads.

create table if not exists bookings (
  id              bigserial primary key,
  telegram_id     bigint references leads(telegram_id) on delete cascade,
  cal_booking_id  text unique not null,
  cal_booking_uid text,
  scheduled_at    timestamptz not null,
  ends_at         timestamptz,
  status          text not null default 'scheduled',
  attendee_name   text,
  attendee_email  text,
  reschedule_url  text,
  cancel_url      text,
  raw_payload     jsonb,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index if not exists bookings_telegram_id_idx on bookings(telegram_id);
create index if not exists bookings_status_idx       on bookings(status);
create index if not exists bookings_scheduled_at_idx on bookings(scheduled_at);

alter table leads add column if not exists booking_status   text;
alter table leads add column if not exists next_session_at  timestamptz;
alter table leads add column if not exists website          text;
alter table leads add column if not exists social_handle    text;
