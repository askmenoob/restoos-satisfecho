-- Satisfecho initial install compatibility shim for SQLModel native enums.
-- Runs only when the isolated PostgreSQL data directory is first initialized.
-- The upstream migration runner later verifies and adds any schema changes.
DO $$ BEGIN CREATE TYPE user_role AS ENUM ('owner','admin','kitchen','waiter','receptionist','bartender','courier','provider','platform_operator'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE staff_contract_kind AS ENUM ('employee','freelancer'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE staff_contract_status AS ENUM ('draft','pending_signature','active','expired','superseded'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE staff_contract_payment_structure AS ENUM ('payroll','invoice'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
