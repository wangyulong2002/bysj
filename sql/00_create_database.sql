-- ============================================================
-- 00_create_database.sql  创建业务数据库（T0-4）
-- 幂等：IF NOT EXISTS，可重复执行。
-- 依据设计报告 9.1/5.1：utf8mb4 / utf8mb4_unicode_ci
-- ============================================================

CREATE DATABASE IF NOT EXISTS `campus`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE campus;
