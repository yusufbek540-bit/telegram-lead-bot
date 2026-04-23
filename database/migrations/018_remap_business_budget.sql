-- One-time backfill: remap legacy business_type and budget_range keys
-- to the new taxonomy (see bot/keyboards/questionnaire.py & twa/index.html).
-- Safe to run multiple times — each UPDATE is idempotent.

BEGIN;

-- ── business_type ─────────────────────────────────────────────
-- Legacy keys: restaurant, retail, service, it, beauty, education, other
-- New keys:    health, beauty, realestate, education, auto, b2b,
--              consulting, ecommerce, fitness, horeca, fmcg, other

UPDATE leads SET business_type = 'horeca'     WHERE business_type = 'restaurant';
UPDATE leads SET business_type = 'ecommerce'  WHERE business_type = 'retail';
UPDATE leads SET business_type = 'b2b'        WHERE business_type = 'service';
UPDATE leads SET business_type = 'b2b'        WHERE business_type = 'it';
-- 'beauty', 'education', 'other' keep the same key — no-op.

-- ── budget_range ──────────────────────────────────────────────
-- Legacy keys: 200_500, under_500, 500_1000, 1000_3000, 3000, 3000_plus, unknown
-- New keys:    1000_1500, 2000_3000, 3000_5000, 5000_plus

UPDATE leads SET budget_range = '1000_1500'  WHERE budget_range IN ('200_500', 'under_500', '500_1000');
UPDATE leads SET budget_range = '2000_3000'  WHERE budget_range = '1000_3000';
UPDATE leads SET budget_range = '5000_plus'  WHERE budget_range IN ('3000', '3000_plus');
UPDATE leads SET budget_range = NULL         WHERE budget_range = 'unknown';

COMMIT;

-- Sanity check — run separately after the transaction:
-- SELECT business_type, COUNT(*) FROM leads GROUP BY business_type ORDER BY 2 DESC;
-- SELECT budget_range,  COUNT(*) FROM leads GROUP BY budget_range  ORDER BY 2 DESC;
