#!/usr/bin/env python3
"""生成演示数据 SQL（每张业务表 >= 10 条，幂等可重复执行）。

用法：
  python3 scripts/gen_seed_demo.py          # 生成 sql/seed_demo_data.sql
  mysql -h127.0.0.1 -P3307 -uroot -p123456 < sql/seed_demo_data.sql

设计约束对齐（设计报告 5.x）：
- 数据段：id 50000~50130（避开业务自增 id），删除走固定 id 段 → 幂等
- 外键依赖顺序：dept→class/course→term→sys_user→student/teacher→offering→schedule/score/...
- 通用审计字段：create_by/create_time/update_by/update_time/del_flag('0')
- sys_user 密码：PBKDF2（123456），role_code 区分角色
- campus_term.is_current 仅一条；排课不冲突；score (student,offering) 唯一
"""
import hashlib
import os

START = 50000
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sql", "seed_demo_data.sql")


def pbkdf2(raw: str = "123456") -> str:
    """生成与 Django 兼容的 PBKDF2 密码哈希（123456）。"""
    iterations = 10000
    salt = os.urandom(8).hex()
    dk = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${__import__('base64').b64encode(dk).decode().rstrip('=')}"


# ---- 基础数据 ----
DEPTS = ["计算机学院", "软件学院", "人工智能学院", "电子信息学院", "机械工程学院",
         "土木工程学院", "经济管理学院", "外国语学院", "艺术设计学院", "数理学院"]
CLASSES = ["计科2301", "软工2301", "人工智能2301", "电信2301", "机械2301",
           "土木2301", "经管2301", "英语2301", "艺术2301", "数理2301"]
COURSES = [("程序设计基础", "CS101"), ("数据结构", "CS201"), ("操作系统", "CS301"),
           ("计算机网络", "CS302"), ("数据库原理", "CS401"), ("软件工程", "SE201"),
           ("机器学习", "AI301"), ("数字电路", "EE201"), ("机械制图", "ME101"),
           ("高等数学", "MA101")]

PWD = pbkdf2()
ID = [START + i for i in range(130)]


def audit(creator: int = 1) -> str:
    """通用审计字段（5.1）。"""
    return f"1, NOW(), {creator}, NOW(), '0'"


