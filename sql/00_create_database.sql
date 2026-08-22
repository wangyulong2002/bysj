-- ============================================================
-- 00_create_database.sql  创建业务数据库（T0-4）
-- 幂等：IF NOT EXISTS，可重复执行。
-- 依据设计报告 v2.2 9.1/5.1：utf8mb4 / collation 统一 utf8mb4_0900_ai_ci（B-10）
-- ============================================================

CREATE DATABASE IF NOT EXISTS `campus`
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE campus;
