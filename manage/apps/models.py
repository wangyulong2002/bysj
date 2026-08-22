# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class CampusDepartment(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    dept_name = models.CharField(max_length=50, db_comment='院系名称')
    dept_code = models.CharField(unique=True, max_length=20, db_comment='院系编码（唯一）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除：0正常 2删除')

    class Meta:
        managed = True
        db_table = 'campus_department'
        db_table_comment = '院系表'


class CampusTerm(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    term_name = models.CharField(max_length=50, db_comment='学期名称')
    start_date = models.DateField(db_comment='开始日期')
    end_date = models.DateField(db_comment='结束日期')
    total_weeks = models.IntegerField(db_comment='总周数')
    is_current = models.CharField(max_length=1, db_comment='是否当前学期：0否 1是（任意时刻仅一个）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    # A unique constraint could not be introspected.
    class Meta:
        managed = True
        db_table = 'campus_term'
        db_table_comment = '学期表'


class CampusClass(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    class_name = models.CharField(max_length=50, db_comment='班级名称（如：计科2301）')
    class_code = models.CharField(unique=True, max_length=20, db_comment='班级编码（唯一）')
    grade = models.CharField(max_length=10, db_comment='年级（如：2023）')
    major = models.CharField(max_length=50, blank=True, null=True, db_comment='专业')
    department = models.ForeignKey(CampusDepartment, models.DO_NOTHING, blank=True, null=True, db_comment='院系 id')
    counselor = models.ForeignKey('users.CustomUser', models.RESTRICT, blank=True, null=True, db_comment='辅导员（sys_user.id）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_class'
        db_table_comment = '班级表'


class CampusCourse(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    course_name = models.CharField(max_length=100, db_comment='课程名称')
    course_code = models.CharField(unique=True, max_length=30, db_comment='课程编码（唯一）')
    credit = models.DecimalField(max_digits=3, decimal_places=1, db_comment='学分')
    hours = models.IntegerField(db_comment='总学时')
    department = models.ForeignKey(CampusDepartment, models.DO_NOTHING, blank=True, null=True, db_comment='开课院系')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_course'
        db_table_comment = '课程表'


class CampusStudent(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    user = models.OneToOneField('users.CustomUser', models.RESTRICT, db_comment='sys_user.id（唯一）')
    student_no = models.CharField(unique=True, max_length=20, db_comment='学号（唯一，权威字段）')
    class_field = models.ForeignKey(CampusClass, models.DO_NOTHING, db_column='class_id', blank=True, null=True, db_comment='班级 id')  # Field renamed because it was a Python reserved word.
    enroll_year = models.CharField(max_length=10, blank=True, null=True, db_comment='入学年份')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_student'
        db_table_comment = '学生档案表'


class CampusTeacher(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    user = models.OneToOneField('users.CustomUser', models.RESTRICT, db_comment='sys_user.id（唯一）')
    teacher_no = models.CharField(unique=True, max_length=20, db_comment='工号（唯一，权威字段）')
    title = models.CharField(max_length=20, blank=True, null=True, db_comment='职称')
    department = models.ForeignKey(CampusDepartment, models.DO_NOTHING, blank=True, null=True, db_comment='所属院系')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_teacher'
        db_table_comment = '教师档案表'


class CampusCourseOffering(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    course = models.ForeignKey(CampusCourse, models.DO_NOTHING, db_comment='课程 id')
    term = models.ForeignKey(CampusTerm, models.DO_NOTHING, db_comment='学期 id')
    class_field = models.ForeignKey(CampusClass, models.DO_NOTHING, db_column='class_id', db_comment='班级 id')  # Field renamed because it was a Python reserved word.
    teacher = models.ForeignKey('users.CustomUser', models.RESTRICT, db_comment='任课教师（sys_user.id）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_course_offering'
        unique_together = (('term', 'class_field', 'course'),)
        db_table_comment = '教学班表'


class CampusCourseSchedule(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    offering = models.ForeignKey(CampusCourseOffering, models.DO_NOTHING, db_comment='教学班 id')
    week_start = models.IntegerField(db_comment='起始周')
    week_end = models.IntegerField(db_comment='结束周')
    day_of_week = models.IntegerField(db_comment='星期（1~7）')
    period_start = models.IntegerField(db_comment='开始节次')
    period_end = models.IntegerField(db_comment='结束节次')
    location = models.CharField(max_length=50, blank=True, null=True, db_comment='上课地点（v1 仅展示）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_course_schedule'
        db_table_comment = '排课表'


class CampusScore(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    student = models.ForeignKey(CampusStudent, models.DO_NOTHING, db_comment='学生档案 id')
    offering = models.ForeignKey(CampusCourseOffering, models.DO_NOTHING, db_comment='教学班 id')
    usual_score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_comment='平时成绩')
    exam_score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_comment='考试成绩')
    total_score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_comment='总评成绩（自动计算）')
    usual_ratio = models.IntegerField(blank=True, null=True, db_comment='平时占比快照（发布时固化）')
    exam_ratio = models.IntegerField(blank=True, null=True, db_comment='考试占比快照')
    is_published = models.CharField(max_length=1, db_comment='0未发布 1已发布')
    version = models.IntegerField(db_comment='乐观锁版本号（3.6/A-02）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='录入人')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='最近修改人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='最近修改时间')
    publish_by = models.BigIntegerField(blank=True, null=True, db_comment='发布人')
    publish_time = models.DateTimeField(blank=True, null=True, db_comment='发布时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_score'
        unique_together = (('student', 'offering'),)
        db_table_comment = '成绩表'


class CampusScoreAudit(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    student = models.ForeignKey(CampusStudent, models.DO_NOTHING, db_comment='学生档案 id')
    offering = models.ForeignKey(CampusCourseOffering, models.DO_NOTHING, db_comment='教学班 id')
    old_score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_comment='修改前总评')
    new_score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, db_comment='修改后总评')
    old_detail = models.JSONField(blank=True, null=True, db_comment='修改前明细（B-11：usual/exam/ratios）')
    new_detail = models.JSONField(blank=True, null=True, db_comment='修改后明细（B-11：usual/exam/ratios）')
    operator_id = models.BigIntegerField(blank=True, null=True, db_comment='操作人')
    operation = models.CharField(max_length=1, db_comment='1录入 2修改 3发布 4撤销发布')
    operation_time = models.DateTimeField(blank=True, null=True, db_comment='操作时间')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_score_audit'
        db_table_comment = '成绩审计表'


class CampusAnnouncement(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    title = models.CharField(max_length=100, db_comment='标题')
    content = models.TextField(blank=True, null=True, db_comment='内容')
    ann_type = models.CharField(max_length=1, db_comment='1校园 2院系 3班级')
    target_class = models.ForeignKey(CampusClass, models.DO_NOTHING, blank=True, null=True, db_comment='班级公告目标班级（ann_type=3 时填，可空；v1 单目标）')
    target_department = models.ForeignKey(CampusDepartment, models.DO_NOTHING, blank=True, null=True, db_comment='院系公告目标院系（ann_type=2 时填，可空）')
    publisher = models.ForeignKey('users.CustomUser', models.RESTRICT, blank=True, null=True, db_comment='发布人（sys_user.id，仅管理员）')
    is_top = models.CharField(max_length=1, db_comment='是否置顶')
    status = models.CharField(max_length=1, db_comment='0草稿 1发布 2下架')
    publish_time = models.DateTimeField(blank=True, null=True, db_comment='发布时间')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_announcement'
        db_table_comment = '公告表'


class CampusFile(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    original_name = models.CharField(max_length=255, db_comment='原始文件名')
    stored_name = models.CharField(max_length=64, db_comment='服务端存储名（随机 UUID）')
    mime_type = models.CharField(max_length=100, db_comment='MIME 类型')
    file_size = models.BigIntegerField(db_comment='大小（字节）')
    storage_path = models.CharField(max_length=255, db_comment='存储相对路径')
    file_hash = models.CharField(max_length=64, blank=True, null=True, db_comment='文件哈希（去重/校验）')
    uploader = models.ForeignKey('users.CustomUser', models.RESTRICT, blank=True, null=True, db_comment='上传人（sys_user.id）')
    owner_id = models.BigIntegerField(blank=True, null=True, db_comment='归属用户（B-03，ACL 判定）')
    biz_type = models.CharField(max_length=30, blank=True, null=True, db_comment='业务类型（avatar/leave_attachment/announcement_attachment，P1-16）')
    biz_id = models.BigIntegerField(blank=True, null=True, db_comment='业务记录 id（P1-16：leave_id/announcement_id）')
    visibility = models.CharField(max_length=1, db_comment='可见性（P1-16：1私有 2本人+授权 3登录可见 4公开）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_file'
        db_table_comment = '文件表'


class CampusLeave(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    student = models.ForeignKey(CampusStudent, models.DO_NOTHING, db_comment='学生档案 id')
    leave_type = models.CharField(max_length=1, db_comment='1事假 2病假 3其他')
    reason = models.CharField(max_length=500, blank=True, null=True, db_comment='请假事由')
    start_time = models.DateTimeField(db_comment='开始时间')
    end_time = models.DateTimeField(db_comment='结束时间')
    leave_duration_minutes = models.IntegerField(db_comment='时长权威字段（P1-14，分钟）')
    total_days = models.DecimalField(max_digits=4, decimal_places=1, db_comment='时长（天，由分钟换算，展示用）')
    status = models.CharField(max_length=1, db_comment='0待审批 1通过 2驳回 3撤销')
    version = models.IntegerField(db_comment='乐观锁版本号（3.6/A-02）')
    approver_id = models.BigIntegerField(blank=True, null=True, db_comment='审批人（辅导员 sys_user.id）')
    approve_time = models.DateTimeField(blank=True, null=True, db_comment='审批时间')
    approve_comment = models.CharField(max_length=500, blank=True, null=True, db_comment='审批意见')
    attachment = models.ForeignKey(CampusFile, models.DO_NOTHING, blank=True, null=True, db_comment='附件文件 id（campus_file，可空）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='提交时间/创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_leave'
        db_table_comment = '请假表'


class CampusMessage(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    user = models.ForeignKey('users.CustomUser', models.RESTRICT, db_comment='接收用户（sys_user.id）')
    msg_type = models.CharField(max_length=1, db_comment='1请假审批 2系统 3公告（v1 不生成，B-11）')
    title = models.CharField(max_length=100, blank=True, null=True, db_comment='标题')
    content = models.CharField(max_length=500, blank=True, null=True, db_comment='内容')
    business_type = models.CharField(max_length=30, blank=True, null=True, db_comment='业务类型（leave/announcement/...）')
    business_id = models.BigIntegerField(blank=True, null=True, db_comment='业务记录 id')
    is_read = models.CharField(max_length=1, db_comment='0未读 1已读')
    read_time = models.DateTimeField(blank=True, null=True, db_comment='阅读时间')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_message'
        db_table_comment = '站内消息表'


class CampusKnowledge(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    title = models.CharField(max_length=100, db_comment='标题')
    category = models.CharField(max_length=1, db_comment='分类（1师资 2宿舍 3食堂 4制度 5招生 6设施 7其他）')
    content = models.TextField(blank=True, null=True, db_comment='正文（富文本）')
    tags = models.CharField(max_length=200, blank=True, null=True, db_comment='标签（逗号分隔）')
    content_hash = models.CharField(max_length=64, blank=True, null=True, db_comment='内容哈希（变更检测，避免无变化重复向量化）')
    status = models.CharField(max_length=1, db_comment='0草稿 1发布（发布即触发向量化）')
    publisher = models.ForeignKey('users.CustomUser', models.RESTRICT, blank=True, null=True, db_comment='发布人（sys_user.id）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_knowledge'
        db_table_comment = '知识库文档表'


class CampusRagChunk(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    source_type = models.CharField(max_length=1, db_comment='1公告 2知识库')
    source_id = models.BigIntegerField(db_comment='原文档 id')
    source_version = models.IntegerField(db_comment='文档版本号（编辑后递增，整源重建判定）')
    chunk_index = models.IntegerField(db_comment='分片序号')
    content = models.TextField(blank=True, null=True, db_comment='分片文本（冗余存储）')
    title = models.CharField(max_length=100, blank=True, null=True, db_comment='来源标题')
    url = models.CharField(max_length=255, blank=True, null=True, db_comment='来源链接')
    status = models.CharField(max_length=1, db_comment='0待向量化 1已向量化 2失败')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_rag_chunk'
        db_table_comment = '向量化分片表'


class CampusRagLog(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    session_id = models.CharField(max_length=64, blank=True, null=True, db_comment='会话 id（前端 uuid）')
    question = models.CharField(max_length=500, blank=True, null=True, db_comment='用户问题（P2-18：默认不存全文，仅摘要/置空）')
    answer = models.TextField(blank=True, null=True, db_comment='回答')
    ref_ids = models.CharField(max_length=500, blank=True, null=True, db_comment='引用来源 id 列表')
    hit_count = models.IntegerField(db_comment='命中检索片段数')
    model = models.CharField(max_length=30, blank=True, null=True, db_comment='生成模型')
    prompt_tokens = models.IntegerField(db_comment='输入 token')
    completion_tokens = models.IntegerField(db_comment='输出 token')
    cost_time_ms = models.IntegerField(db_comment='总耗时')
    ip = models.CharField(max_length=50, blank=True, null=True, db_comment='提问者 IP（P2-18：落库前哈希/脱敏）')
    feedback = models.CharField(max_length=1, db_comment='0未评 1赞 2踩')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_rag_log'
        db_table_comment = '问答日志表'


class CampusRagTask(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    operation = models.CharField(max_length=1, db_comment='1 upsert 2 delete')
    source_type = models.CharField(max_length=1, db_comment='1公告 2知识库')
    source_id = models.BigIntegerField(db_comment='原文档 id')
    status = models.CharField(max_length=1, db_comment='0 PENDING 1 PROCESSING 2 SUCCESS 3 FAILED')
    retry_count = models.IntegerField(db_comment='已重试次数（上限 3）')
    next_retry_time = models.DateTimeField(blank=True, null=True, db_comment='下次重试时间（指数退避）')
    last_error = models.CharField(max_length=500, blank=True, null=True, db_comment='最近错误信息')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_rag_task'
        db_table_comment = 'RAG 任务表'


class CampusIdempotencyKey(models.Model):
    id = models.BigAutoField(primary_key=True, db_comment='主键')
    biz_key = models.CharField(unique=True, max_length=64, db_comment='幂等键（user_id+method+path+body 哈希，唯一）')
    user_id = models.BigIntegerField(blank=True, null=True, db_comment='操作人（sys_user.id）')
    method = models.CharField(max_length=20, db_comment='请求方法')
    path = models.CharField(max_length=255, db_comment='请求路径')
    body_hash = models.CharField(max_length=64, blank=True, null=True, db_comment='请求体哈希（SHA-256）')
    response_code = models.IntegerField(db_comment='首次响应 code')
    response_body = models.JSONField(blank=True, null=True, db_comment='首次响应体（重复请求直接返回）')
    expire_time = models.DateTimeField(db_comment='过期时间（业务超时 + 24h）')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'campus_idempotency_key'
        db_table_comment = '幂等记录表'


class SysDictType(models.Model):
    """字典类型表（设计 5.2，sys_dict_type）。"""

    dict_name = models.CharField(max_length=100, db_comment='字典名称')
    dict_type = models.CharField(unique=True, max_length=100, db_comment='字典类型（唯一）')
    status = models.CharField(max_length=1, default='0', db_comment='状态：0正常 1停用')
    remark = models.CharField(max_length=500, blank=True, null=True, db_comment='备注')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'sys_dict_type'
        db_table_comment = '字典类型表'


class SysDictData(models.Model):
    """字典数据表（设计 5.2，sys_dict_data）。"""

    dict_sort = models.IntegerField(db_comment='排序')
    dict_label = models.CharField(max_length=100, db_comment='标签')
    dict_value = models.CharField(max_length=100, db_comment='值')
    dict_type = models.CharField(max_length=100, db_comment='类型（关联 sys_dict_type）')
    css_class = models.CharField(max_length=100, blank=True, null=True, db_comment='样式 class')
    list_class = models.CharField(max_length=100, blank=True, null=True, db_comment='列表样式')
    is_default = models.CharField(max_length=1, db_comment='是否默认：Y/N')
    status = models.CharField(max_length=1, db_comment='状态：0正常 1停用')
    remark = models.CharField(max_length=500, blank=True, null=True, db_comment='备注')
    create_by = models.BigIntegerField(blank=True, null=True, db_comment='创建人')
    create_time = models.DateTimeField(blank=True, null=True, db_comment='创建时间')
    update_by = models.BigIntegerField(blank=True, null=True, db_comment='更新人')
    update_time = models.DateTimeField(blank=True, null=True, db_comment='更新时间')
    del_flag = models.CharField(max_length=1, db_comment='逻辑删除')

    class Meta:
        managed = True
        db_table = 'sys_dict_data'
        db_table_comment = '字典数据表'