def main() -> None:
    sql = []
    A = sql.append
    A("-- ============================================================")
    A("-- seed_demo_data.sql  演示数据（每张业务表 >= 10 条）")
    A("-- 由 scripts/gen_seed_demo.py 生成；幂等：删除 id 50000~50129 后重建")
    A("-- 依赖：先执行 init_all.sql（表结构）")
    A("-- ============================================================")
    A("USE campus;")
    A("SET NAMES utf8mb4;")
    A("SET FOREIGN_KEY_CHECKS = 0;")

    # 清理数据段（幂等）：覆盖所有种子 id 段（基础表 50000~50129 +
    # knowledge +20000 / rag_chunk +30000 / rag_log +40000 / rag_task +50000 /
    # idempotency +60000 / announcement +70000），统一 50000~120010
    for t in ["campus_department", "campus_class", "campus_course", "campus_term",
              "campus_student", "campus_teacher", "campus_course_offering",
              "campus_course_schedule", "campus_score", "campus_score_audit",
              "campus_leave", "campus_message", "campus_file", "campus_knowledge",
              "campus_rag_chunk", "campus_rag_log", "campus_rag_task",
              "campus_idempotency_key", "campus_announcement"]:
        A(f"DELETE FROM {t} WHERE id BETWEEN {START} AND {START + 70010};")
    A("DELETE FROM sys_user WHERE username LIKE 'demo\\_%';")
    A("")

    # 1. 院系（10）
    A("-- 1. 院系 campus_department（10）")
    for i in range(10):
        A(f"INSERT INTO campus_department (id, dept_name, dept_code, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[0] + i}, '{DEPTS[i]}', 'D{i + 1:02d}', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 2. 班级（10，辅导员关联后面建，先插入班级再 UPDATE counselor）
    A("-- 2. 班级 campus_class（10，辅导员稍后回填）")
    for i in range(10):
        grade = 2023 + (i % 3)
        A(f"INSERT INTO campus_class (id, class_name, class_code, grade, major, department_id, counselor_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[10] + i}, '{CLASSES[i]}', 'C{i + 1:02d}', {grade}, 'demo专业{i + 1}', {ID[0] + (i % 10)}, NULL, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 3. 课程（10）
    A("-- 3. 课程 campus_course（10）")
    for i in range(10):
        name, code = COURSES[i]
        A(f"INSERT INTO campus_course (id, course_name, course_code, credit, hours, department_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[20] + i}, '{name}', '{code}', {3.0 if i % 2 else 2.5}, {48 + i * 4}, {ID[0] + (i % 10)}, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 4. 学期（10，仅一条 is_current）
    A("-- 4. 学期 campus_term（10，仅 1 条当前）")
    for i in range(10):
        year = 2021 + i // 2
        term_no = (i % 2) + 1
        is_cur = "1" if i == 8 else "0"  # 2025-2026 第一学期为当前
        A(f"INSERT INTO campus_term (id, term_name, start_date, end_date, total_weeks, is_current, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[30] + i}, '{year}-{year + 1}学年第{['一', '二'][i % 2]}学期', "
          f"'{year}-09-01', '{year + 1}-01-18', 20, '{is_cur}', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 5. 辅导员（v2.4 无专职辅导员）：由教师兼任（demo_t01~10 被班级 counselor_id 指定）

    # 6. 教师 sys_user + campus_teacher（10）
    A("-- 6. 教师 sys_user + campus_teacher（10，role=teacher）")
    for i in range(10):
        uid = 90000 + i  # sys_user id 段（用固定段便于引用）
        A(f"INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, del_flag, role_code, teacher_no, password_version, create_by, create_time, update_by, update_time) "
          f"VALUES ({uid}, 'demo_t{i + 1:02d}', '教师{i + 1}', '{PWD}', 0, '0', '0', 'teacher', 'T{i + 1:04d}', 0, 1, NOW(), 1, NOW());")
        A(f"INSERT INTO campus_teacher (id, user_id, teacher_no, title, department_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[40] + i}, {uid}, 'T{i + 1:04d}', '{['讲师', '副教授', '教授', '助教'][i % 4]}', {ID[0] + (i % 10)}, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 7. 学生 sys_user + campus_student（10，每班 1 人）
    A("-- 7. 学生 sys_user + campus_student（10，role=student，每班 1 人）")
    for i in range(10):
        uid = 91000 + i
        A(f"INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, del_flag, role_code, student_no, password_version, create_by, create_time, update_by, update_time) "
          f"VALUES ({uid}, 'demo_s{i + 1:02d}', '学生{i + 1}', '{PWD}', 0, '0', '0', 'student', 'S{i + 1:08d}', 0, 1, NOW(), 1, NOW());")
        A(f"INSERT INTO campus_student (id, user_id, student_no, class_id, enroll_year, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[50] + i}, {uid}, 'S{i + 1:08d}', {ID[10] + i}, {2023 + (i % 3)}, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 8. 回填班级辅导员（v2.4：教师兼任，班级 i 的辅导员 = demo_t[i%10+1]，每人兼任 1 班 ≤2）
    A("-- 8. 回填班级辅导员（教师兼任 demo_t01~10）")
    for i in range(10):
        A(f"UPDATE campus_class SET counselor_id = {90000 + i} WHERE id = {ID[10] + i};")
    A("")

    # 9. 教学班（10：当前学期 课程×班级×教师）
    A("-- 9. 教学班 campus_course_offering（10，当前学期）")
    for i in range(10):
        tid = 90000 + i
        A(f"INSERT INTO campus_course_offering (id, course_id, term_id, class_id, teacher_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[60] + i}, {ID[20] + i}, {ID[30] + 8}, {ID[10] + i}, {tid}, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 10. 排课（10：每教学班 1 条，时间不冲突）
    A("-- 10. 排课 campus_course_schedule（10，时间不冲突）")
    for i in range(10):
        day = (i % 5) + 1
        ps = (i % 4) * 2 + 1
        A(f"INSERT INTO campus_course_schedule (id, offering_id, week_start, week_end, day_of_week, period_start, period_end, location, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[70] + i}, {ID[60] + i}, 1, 20, {day}, {ps}, {ps + 1}, '教1-{100 + i}室', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 11. 成绩（10：学生×教学班 唯一）
    A("-- 11. 成绩 campus_score（10，发布）")
    for i in range(10):
        usual = 80 + i
        exam = 70 + (i * 3) % 25
        total = round(usual * 0.4 + exam * 0.6, 2)
        A(f"INSERT INTO campus_score (id, student_id, offering_id, usual_score, exam_score, total_score, usual_ratio, exam_ratio, is_published, version, create_by, update_by, update_time, publish_by, publish_time, del_flag) "
          f"VALUES ({ID[80] + i}, {ID[50] + i}, {ID[60] + i}, {usual}.00, {exam}.00, {total}, 40, 60, '1', 0, 1, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 12. 成绩审计（10）
    A("-- 12. 成绩审计 campus_score_audit（10）")
    for i in range(10):
        A(f"INSERT INTO campus_score_audit (id, student_id, offering_id, old_score, new_score, old_detail, new_detail, operator_id, operation, operation_time, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[90] + i}, {ID[50] + i}, {ID[60] + i}, 75.00, {78 + i}.50, JSON_OBJECT('usual',75,'exam',75), JSON_OBJECT('usual',80,'exam',{75 + i}), 90000, '{['2', '1'][i % 2]}', NOW(), 1, NOW(), 1, NOW(), '0');")
    A("")

    # 13. 请假（10：学生提交，状态混合，审批人=兼任教师 id=90000+）
    A("-- 13. 请假 campus_leave（10，状态混合，审批人=兼任教师）")
    for i in range(10):
        status = "1" if i < 5 else ("0" if i < 8 else "2")
        minutes = (i + 1) * 120
        A(f"INSERT INTO campus_leave (id, student_id, leave_type, reason, start_time, end_time, leave_duration_minutes, total_days, status, approver_id, approve_time, approve_comment, version, create_time, create_by, update_by, update_time, del_flag) "
          f"VALUES ({ID[100] + i}, {ID[50] + i}, '{str(i % 3 + 1)}', '请假事由{i + 1}（演示数据）', DATE_SUB(NOW(), INTERVAL {i} DAY), DATE_ADD(DATE_SUB(NOW(), INTERVAL {i} DAY), INTERVAL {i + 1} HOUR), {minutes}, {minutes / 60}, '{status}', "
          f"{(90000 + i) if status == '1' else 'NULL'}, {'NOW()' if status == '1' else 'NULL'}, {'\"同意\"' if status == '1' else 'NULL'}, 0, NOW(), 1, 1, NOW(), '0');")
    A("")

    # 14. 站内消息（10）
    A("-- 14. 站内消息 campus_message（10）")
    for i in range(10):
        A(f"INSERT INTO campus_message (id, user_id, msg_type, title, content, business_type, business_id, is_read, read_time, create_time, create_by, update_by, update_time, del_flag) "
          f"VALUES ({ID[110] + i}, {91000 + i}, '1', '请假审批结果', '您的请假已{'通过' if i < 5 else '驳回'}（演示数据）', 'leave', {ID[100] + i}, '{'0' if i % 2 else '1'}', {'NOW()' if i % 2 else 'NULL'}, NOW(), 1, 1, NOW(), '0');")
    A("")

    # 15. 文件（10）
    A("-- 15. 文件 campus_file（10）")
    for i in range(10):
        A(f"INSERT INTO campus_file (id, original_name, stored_name, mime_type, file_size, storage_path, file_hash, uploader_id, owner_id, biz_type, biz_id, visibility, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[120] + i}, 'demo_{i + 1}.jpg', 'demo-{i + 1:08x}', 'image/jpeg', {1024 + i * 100}, 'uploads/demo/demo_{i + 1}.jpg', '{hashlib.sha256(f'demo{i}'.encode()).hexdigest()}', 91000, {91000 + i}, '{['avatar', 'leave_attachment'][i % 2]}', {ID[100] + i}, '2', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 16. 知识库（10）
    A("-- 16. 知识库 campus_knowledge（10）")
    cats = ["1", "2", "3", "4", "5", "6", "7"]
    for i in range(10):
        A(f"INSERT INTO campus_knowledge (id, title, category, content, tags, content_hash, status, publisher_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[0] + i + 20000}, '知识库文档{i + 1}（演示）', '{cats[i % 7]}', '这里是知识库第{i + 1}条演示内容……', '标签{i % 5 + 1}', '{hashlib.sha256(f'k{i}'.encode()).hexdigest()}', '{'1' if i < 7 else '0'}', 1, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 17. RAG 分片（10）
    A("-- 17. RAG 分片 campus_rag_chunk（10）")
    for i in range(10):
        A(f"INSERT INTO campus_rag_chunk (id, source_type, source_id, source_version, chunk_index, content, title, url, status, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[0] + i + 30000}, '{str(i % 2 + 1)}', {ID[0] + i + 20000}, 1, 0, '分片内容{i + 1}（演示）', '文档{i + 1}', '', '1', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 18. RAG 问答日志（10）
    A("-- 18. RAG 日志 campus_rag_log（10）")
    for i in range(10):
        A(f"INSERT INTO campus_rag_log (id, session_id, question, answer, ref_ids, hit_count, model, prompt_tokens, completion_tokens, cost_time_ms, ip, feedback, create_time, create_by, update_by, update_time, del_flag) "
          f"VALUES ({ID[0] + i + 40000}, 'demo-sess-{i}', '演示问题{i + 1}？', '这是演示回答{i + 1}。', '1,2', {i + 1}, 'deepseek-chat', {100 + i * 10}, {50 + i * 5}, {200 + i * 30}, '192.168.0.100', '{'0' if i % 3 else '1'}', NOW(), 1, 1, NOW(), '0');")
    A("")

    # 19. RAG 任务（10）
    A("-- 19. RAG 任务 campus_rag_task（10）")
    for i in range(10):
        status = "2" if i < 6 else "0"
        A(f"INSERT INTO campus_rag_task (id, operation, source_type, source_id, status, retry_count, next_retry_time, last_error, create_time, update_time, del_flag) "
          f"VALUES ({ID[0] + i + 50000}, '{str(i % 2 + 1)}', '{str(i % 2 + 1)}', {ID[0] + i + 20000}, '{status}', 0, NULL, NULL, NOW(), NOW(), '0');")
    A("")

    # 20. 幂等记录（10）
    A("-- 20. 幂等记录 campus_idempotency_key（10）")
    for i in range(10):
        A(f"INSERT INTO campus_idempotency_key (id, biz_key, user_id, method, path, body_hash, response_code, response_body, expire_time, create_time, del_flag) "
          f"VALUES ({ID[0] + i + 60000}, 'demo-biz-{i}', {91000 + i}, 'POST', '/api/demo', '{hashlib.sha256(f'b{i}'.encode()).hexdigest()}', 0, JSON_OBJECT('code',0,'msg','ok'), DATE_ADD(NOW(), INTERVAL 24 HOUR), NOW(), '0');")
    A("")

    # 21. 公告（10，状态机混合）
    A("-- 21. 公告 campus_announcement（10，状态混合）")
    for i in range(10):
        status = "1" if i < 5 else ("0" if i < 8 else "2")
        is_top = "1" if i < 2 else "0"
        ann_type = str(i % 3 + 1)
        target_class = str(ID[10] + i) if ann_type == "3" else "NULL"
        target_dept = str(ID[0] + i) if ann_type == "2" else "NULL"
        A(f"INSERT INTO campus_announcement (id, title, content, ann_type, target_class_id, target_department_id, publisher_id, is_top, status, publish_time, create_time, update_time, create_by, update_by, del_flag) "
          f"VALUES ({ID[0] + i + 70000}, '公告{i + 1}：{['开学通知', '校园活动', '选课提醒', '考试安排', '放假安排', '宿舍通知', '食堂通知', '图书馆通知', '竞赛通知', '校车安排'][i]}（演示）', '这是公告{i + 1}的演示内容，用于验证列表与详情。', '{ann_type}', {target_class}, {target_dept}, 1, '{is_top}', '{status}', "
          f"{'DATE_SUB(NOW(), INTERVAL ' + str(i + 1) + ' DAY)' if status == '1' else 'NULL'}, NOW(), NOW(), 1, 1, '0');")
    A("")

    A("SET FOREIGN_KEY_CHECKS = 1;")
    A("-- ============================================================")
    A("-- 演示数据生成完成（20 张表各 >= 10 条）。")
    A("-- 登录账号：demo_s01~10（学生）/ demo_t01~10（教师兼任辅导员），密码 123456")
    A("-- ============================================================")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(sql) + "\n")
    print(f"已生成: {OUT}（{len(sql)} 行）")


if __name__ == "__main__":
    main()
