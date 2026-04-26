-- 020_booking_reminders.sql
-- Track per-booking reminder dispatch + user confirmation for the 2h reminder flow.

alter table bookings add column if not exists reminder_sent_at timestamptz;
alter table bookings add column if not exists confirmed_at     timestamptz;

create index if not exists bookings_reminder_due_idx
  on bookings(scheduled_at)
  where status = 'scheduled' and reminder_sent_at is null;
