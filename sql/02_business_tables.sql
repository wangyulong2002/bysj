-- ============================================================
-- 02_business_tables.sql  业务表建表 DDL（T0-4 / 设计第 5 章）
-- 依据《智慧校园信息管理系统 设计报告》5.3/5.4/5.5
--
-- 通用约定（5.1）：
--   * 字符集 utf8mb4、引擎 InnoDB、主键 id BIGINT AUTO_INCREMENT
--   * 审计字段：create_by/create_time/update_by/update_time + 逻辑删除 del_flag(0正常 2删除)
--   * 外键默认 ON DELETE RESTRICT（禁物理级联删除，删除走 del_flag）
--   * campus_term.is_current 唯一：应用层事务切换 + 唯一索引辅助（5.1/P1-04）
--
-- 幂等性：各表先 DROP TABLE IF EXISTS 再重建，可直接重复执行。
-- 注意：DROP 会清空数据，仅用于初始化环境；生产环境请勿直接重跑。
-- ============================================================

USE campus;

SET FOREIGN_KEY_CHECKS = 0;
SET NAMES utf8mb4;

-- ============================================================
-- 5.3.1 院系表
-- ============================================================
DROP TABLE IF EXISTS `campus_department`;
CREATE TABLE `campus_department` (
    `id`          bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `dept_name`   varchar(50)  NOT NULL COMMENT '院系名称',
    `dept_code`   varchar(20)  NOT NULL COMMENT '院系编码（唯一）',
    `create_by`   bigint       DEFAULT NULL COMMENT '创建人',
    `create_time` datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`   bigint       DEFAULT NULL COMMENT '更新人',
    `update_time` datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`    char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除：0正常 2删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_dept_code` (`dept_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='院系表';

-- ============================================================
-- 5.3.6 学期表（先于教学班建）
-- ============================================================
DROP TABLE IF EXISTS `campus_term`;
CREATE TABLE `campus_term` (
    `id`          bigint   NOT NULL AUTO_INCREMENT COMMENT '主键',
    `term_name`   varchar(50) NOT NULL COMMENT '学期名称',
    `start_date`  date     NOT NULL COMMENT '开始日期',
    `end_date`    date     NOT NULL COMMENT '结束日期',
    `total_weeks` int      NOT NULL COMMENT '总周数',
    `is_current`  char(1)  NOT NULL DEFAULT '0' COMMENT '是否当前学期：0否 1是（任意时刻仅一个）',
    `create_by`   bigint   DEFAULT NULL COMMENT '创建人',
    `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`   bigint   DEFAULT NULL COMMENT '更新人',
    `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`    char(1)  NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    -- 函数索引/唯一约束辅助：仅一个当前学期（5.1/P1-04），is_current='1' 时唯一
    UNIQUE KEY `uk_term_current` ((IF(`is_current` = '1', `is_current`, NULL)))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学期表';

-- ============================================================
-- 5.3.2 班级表（辅导员/班主任引用 ry.sys_user）
-- ============================================================
DROP TABLE IF EXISTS `campus_class`;
CREATE TABLE `campus_class` (
    `id`               bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `class_name`       varchar(50)  NOT NULL COMMENT '班级名称（如：计科2301）',
    `class_code`       varchar(20)  NOT NULL COMMENT '班级编码（唯一）',
    `grade`            varchar(10)  NOT NULL COMMENT '年级（如：2023）',
    `major`            varchar(50)  DEFAULT NULL COMMENT '专业',
    `department_id`    bigint       DEFAULT NULL COMMENT '院系 id',
    `counselor_id`     bigint       DEFAULT NULL COMMENT '辅导员（ry.sys_user.id）',
    `head_teacher_id`  bigint       DEFAULT NULL COMMENT '班主任（ry.sys_user.id，可选）',
    `create_by`        bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`      datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`        bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`      datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`         char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_class_code` (`class_code`),
    KEY `idx_class_dept` (`department_id`),
    KEY `idx_class_counselor` (`counselor_id`),
    CONSTRAINT `fk_class_dept`    FOREIGN KEY (`department_id`) REFERENCES `campus_department`(`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_class_counselor` FOREIGN KEY (`counselor_id`) REFERENCES `ry`.`sys_user`(`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='班级表';

-- ============================================================
-- 5.3.3 课程表
-- ============================================================
DROP TABLE IF EXISTS `campus_course`;
CREATE TABLE `campus_course` (
    `id`            bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `course_name`   varchar(100) NOT NULL COMMENT '课程名称',
    `course_code`   varchar(30)  NOT NULL COMMENT '课程编码（唯一）',
    `credit`        decimal(3,1) NOT NULL DEFAULT 0.0 COMMENT '学分',
    `hours`         int          NOT NULL DEFAULT 0 COMMENT '总学时',
    `department_id` bigint       DEFAULT NULL COMMENT '开课院系',
    `create_by`     bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`   datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`     bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`   datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`      char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_course_code` (`course_code`),
    KEY `idx_course_dept` (`department_id`),
    CONSTRAINT `fk_course_dept` FOREIGN KEY (`department_id`) REFERENCES `campus_department`(`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程表';

-- ============================================================
-- 5.3.7 学生档案表（user_id → ry.sys_user，class_id → campus_class）
-- ============================================================
DROP TABLE IF EXISTS `campus_student`;
CREATE TABLE `campus_student` (
    `id`          bigint      NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`     bigint      NOT NULL COMMENT 'ry.sys_user.id（唯一）',
    `student_no`  varchar(20) NOT NULL COMMENT '学号（唯一）',
    `class_id`    bigint      DEFAULT NULL COMMENT '班级 id',
    `enroll_year` varchar(10) DEFAULT NULL COMMENT '入学年份',
    `create_by`   bigint      DEFAULT NULL COMMENT '创建人',
    `create_time` datetime    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`   bigint      DEFAULT NULL COMMENT '更新人',
    `update_time` datetime    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`    char(1)     NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_student_user` (`user_id`),
    UNIQUE KEY `uk_student_no` (`student_no`),
    KEY `idx_student_class` (`class_id`),
    CONSTRAINT `fk_student_class` FOREIGN KEY (`class_id`) REFERENCES `campus_class`(`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_student_user`  FOREIGN KEY (`user_id`)  REFERENCES `ry`.`sys_user`(`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生档案表';

-- ============================================================
-- 5.3.8 教师档案表（user_id → ry.sys_user）
-- ============================================================
DROP TABLE IF EXISTS `campus_teacher`;
CREATE TABLE `campus_teacher` (
    `id`            bigint      NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`       bigint      NOT NULL COMMENT 'ry.sys_user.id（唯一）',
    `teacher_no`    varchar(20) NOT NULL COMMENT '工号（唯一）',
    `title`         varchar(20) DEFAULT NULL COMMENT '职称',
    `department_id` bigint      DEFAULT NULL COMMENT '所属院系',
    `create_by`     bigint      DEFAULT NULL COMMENT '创建人',
    `create_time`   datetime    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`     bigint      DEFAULT NULL COMMENT '更新人',
    `update_time`   datetime    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`      char(1)     NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_teacher_user` (`user_id`),
    UNIQUE KEY `uk_teacher_no` (`teacher_no`),
    KEY `idx_teacher_dept` (`department_id`),
    CONSTRAINT `fk_teacher_dept` FOREIGN KEY (`department_id`) REFERENCES `campus_department`(`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_teacher_user`  FOREIGN KEY (`user_id`)  REFERENCES `ry`.`sys_user`(`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='教师档案表';

-- ============================================================
-- 5.3.4 教学班表（核心，P0-04）
-- 唯一约束 (term_id, class_id, course_id) 同学期同班级同课程仅一个教学班
-- ============================================================
DROP TABLE IF EXISTS `campus_course_offering`;
CREATE TABLE `campus_course_offering` (
    `id`          bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
    `course_id`   bigint NOT NULL COMMENT '课程 id',
    `term_id`     bigint NOT NULL COMMENT '学期 id',
    `class_id`    bigint NOT NULL COMMENT '班级 id',
    `teacher_id`  bigint NOT NULL COMMENT '任课教师（ry.sys_user.id）',
    `create_by`   bigint DEFAULT NULL COMMENT '创建人',
    `create_time` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`   bigint DEFAULT NULL COMMENT '更新人',
    `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`    char(1) NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_offering_term_class_course` (`term_id`, `class_id`, `course_id`),
    KEY `idx_offering_teacher` (`teacher_id`),
    KEY `idx_offering_course` (`course_id`),
    KEY `idx_offering_class` (`class_id`),
    KEY `idx_offering_term` (`term_id`),
    CONSTRAINT `fk_offering_course` FOREIGN KEY (`course_id`)  REFERENCES `campus_course`(`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_offering_term`   FOREIGN KEY (`term_id`)    REFERENCES `campus_term`(`id`)   ON DELETE RESTRICT,
    CONSTRAINT `fk_offering_class`  FOREIGN KEY (`class_id`)   REFERENCES `campus_class`(`id`)  ON DELETE RESTRICT,
    CONSTRAINT `fk_offering_teacher` FOREIGN KEY (`teacher_id`) REFERENCES `ry`.`sys_user`(`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='教学班表';

-- ============================================================
-- 5.3.5 排课表（基于教学班）
-- 关键查询：WHERE offering_id=? AND week_start<=? AND week_end>=?
-- ============================================================
DROP TABLE IF EXISTS `campus_course_schedule`;
CREATE TABLE `campus_course_schedule` (
    `id`           bigint      NOT NULL AUTO_INCREMENT COMMENT '主键',
    `offering_id`  bigint      NOT NULL COMMENT '教学班 id',
    `week_start`   int         NOT NULL COMMENT '起始周',
    `week_end`     int         NOT NULL COMMENT '结束周',
    `day_of_week`  tinyint     NOT NULL COMMENT '星期（1~7）',
    `period_start` tinyint     NOT NULL COMMENT '开始节次',
    `period_end`   tinyint     NOT NULL COMMENT '结束节次',
    `location`     varchar(50) DEFAULT NULL COMMENT '上课地点（v1 仅展示）',
    `create_by`    bigint      DEFAULT NULL COMMENT '创建人',
    `create_time`  datetime    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`    bigint      DEFAULT NULL COMMENT '更新人',
    `update_time`  datetime    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`     char(1)     NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_schedule_offering_week` (`offering_id`, `week_start`, `week_end`),
    CONSTRAINT `fk_schedule_offering` FOREIGN KEY (`offering_id`) REFERENCES `campus_course_offering`(`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='排课表';

-- ============================================================
-- 5.3.10 成绩表
-- 唯一约束 (student_id, offering_id) 一个学生一个教学班一条成绩
-- ============================================================
DROP TABLE IF EXISTS `campus_score`;
CREATE TABLE `campus_score` (
    `id`            bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `student_id`    bigint       NOT NULL COMMENT '学生档案 id',
    `offering_id`   bigint       NOT NULL COMMENT '教学班 id',
    `usual_score`   decimal(5,2) DEFAULT NULL COMMENT '平时成绩',
    `exam_score`    decimal(5,2) DEFAULT NULL COMMENT '考试成绩',
    `total_score`   decimal(5,2) DEFAULT NULL COMMENT '总评成绩（自动计算）',
    `usual_ratio`   tinyint      DEFAULT NULL COMMENT '平时占比快照（发布时固化）',
    `exam_ratio`    tinyint      DEFAULT NULL COMMENT '考试占比快照',
    `is_published`  char(1)      NOT NULL DEFAULT '0' COMMENT '0未发布 1已发布',
    `version`       int          NOT NULL DEFAULT 0 COMMENT '乐观锁版本号（3.6/P1-09）',
    `create_by`     bigint       DEFAULT NULL COMMENT '录入人',
    `update_by`     bigint       DEFAULT NULL COMMENT '最近修改人',
    `create_time`   datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time`   datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最近修改时间',
    `publish_by`    bigint       DEFAULT NULL COMMENT '发布人',
    `publish_time`  datetime     DEFAULT NULL COMMENT '发布时间',
    `del_flag`      char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_score_student_offering` (`student_id`, `offering_id`),
    KEY `idx_score_student` (`student_id`),
    KEY `idx_score_offering` (`offering_id`),
    CONSTRAINT `fk_score_student`  FOREIGN KEY (`student_id`)  REFERENCES `campus_student`(`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_score_offering` FOREIGN KEY (`offering_id`) REFERENCES `campus_course_offering`(`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成绩表';

-- ============================================================
-- 5.3.11 成绩审计表（P1-05）
-- ============================================================
DROP TABLE IF EXISTS `campus_score_audit`;
CREATE TABLE `campus_score_audit` (
    `id`              bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `student_id`      bigint       NOT NULL COMMENT '学生档案 id',
    `offering_id`     bigint       NOT NULL COMMENT '教学班 id',
    `old_score`       decimal(5,2) DEFAULT NULL COMMENT '修改前总评',
    `new_score`       decimal(5,2) DEFAULT NULL COMMENT '修改后总评',
    `operator_id`     bigint       DEFAULT NULL COMMENT '操作人',
    `operation`       char(1)      NOT NULL COMMENT '1录入 2修改 3发布 4撤销发布',
    `operation_time`  datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    `create_by`       bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`     datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`       bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`     datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`        char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_score_audit_student` (`student_id`),
    KEY `idx_score_audit_offering` (`offering_id`),
    CONSTRAINT `fk_score_audit_student`  FOREIGN KEY (`student_id`)  REFERENCES `campus_student`(`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_score_audit_offering` FOREIGN KEY (`offering_id`) REFERENCES `campus_course_offering`(`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='成绩审计表';

-- ============================================================
-- 5.3.9 公告表（发布人 → ry.sys_user）
-- ============================================================
DROP TABLE IF EXISTS `campus_announcement`;
CREATE TABLE `campus_announcement` (
    `id`                   bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `title`                varchar(100) NOT NULL COMMENT '标题',
    `content`              longtext     COMMENT '内容',
    `ann_type`             char(1)      NOT NULL COMMENT '1校园 2院系 3班级',
    `target_class_id`      bigint       DEFAULT NULL COMMENT '班级公告目标班级（ann_type=3 时填，可空；v1 单目标）',
    `target_department_id` bigint       DEFAULT NULL COMMENT '院系公告目标院系（ann_type=2 时填，可空）',
    `publisher_id`         bigint       DEFAULT NULL COMMENT '发布人（ry.sys_user.id，仅管理员）',
    `is_top`               char(1)      NOT NULL DEFAULT '0' COMMENT '是否置顶',
    `status`               char(1)      NOT NULL DEFAULT '0' COMMENT '0草稿 1发布 2下架',
    `publish_time`         datetime     DEFAULT NULL COMMENT '发布时间',
    `create_by`            bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`          datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`            bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`          datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`             char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_announcement_status_publish` (`status`, `publish_time`),
    KEY `idx_announcement_type` (`ann_type`, `target_class_id`),
    KEY `idx_announcement_dept` (`target_department_id`),
    CONSTRAINT `fk_announcement_publisher` FOREIGN KEY (`publisher_id`) REFERENCES `ry`.`sys_user`(`user_id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_announcement_class`     FOREIGN KEY (`target_class_id`)     REFERENCES `campus_class`(`id`)  ON DELETE RESTRICT,
    CONSTRAINT `fk_announcement_dept`      FOREIGN KEY (`target_department_id`) REFERENCES `campus_department`(`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公告表';

-- ============================================================
-- 5.3.14 文件表（P1-06，先于请假建，因请假引用附件）
-- ============================================================
DROP TABLE IF EXISTS `campus_file`;
CREATE TABLE `campus_file` (
    `id`            bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `original_name` varchar(255) NOT NULL COMMENT '原始文件名',
    `stored_name`   varchar(64)  NOT NULL COMMENT '服务端存储名（随机 UUID）',
    `mime_type`     varchar(100) NOT NULL COMMENT 'MIME 类型',
    `file_size`     bigint       NOT NULL DEFAULT 0 COMMENT '大小（字节）',
    `storage_path`  varchar(255) NOT NULL COMMENT '存储相对路径',
    `file_hash`     varchar(64)  DEFAULT NULL COMMENT '文件哈希（去重/校验）',
    `uploader_id`   bigint       DEFAULT NULL COMMENT '上传人（ry.sys_user.id）',
    `create_by`     bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`   datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`     bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`   datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`      char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_file_uploader` (`uploader_id`),
    CONSTRAINT `fk_file_uploader` FOREIGN KEY (`uploader_id`) REFERENCES `ry`.`sys_user`(`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文件表';

-- ============================================================
-- 5.3.12 请假表（引用 campus_file 附件）
-- ============================================================
DROP TABLE IF EXISTS `campus_leave`;
CREATE TABLE `campus_leave` (
    `id`              bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `student_id`      bigint       NOT NULL COMMENT '学生档案 id',
    `leave_type`      char(1)      NOT NULL COMMENT '1事假 2病假 3其他',
    `reason`          varchar(500) DEFAULT NULL COMMENT '请假事由',
    `start_time`      datetime     NOT NULL COMMENT '开始时间',
    `end_time`        datetime     NOT NULL COMMENT '结束时间',
    `total_days`      decimal(4,1) NOT NULL DEFAULT 0.0 COMMENT '时长（天）',
    `status`          char(1)      NOT NULL DEFAULT '0' COMMENT '0待审批 1通过 2驳回 3撤销',
    `version`         int          NOT NULL DEFAULT 0 COMMENT '乐观锁版本号（3.6/P1-09）',
    `approver_id`     bigint       DEFAULT NULL COMMENT '审批人（辅导员 ry.sys_user.id）',
    `approve_time`    datetime     DEFAULT NULL COMMENT '审批时间',
    `approve_comment` varchar(500) DEFAULT NULL COMMENT '审批意见',
    `attachment_id`   bigint       DEFAULT NULL COMMENT '附件文件 id（campus_file，可空）',
    `create_by`       bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`     datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间/创建时间',
    `update_by`       bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`     datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`        char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_leave_student_status` (`student_id`, `status`),
    KEY `idx_leave_approver_status` (`approver_id`, `status`),
    CONSTRAINT `fk_leave_student` FOREIGN KEY (`student_id`) REFERENCES `campus_student`(`id`) ON DELETE RESTRICT,
    CONSTRAINT `fk_leave_attachment` FOREIGN KEY (`attachment_id`) REFERENCES `campus_file`(`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='请假表';

-- ============================================================
-- 5.3.13 站内消息表（P0-07）
-- ============================================================
DROP TABLE IF EXISTS `campus_message`;
CREATE TABLE `campus_message` (
    `id`            bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `user_id`       bigint       NOT NULL COMMENT '接收用户（ry.sys_user.id）',
    `msg_type`      char(1)      NOT NULL COMMENT '1请假审批 2系统 3公告',
    `title`         varchar(100) DEFAULT NULL COMMENT '标题',
    `content`       varchar(500) DEFAULT NULL COMMENT '内容',
    `business_type` varchar(30)  DEFAULT NULL COMMENT '业务类型（leave/announcement/...）',
    `business_id`   bigint       DEFAULT NULL COMMENT '业务记录 id',
    `is_read`       char(1)      NOT NULL DEFAULT '0' COMMENT '0未读 1已读',
    `read_time`     datetime     DEFAULT NULL COMMENT '阅读时间',
    `create_by`     bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`   datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`     bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`   datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`      char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_message_user_read` (`user_id`, `is_read`),
    CONSTRAINT `fk_message_user` FOREIGN KEY (`user_id`) REFERENCES `ry`.`sys_user`(`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='站内消息表';

-- ============================================================
-- 5.3.15 知识库文档表
-- ============================================================
DROP TABLE IF EXISTS `campus_knowledge`;
CREATE TABLE `campus_knowledge` (
    `id`           bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `title`        varchar(100) NOT NULL COMMENT '标题',
    `category`     char(1)      NOT NULL COMMENT '分类（1师资 2宿舍 3食堂 4制度 5招生 6设施 7其他）',
    `content`      longtext     COMMENT '正文（富文本）',
    `tags`         varchar(200) DEFAULT NULL COMMENT '标签（逗号分隔）',
    `content_hash` varchar(64)  DEFAULT NULL COMMENT '内容哈希（变更检测，避免无变化重复向量化）',
    `status`       char(1)      NOT NULL DEFAULT '0' COMMENT '0草稿 1发布（发布即触发向量化）',
    `publisher_id` bigint       DEFAULT NULL COMMENT '发布人（ry.sys_user.id）',
    `create_by`    bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`  datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`    bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`  datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`     char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_knowledge_category_status` (`category`, `status`),
    CONSTRAINT `fk_knowledge_publisher` FOREIGN KEY (`publisher_id`) REFERENCES `ry`.`sys_user`(`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='知识库文档表';

-- ============================================================
-- 5.3.16 向量化分片表（id 对应 Redis key rag:chunk:{id}）
-- ============================================================
DROP TABLE IF EXISTS `campus_rag_chunk`;
CREATE TABLE `campus_rag_chunk` (
    `id`            bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `source_type`   char(1)      NOT NULL COMMENT '1公告 2知识库',
    `source_id`     bigint       NOT NULL COMMENT '原文档 id',
    `source_version` int         NOT NULL DEFAULT 1 COMMENT '文档版本号（编辑后递增，整源重建判定）',
    `chunk_index`   int          NOT NULL DEFAULT 0 COMMENT '分片序号',
    `content`       text         COMMENT '分片文本（冗余存储）',
    `title`         varchar(100) DEFAULT NULL COMMENT '来源标题',
    `url`           varchar(255) DEFAULT NULL COMMENT '来源链接',
    `status`        char(1)      NOT NULL DEFAULT '0' COMMENT '0待向量化 1已向量化 2失败',
    `create_by`     bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`   datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`     bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`   datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`      char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_rag_chunk_source` (`source_type`, `source_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='向量化分片表';

-- ============================================================
-- 5.3.17 问答日志表
-- ============================================================
DROP TABLE IF EXISTS `campus_rag_log`;
CREATE TABLE `campus_rag_log` (
    `id`                bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `session_id`        varchar(64)  DEFAULT NULL COMMENT '会话 id（前端 uuid）',
    `question`          varchar(500) NOT NULL COMMENT '用户问题',
    `answer`            longtext     COMMENT '回答',
    `ref_ids`           varchar(500) DEFAULT NULL COMMENT '引用来源 id 列表',
    `hit_count`         int          NOT NULL DEFAULT 0 COMMENT '命中检索片段数',
    `model`             varchar(30)  DEFAULT NULL COMMENT '生成模型',
    `prompt_tokens`     int          NOT NULL DEFAULT 0 COMMENT '输入 token',
    `completion_tokens` int          NOT NULL DEFAULT 0 COMMENT '输出 token',
    `cost_time_ms`      int          NOT NULL DEFAULT 0 COMMENT '总耗时',
    `ip`                varchar(50)  DEFAULT NULL COMMENT '提问者 IP（仅限流/审计）',
    `feedback`          char(1)      NOT NULL DEFAULT '0' COMMENT '0未评 1赞 2踩',
    `create_by`         bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`       datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '时间',
    `update_by`         bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`       datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`          char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_rag_log_session` (`session_id`),
    KEY `idx_rag_log_create_time` (`create_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问答日志表';

-- ============================================================
-- 5.3.18 RAG 任务表（P0-08）
-- ============================================================
DROP TABLE IF EXISTS `campus_rag_task`;
CREATE TABLE `campus_rag_task` (
    `id`              bigint       NOT NULL AUTO_INCREMENT COMMENT '主键',
    `operation`       char(1)      NOT NULL COMMENT '1 upsert 2 delete',
    `source_type`     char(1)      NOT NULL COMMENT '1公告 2知识库',
    `source_id`       bigint       NOT NULL COMMENT '原文档 id',
    `status`          char(1)      NOT NULL DEFAULT '0' COMMENT '0 PENDING 1 PROCESSING 2 SUCCESS 3 FAILED',
    `retry_count`     int          NOT NULL DEFAULT 0 COMMENT '已重试次数（上限 3）',
    `next_retry_time` datetime     DEFAULT NULL COMMENT '下次重试时间（指数退避）',
    `last_error`      varchar(500) DEFAULT NULL COMMENT '最近错误信息',
    `create_by`       bigint       DEFAULT NULL COMMENT '创建人',
    `create_time`     datetime     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_by`       bigint       DEFAULT NULL COMMENT '更新人',
    `update_time`     datetime     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `del_flag`        char(1)      NOT NULL DEFAULT '0' COMMENT '逻辑删除',
    PRIMARY KEY (`id`),
    KEY `idx_rag_task_status_retry` (`status`, `next_retry_time`),
    KEY `idx_rag_task_source` (`source_type`, `source_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RAG 任务表';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- 建表完成。共 18 张业务表：
-- campus_department, campus_term, campus_class, campus_course,
-- campus_student, campus_teacher, campus_course_offering,
-- campus_course_schedule, campus_score, campus_score_audit,
-- campus_announcement, campus_file, campus_leave, campus_message,
-- campus_knowledge, campus_rag_chunk, campus_rag_log, campus_rag_task
-- ============================================================
