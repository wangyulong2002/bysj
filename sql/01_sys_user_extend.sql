-- ============================================================
-- 01_sys_user_extend.sql  sys_user 扩展字段（T0-4 / 设计 5.2）
-- 依据《智慧校园信息管理系统 设计报告》5.2 / 子任务 T0-4
--
-- 说明：
--   1) 本脚本针对若依库 ry.sys_user 增加扩展字段，幂等可重复执行。
--   2) 编号字段权威来源为 campus_student.student_no / campus_teacher.teacher_no，
--      sys_user 中为展示冗余，档案变更时同步写入（见设计 5.2）。
--   3) wechat_openid 唯一约束（设计 3.4 / T1-4 使用）。
--   4) password_version：改密后自增使旧 JWT 失效（设计 3.4 / 4.5）。
--
-- 兼容性：MySQL 8.0 不支持 ADD COLUMN IF NOT EXISTS（MariaDB 语法），
--          故使用 INFORMATION_SCHEMA 判断 + PREPARE 动态 SQL 实现幂等。
-- ============================================================

USE ry;

-- 工具：判断列是否存在
SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user'
      AND COLUMN_NAME = 'student_no'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE `sys_user` ADD COLUMN `student_no` varchar(20) DEFAULT NULL COMMENT ''学号（展示冗余，权威在 campus_student）'' AFTER `nick_name`',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user'
      AND COLUMN_NAME = 'teacher_no'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE `sys_user` ADD COLUMN `teacher_no` varchar(20) DEFAULT NULL COMMENT ''工号（展示冗余，权威在 campus_teacher）'' AFTER `student_no`',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user'
      AND COLUMN_NAME = 'wechat_openid'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE `sys_user` ADD COLUMN `wechat_openid` varchar(64) DEFAULT NULL COMMENT ''微信 openid（唯一）'' AFTER `teacher_no`',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user'
      AND COLUMN_NAME = 'role_code'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE `sys_user` ADD COLUMN `role_code` varchar(20) DEFAULT NULL COMMENT ''角色标识（student/teacher/counselor/admin）'' AFTER `wechat_openid`',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @col_exists := (
    SELECT COUNT(*) FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user'
      AND COLUMN_NAME = 'password_version'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE `sys_user` ADD COLUMN `password_version` int NOT NULL DEFAULT 0 COMMENT ''密码版本号（改密自增使旧 token 失效）'' AFTER `role_code`',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- wechat_openid 唯一约束（仅当尚不存在时创建）
SET @has_unique := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user' AND INDEX_NAME = 'uk_sys_user_openid'
);
SET @sql := IF(@has_unique = 0,
    'ALTER TABLE `sys_user` ADD UNIQUE KEY `uk_sys_user_openid` (`wechat_openid`)',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 常规索引（幂等）
SET @idx_exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user' AND INDEX_NAME = 'idx_sys_user_role_code'
);
SET @sql := IF(@idx_exists = 0,
    'ALTER TABLE `sys_user` ADD INDEX `idx_sys_user_role_code` (`role_code`)',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user' AND INDEX_NAME = 'idx_sys_user_student_no'
);
SET @sql := IF(@idx_exists = 0,
    'ALTER TABLE `sys_user` ADD INDEX `idx_sys_user_student_no` (`student_no`)',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @idx_exists := (
    SELECT COUNT(*) FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = 'ry' AND TABLE_NAME = 'sys_user' AND INDEX_NAME = 'idx_sys_user_teacher_no'
);
SET @sql := IF(@idx_exists = 0,
    'ALTER TABLE `sys_user` ADD INDEX `idx_sys_user_teacher_no` (`teacher_no`)',
    'DO 0');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ============================================================
-- 执行完成。可用以下语句核对：
--   SHOW COLUMNS FROM ry.sys_user LIKE '%_no%'; 等
-- ============================================================
