-- =====================================================================
-- SplitSmart Database Schema (MySQL 8.0+)
-- Phase 1: Core Foundation & Normalized Schema
-- All monetary math uses DECIMAL(10, 2) for zero binary floating-point drift.
-- =====================================================================

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS settlements;
DROP TABLE IF EXISTS receipt_item_assignments;
DROP TABLE IF EXISTS receipt_items;
DROP TABLE IF EXISTS expense_splits;
DROP TABLE IF EXISTS expense_payers;
DROP TABLE IF EXISTS expenses;
DROP TABLE IF EXISTS fund_contributions;
DROP TABLE IF EXISTS group_members;
DROP TABLE IF EXISTS family_units;
DROP TABLE IF EXISTS `groups`;
DROP TABLE IF EXISTS users;

SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 1. USERS
-- Registered application accounts.
-- ---------------------------------------------------------------------
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NULL,
    phone VARCHAR(20) UNIQUE NULL,
    password_hash VARCHAR(255) NULL,
    avatar_url VARCHAR(500) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_email (email),
    INDEX idx_users_phone (phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2. GROUPS
-- Supports 4 operating modes and 2 funding modes:
-- Modes: 'quick_split', 'regular', 'friends_trip', 'family_trip'
-- Funding Modes: 'individual' (pay-as-you-go), 'pooled_kitty' (common trip fund)
-- Note: `groups` is backticked because GROUPS is a reserved keyword in MySQL 8.0+.
-- ---------------------------------------------------------------------
CREATE TABLE `groups` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    description TEXT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'Other',
    mode ENUM('quick_split', 'regular', 'friends_trip', 'family_trip') NOT NULL DEFAULT 'regular',
    funding_mode ENUM('individual', 'pooled_kitty') NOT NULL DEFAULT 'individual',
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    invite_code VARCHAR(64) UNIQUE NOT NULL,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_groups_created_by FOREIGN KEY (created_by) 
        REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_groups_mode (mode),
    INDEX idx_groups_invite (invite_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 3. FAMILY UNITS
-- Used in 'family_trip' mode to group relatives or family households.
-- ---------------------------------------------------------------------
CREATE TABLE family_units (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_family_units_group FOREIGN KEY (group_id) 
        REFERENCES `groups`(id) ON DELETE CASCADE,
    INDEX idx_family_group (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 4. GROUP MEMBERS
-- Supports hybrid onboarding:
-- - user_id is NULL for direct guest placeholders.
-- - guest_email / guest_phone allows auto-linking when an invite is claimed or guest registers.
-- - sponsor_id is a self-referencing foreign key for child-to-parent debt rollups (Family Trip mode).
-- ---------------------------------------------------------------------
CREATE TABLE group_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    user_id INT NULL,
    display_name VARCHAR(100) NOT NULL,
    guest_email VARCHAR(255) NULL,
    guest_phone VARCHAR(20) NULL,
    sponsor_id INT NULL,
    family_unit_id INT NULL,
    role ENUM('admin', 'member') NOT NULL DEFAULT 'member',
    status ENUM('active', 'invited', 'guest') NOT NULL DEFAULT 'active',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_gm_group FOREIGN KEY (group_id) 
        REFERENCES `groups`(id) ON DELETE CASCADE,
    CONSTRAINT fk_gm_user FOREIGN KEY (user_id) 
        REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_gm_sponsor FOREIGN KEY (sponsor_id) 
        REFERENCES group_members(id) ON DELETE SET NULL,
    CONSTRAINT fk_gm_family FOREIGN KEY (family_unit_id) 
        REFERENCES family_units(id) ON DELETE SET NULL,
    UNIQUE KEY uq_group_user (group_id, user_id),
    INDEX idx_gm_group (group_id),
    INDEX idx_gm_user (user_id),
    INDEX idx_gm_sponsor (sponsor_id),
    INDEX idx_gm_guest_contact (guest_email, guest_phone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 5. FUND CONTRIBUTIONS
-- Used when a group operates in 'pooled_kitty' (Common Trip Fund) mode.
-- Tracks cash/UPI deposits by members into the collective kitty.
-- ---------------------------------------------------------------------
CREATE TABLE fund_contributions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    member_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) DEFAULT 'Cash',
    notes VARCHAR(255) NULL,
    contributed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fc_group FOREIGN KEY (group_id) 
        REFERENCES `groups`(id) ON DELETE CASCADE,
    CONSTRAINT fk_fc_member FOREIGN KEY (member_id) 
        REFERENCES group_members(id) ON DELETE CASCADE,
    INDEX idx_fc_group_member (group_id, member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 6. EXPENSES
-- Master record for every expense incurred.
-- Supports:
-- - Multiple split types ('equal', 'exact', 'percentage', 'shares', 'itemized')
-- - Funding source ('individual' vs 'kitty')
-- - Gemini AI extraction payload storage (ai_parsed_raw)
-- ---------------------------------------------------------------------
CREATE TABLE expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'General',
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    expense_date DATE NOT NULL,
    split_type ENUM('equal', 'exact', 'percentage', 'shares', 'itemized') NOT NULL DEFAULT 'equal',
    funding_source ENUM('individual', 'kitty') NOT NULL DEFAULT 'individual',
    receipt_image_path VARCHAR(500) NULL,
    ai_parsed_raw JSON NULL,
    created_by_member_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_exp_group FOREIGN KEY (group_id) 
        REFERENCES `groups`(id) ON DELETE CASCADE,
    CONSTRAINT fk_exp_creator FOREIGN KEY (created_by_member_id) 
        REFERENCES group_members(id) ON DELETE CASCADE,
    INDEX idx_exp_group_date (group_id, expense_date),
    INDEX idx_exp_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 7. EXPENSE PAYERS
-- Normalized payer ledger enabling single or multi-payer expenses.
-- (e.g. Alice paid 60.00 and Bob paid 40.00 on a 100.00 expense).
-- ---------------------------------------------------------------------
CREATE TABLE expense_payers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expense_id INT NOT NULL,
    member_id INT NOT NULL,
    amount_paid DECIMAL(10, 2) NOT NULL,
    CONSTRAINT fk_ep_expense FOREIGN KEY (expense_id) 
        REFERENCES expenses(id) ON DELETE CASCADE,
    CONSTRAINT fk_ep_member FOREIGN KEY (member_id) 
        REFERENCES group_members(id) ON DELETE CASCADE,
    UNIQUE KEY uq_expense_payer (expense_id, member_id),
    INDEX idx_ep_member (member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 8. EXPENSE SPLITS
-- Normalized debtor ledger defining exactly who owes what.
-- Decimal precision ensures mathematically exact totals.
-- ---------------------------------------------------------------------
CREATE TABLE expense_splits (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expense_id INT NOT NULL,
    member_id INT NOT NULL,
    owed_amount DECIMAL(10, 2) NOT NULL,
    share_value DECIMAL(10, 4) NULL,
    is_settled TINYINT(1) NOT NULL DEFAULT 0,
    CONSTRAINT fk_es_expense FOREIGN KEY (expense_id) 
        REFERENCES expenses(id) ON DELETE CASCADE,
    CONSTRAINT fk_es_member FOREIGN KEY (member_id) 
        REFERENCES group_members(id) ON DELETE CASCADE,
    UNIQUE KEY uq_expense_split (expense_id, member_id),
    INDEX idx_es_member (member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 9. RECEIPT ITEMS
-- Stores line-item breakdowns extracted via Gemini Multimodal OCR
-- or manually itemized bills.
-- ---------------------------------------------------------------------
CREATE TABLE receipt_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    expense_id INT NOT NULL,
    item_name VARCHAR(255) NOT NULL,
    quantity DECIMAL(8, 2) NOT NULL DEFAULT 1.00,
    unit_price DECIMAL(10, 2) NOT NULL,
    total_price DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ri_expense FOREIGN KEY (expense_id) 
        REFERENCES expenses(id) ON DELETE CASCADE,
    INDEX idx_ri_expense (expense_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 10. RECEIPT ITEM ASSIGNMENTS
-- Associates specific group members to individual receipt line items.
-- Supports multi-person sharing of individual dishes or items via share_fraction.
-- ---------------------------------------------------------------------
CREATE TABLE receipt_item_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    receipt_item_id INT NOT NULL,
    member_id INT NOT NULL,
    share_fraction DECIMAL(8, 4) NOT NULL DEFAULT 1.0000,
    assigned_amount DECIMAL(10, 2) NOT NULL,
    CONSTRAINT fk_ria_receipt_item FOREIGN KEY (receipt_item_id) 
        REFERENCES receipt_items(id) ON DELETE CASCADE,
    CONSTRAINT fk_ria_member FOREIGN KEY (member_id) 
        REFERENCES group_members(id) ON DELETE CASCADE,
    UNIQUE KEY uq_item_assignment (receipt_item_id, member_id),
    INDEX idx_ria_member (member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 11. SETTLEMENTS
-- Direct peer-to-peer repayments and Kitty refunds.
-- Reduces net debt between members.
-- ---------------------------------------------------------------------
CREATE TABLE settlements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    payer_member_id INT NOT NULL,
    payee_member_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) DEFAULT 'Cash',
    payment_reference VARCHAR(100) NULL,
    notes VARCHAR(255) NULL,
    status ENUM('pending', 'completed', 'cancelled') NOT NULL DEFAULT 'completed',
    settled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_set_group FOREIGN KEY (group_id) 
        REFERENCES `groups`(id) ON DELETE CASCADE,
    CONSTRAINT fk_set_payer FOREIGN KEY (payer_member_id) 
        REFERENCES group_members(id) ON DELETE CASCADE,
    CONSTRAINT fk_set_payee FOREIGN KEY (payee_member_id) 
        REFERENCES group_members(id) ON DELETE CASCADE,
    INDEX idx_set_group (group_id),
    INDEX idx_set_payer (payer_member_id),
    INDEX idx_set_payee (payee_member_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
