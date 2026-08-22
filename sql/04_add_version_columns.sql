-- ============================================================
-- 04_add_version_columns.sql  乐观锁 version 列迁移（T0-6）
-- 依据设计 v2.2 3.6/A-02：成绩批量录入、请假状态更新使用 version 乐观锁。
-- 为已存在的 campus_score / campus_leave 补 version 列，幂等可重复执行。
-- 注：02_business_tables.sql 已包含 version 列；本脚本仅用于对已存在库的增量迁移。
-- ============================================================

USE campus;

-- campus_score.version
SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'campus' AND TABLE_NAME = 'campus_score' AND COLUMN_NAME = 'version'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE `campus_score` ADD COLUMN `version` int NOT NULL DEFAULT 0 COMMENT ''乐观锁版本号'' AFTER `is_published`',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- campus_leave.version
SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'campus' AND TABLE_NAME = 'campus_leave' AND COLUMN_NAME = 'version'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE `campus_leave` ADD COLUMN `version` int NOT NULL DEFAULT 0 COMMENT ''乐观锁版本号'' AFTER `status`',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 说明：02_business_tables.sql 已包含 version 列；本脚本仅用于对已存在库的增量迁移。
