-- ============================================================
-- 03_dict_data.sql  字典表自建 + 字典数据初始化（T0-4 / 设计 5.2、2.2、4.6）
-- 依据设计报告 v2.2：请假类型、公告类型、成绩等级、周次等字典（4.6）
--
-- 说明：
--   1) v2.0 起不再依赖若依 ry 库，sys_dict_type / sys_dict_data 在本库精简自建。
--   2) 字典类型/标签/值/排序为实施侧约定，设计报告未硬编码具体值，
--      此处给出自洽、符合系统约定的默认字典，后续可按需调整。
--   3) 幂等：先 DROP 建表，再 DELETE+INSERT 指定 dict_type，可重复执行。
--   4) DDL 权威（P0-1）：正式环境以 Django migrations 为准，本脚本仅初始化/演示用。
-- ============================================================

USE campus;

SET FOREIGN_KEY_CHECKS = 0;
SET NAMES utf8mb4;

-- ============================================================
-- 字典类型表（精简自建，对应设计 5.2）
-- ============================================================
DROP TABLE IF EXISTS `sys_dict_type`;
CREATE TABLE `sys_dict_type` (
    `id`          bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `dict_name`   varchar(100) NOT NULL COMMENT '字典名称',
    `dict_type`   varchar(100) NOT NULL COMMENT '字典类型（唯一）',
    `status`      char(1)      NOT NULL DEFAULT '0' COMMENT '状态：0正常 1停用',
    `remark`      varchar(500) DEFAULT NULL COMMENT '备注',
    `create_by`   bigint       DEFAULT NULL COMMENT '创建人',
    `create_time` datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`   bigint       DEFAULT NULL COMMENT '更新人',
    `update_time` datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`    char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dict_type` (`dict_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='字典类型表';

-- ============================================================
-- 字典数据表（精简自建，对应设计 5.2）
-- ============================================================
DROP TABLE IF EXISTS `sys_dict_data`;
CREATE TABLE `sys_dict_data` (
    `id`          bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `dict_sort`   int          NOT NULL DEFAULT 0 COMMENT '排序',
    `dict_label`  varchar(100) NOT NULL COMMENT '标签',
    `dict_value`  varchar(100) NOT NULL COMMENT '值',
    `dict_type`   varchar(100) NOT NULL COMMENT '类型（关联 sys_dict_type）',
    `css_class`   varchar(100) DEFAULT NULL COMMENT '样式 class',
    `list_class`  varchar(100) DEFAULT NULL COMMENT '列表样式',
    `is_default`  char(1)      NOT NULL DEFAULT 'N' COMMENT '是否默认：Y/N',
    `status`      char(1)      NOT NULL DEFAULT '0' COMMENT '状态：0正常 1停用',
    `remark`      varchar(500) DEFAULT NULL COMMENT '备注',
    `create_by`   bigint       DEFAULT NULL COMMENT '创建人',
    `create_time` datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`   bigint       DEFAULT NULL COMMENT '更新人',
    `update_time` datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`    char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_dict_data_type` (`dict_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='字典数据表';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 字典数据（幂等：DELETE + INSERT 指定 dict_type）
-- ============================================================
DELETE FROM sys_dict_data
    WHERE dict_type IN ('campus_leave_type', 'campus_ann_type',
                        'campus_score_level', 'campus_weekday',
                        'campus_leave_status', 'campus_score_ratio',
                        'campus_ann_status', 'campus_score_status');
DELETE FROM sys_dict_type
    WHERE dict_type IN ('campus_leave_type', 'campus_ann_type',
                        'campus_score_level', 'campus_weekday',
                        'campus_leave_status', 'campus_score_ratio',
                        'campus_ann_status', 'campus_score_status');

-- ============================================================
-- 字典类型
-- ============================================================
INSERT INTO sys_dict_type (dict_name, dict_type, status, create_by, create_time, remark) VALUES
('请假类型', 'campus_leave_type', '0', 1, NOW(), '请假申请的类型：事假/病假/其他'),
('公告类型', 'campus_ann_type', '0', 1, NOW(), '公告类型：校园/院系/班级'),
('成绩等级', 'campus_score_level', '0', 1, NOW(), '成绩等级：优秀/良好/中等/及格/不及格'),
('周次', 'campus_weekday', '0', 1, NOW(), '星期映射（1~7）'),
('请假状态', 'campus_leave_status', '0', 1, NOW(), '请假流程状态'),
('成绩占比', 'campus_score_ratio', '0', 1, NOW(), '平时/考试占比（总评计算，发布时固化快照）'),
('公告状态', 'campus_ann_status', '0', 1, NOW(), '公告草稿/发布/下架'),
('成绩发布状态', 'campus_score_status', '0', 1, NOW(), '成绩是否发布');

-- ============================================================
-- 请假类型（4.4：1事假 2病假 3其他）
-- ============================================================
INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) VALUES
(1, '事假', '1', 'campus_leave_type', '', 'default', 'N', '0', 1, NOW(), ''),
(2, '病假', '2', 'campus_leave_type', '', 'default', 'N', '0', 1, NOW(), ''),
(3, '其他', '3', 'campus_leave_type', '', 'default', 'N', '0', 1, NOW(), '');

-- ============================================================
-- 请假状态（5.3.12：0待审批 1通过 2驳回 3撤销）
-- ============================================================
INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) VALUES
(1, '待审批', '0', 'campus_leave_status', '', 'warning', 'Y', '0', 1, NOW(), ''),
(2, '通过', '1', 'campus_leave_status', '', 'success', 'N', '0', 1, NOW(), ''),
(3, '驳回', '2', 'campus_leave_status', '', 'danger', 'N', '0', 1, NOW(), ''),
(4, '撤销', '3', 'campus_leave_status', '', 'info', 'N', '0', 1, NOW(), '');

-- ============================================================
-- 公告类型（5.3.9：1校园 2院系 3班级）
-- ============================================================
INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) VALUES
(1, '校园', '1', 'campus_ann_type', '', 'primary', 'Y', '0', 1, NOW(), ''),
(2, '院系', '2', 'campus_ann_type', '', 'success', 'N', '0', 1, NOW(), ''),
(3, '班级', '3', 'campus_ann_type', '', 'warning', 'N', '0', 1, NOW(), '');

-- ============================================================
-- 公告状态（5.3.9：0草稿 1发布 2下架）
-- ============================================================
INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) VALUES
(1, '草稿', '0', 'campus_ann_status', '', 'info', 'Y', '0', 1, NOW(), ''),
(2, '发布', '1', 'campus_ann_status', '', 'success', 'N', '0', 1, NOW(), ''),
(3, '下架', '2', 'campus_ann_status', '', 'danger', 'N', '0', 1, NOW(), '');

-- ============================================================
-- 成绩发布状态（5.3.10：0未发布 1已发布）
-- ============================================================
INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) VALUES
(1, '未发布', '0', 'campus_score_status', '', 'warning', 'Y', '0', 1, NOW(), ''),
(2, '已发布', '1', 'campus_score_status', '', 'success', 'N', '0', 1, NOW(), '');

-- ============================================================
-- 成绩等级（4.3：按总评分数）
-- ============================================================
INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) VALUES
(1, '优秀', 'A', 'campus_score_level', '', 'success', 'N', '0', 1, NOW(), '90~100'),
(2, '良好', 'B', 'campus_score_level', '', 'primary', 'N', '0', 1, NOW(), '80~89'),
(3, '中等', 'C', 'campus_score_level', '', 'warning', 'N', '0', 1, NOW(), '70~79'),
(4, '及格', 'D', 'campus_score_level', '', 'default', 'N', '0', 1, NOW(), '60~69'),
(5, '不及格', 'E', 'campus_score_level', '', 'danger', 'N', '0', 1, NOW(), '<60');

-- ============================================================
-- 周次（4.1 教学周历：1~20 周）
-- ============================================================
INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark)
SELECT s.n, CONCAT('第', s.n, '周'), CAST(s.n AS CHAR), 'campus_weekday', '', 'default', IF(s.n=1,'Y','N'), '0', 1, NOW(), ''
FROM (SELECT 1 n UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9 UNION SELECT 10
      UNION SELECT 11 UNION SELECT 12 UNION SELECT 13 UNION SELECT 14 UNION SELECT 15 UNION SELECT 16 UNION SELECT 17 UNION SELECT 18 UNION SELECT 19 UNION SELECT 20) s;

-- ============================================================
-- 成绩占比（4.3/T4-4：平时/考试占比，发布时固化快照）
-- value 约定：a:b 表示 平时:考试
-- ============================================================
INSERT INTO sys_dict_data (dict_sort, dict_label, dict_value, dict_type, css_class, list_class, is_default, status, create_by, create_time, remark) VALUES
(1, '平时40%：考试60%', '40:60', 'campus_score_ratio', '', 'default', 'Y', '0', 1, NOW(), '默认比例'),
(2, '平时30%：考试70%', '30:70', 'campus_score_ratio', '', 'default', 'N', '0', 1, NOW(), ''),
(3, '平时50%：考试50%', '50:50', 'campus_score_ratio', '', 'default', 'N', '0', 1, NOW(), ''),
(4, '平时20%：考试80%', '20:80', 'campus_score_ratio', '', 'default', 'N', '0', 1, NOW(), '');

-- ============================================================
-- 字典初始化完成。
-- ============================================================
