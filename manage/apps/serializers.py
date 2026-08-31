"""DRF 序列化器（T2-1/T2-2/T2-3）。

设计基线：v2.2 5.3.1~5.3.6 表结构 + 6.4 /admin/api/** 管理接口。
- 字段与设计报告表结构一致（含唯一编码校验）；
- 外键关联展示名称（department_name/class_name/teacher_name 等）；
- 请求/响应统一用 DB 字段名（class_id/offering_id 等）。
"""
import random
import string
import time

from django.contrib.auth import get_user_model

from rest_framework import serializers

from .models import (
    CampusAnnouncement,
    CampusClass,
    CampusKnowledge,
    CampusCourse,
    CampusCourseOffering,
    CampusCourseSchedule,
    CampusDepartment,
    CampusLeave,
    CampusScore,
    CampusScoreAudit,
    CampusStudent,
    CampusTeacher,
    CampusTerm,
)

User = get_user_model()


def _gen_unique_code(prefix: str, qs, field: str, length: int = 6) -> str:
    """自动生成唯一业务编码：prefix + 随机字母数字（如 S20260801），冲突自动重试，时间戳兜底。"""
    chars = string.ascii_uppercase + string.digits
    for _ in range(30):
        code = prefix + "".join(random.choices(chars, k=length))
        if not qs.filter(**{field: code}).exists():
            return code
    return f"{prefix}{int(time.time())}"


class DepartmentSerializer(serializers.ModelSerializer):
    """院系（5.3.1）：dept_name + dept_code（唯一，可留空自动生成）。"""

    class Meta:
        model = CampusDepartment
        fields = ["id", "dept_name", "dept_code", "create_time"]
        read_only_fields = ["id", "create_time"]
        extra_kwargs = {"dept_code": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        """院系编码：缺失/留空自动生成唯一编码（DEPT 前缀）；更新时留空保留原值。"""
        code = (attrs.get("dept_code") or "").strip()
        if not code:
            code = (self.instance.dept_code if self.instance is not None
                    else _gen_unique_code("DEPT", CampusDepartment.objects.all(), "dept_code"))
        attrs["dept_code"] = code
        return attrs


class ClassSerializer(serializers.ModelSerializer):
    """班级（5.3.2）：指定辅导员/年级/专业/院系（B-12：v1 不含班主任字段）。"""

    department_name = serializers.CharField(
        source="department.dept_name", read_only=True, default=None
    )
    counselor_name = serializers.SerializerMethodField()
    department_id = serializers.PrimaryKeyRelatedField(
        source="department", queryset=CampusDepartment.objects.all(),
        allow_null=True, required=False, write_only=False,
    )
    counselor_id = serializers.PrimaryKeyRelatedField(
        source="counselor", queryset=User.objects.all(),
        allow_null=True, required=False, write_only=False,
    )

    def get_counselor_name(self, obj) -> str | None:
        """序列化辅导员展示名（昵称优先，其次用户名）。"""
        if obj.counselor is None:
            return None
        return obj.counselor.nick_name or obj.counselor.username

    class Meta:
        model = CampusClass
        fields = [
            "id", "class_name", "class_code", "grade", "major",
            "department_id", "department_name", "counselor_id", "counselor_name",
            "create_time",
        ]
        read_only_fields = ["id", "create_time"]
        extra_kwargs = {"class_code": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        """班级编码：缺失/留空自动生成唯一编码（CLS 前缀）；更新时留空保留原值。"""
        code = (attrs.get("class_code") or "").strip()
        if not code:
            code = (self.instance.class_code if self.instance is not None
                    else _gen_unique_code("CLS", CampusClass.objects.all(), "class_code"))
        attrs["class_code"] = code
        return attrs


class CourseSerializer(serializers.ModelSerializer):
    """课程（5.3.3）：course_name/course_code（唯一）/credit/hours/department_id。"""

    department_name = serializers.CharField(
        source="department.dept_name", read_only=True, default=None
    )
    department_id = serializers.PrimaryKeyRelatedField(
        source="department", queryset=CampusDepartment.objects.all(),
        allow_null=True, required=False, write_only=False,
    )

    class Meta:
        model = CampusCourse
        fields = [
            "id", "course_name", "course_code", "credit", "hours",
            "department_id", "department_name", "create_time",
        ]
        read_only_fields = ["id", "create_time"]
        extra_kwargs = {"course_code": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        """课程编码：缺失/留空自动生成唯一编码（CRS 前缀）；更新时留空保留原值。"""
        code = (attrs.get("course_code") or "").strip()
        if not code:
            code = (self.instance.course_code if self.instance is not None
                    else _gen_unique_code("CRS", CampusCourse.objects.all(), "course_code"))
        attrs["course_code"] = code
        return attrs


class TermSerializer(serializers.ModelSerializer):
    """学期（5.3.6）：起止日期 + 总周数 + is_current（任意时刻仅一个，见 5.1）。"""

    class Meta:
        model = CampusTerm
        fields = [
            "id", "term_name", "start_date", "end_date",
            "total_weeks", "is_current", "create_time",
        ]
        read_only_fields = ["id", "create_time"]

    def validate(self, attrs):
        """学期整体校验：结束日期不得早于开始日期。"""
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError("结束日期不能早于开始日期")
        return attrs


class OfferingSerializer(serializers.ModelSerializer):
    """教学班（5.3.4，核心）：课程/学期/班级/教师 四元组，唯一约束 (term, class, course)。"""

    course_name = serializers.CharField(source="course.course_name", read_only=True)
    term_name = serializers.CharField(source="term.term_name", read_only=True)
    class_name = serializers.CharField(source="class_field.class_name", read_only=True)
    teacher_name = serializers.SerializerMethodField()

    course_id = serializers.PrimaryKeyRelatedField(
        source="course", queryset=CampusCourse.objects.all()
    )
    term_id = serializers.PrimaryKeyRelatedField(
        source="term", queryset=CampusTerm.objects.all()
    )
    class_id = serializers.PrimaryKeyRelatedField(
        source="class_field", queryset=CampusClass.objects.all()
    )
    teacher_id = serializers.PrimaryKeyRelatedField(
        source="teacher", queryset=User.objects.all()
    )

    class Meta:
        model = CampusCourseOffering
        fields = [
            "id", "course_id", "course_name", "term_id", "term_name",
            "class_id", "class_name", "teacher_id", "teacher_name", "create_time",
        ]
        read_only_fields = ["id", "create_time"]

    def get_teacher_name(self, obj) -> str:
        """序列化任课教师展示名（昵称优先，其次用户名）。"""
        return obj.teacher.nick_name or obj.teacher.username


class StudentSerializer(serializers.ModelSerializer):
    """学生档案（5.3.7 / T2-8，方案 B：档案与 sys_user 账号联动）。

    - 创建：自动创建 sys_user（username=学号，角色 student，初始密码可指定，默认 123456）；
    - 姓名（nick_name）写入 sys_user；班级/入学年份写入档案；
    - user_id 由服务端联动写入（只读）。
    """

    class_name = serializers.CharField(
        source="class_field.class_name", read_only=True, default=None
    )
    username = serializers.CharField(source="user.username", read_only=True, default=None)
    user_id = serializers.IntegerField(source="user.id", read_only=True, default=None)
    nick_name = serializers.CharField(write_only=True, required=False, allow_blank=True,
                                      max_length=30, label="姓名")
    password = serializers.CharField(write_only=True, required=False, allow_blank=True,
                                     max_length=128, label="初始密码（默认 123456）")
    class_id = serializers.PrimaryKeyRelatedField(
        source="class_field", queryset=CampusClass.objects.all(),
        allow_null=True, required=False, write_only=False,
    )

    class Meta:
        model = CampusStudent
        fields = [
            "id", "student_no", "nick_name", "username", "password",
            "class_id", "class_name", "enroll_year", "user_id", "create_time",
        ]
        read_only_fields = ["id", "create_time"]
        extra_kwargs = {"student_no": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        """学号：缺失/留空自动生成唯一学号（S 前缀）；更新时留空保留原值。"""
        code = (attrs.get("student_no") or "").strip()
        if not code:
            code = (self.instance.student_no if self.instance is not None
                    else _gen_unique_code("S", CampusStudent.objects.all(), "student_no", length=8))
        attrs["student_no"] = code
        return attrs

    def create(self, validated_data):
        """创建：剔除联动字段（nick_name/password 由 ViewSet 消费，不进模型）。"""
        validated_data.pop("nick_name", None)
        validated_data.pop("password", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """更新：剔除联动字段（同 create）。"""
        validated_data.pop("nick_name", None)
        validated_data.pop("password", None)
        return super().update(instance, validated_data)


class TeacherSerializer(serializers.ModelSerializer):
    """教师档案（5.3.8 / T2-9，方案 B：档案与 sys_user 账号联动；ADR-010 兼任辅导员）。

    - 创建：自动创建 sys_user（username=工号，角色 teacher，初始密码可指定，默认 123456）；
    - 姓名（nick_name）写入 sys_user；职称/院系写入档案；
    - 兼任辅导员（ADR-010）：`is_counselor` + `counselor_class_ids`（1~2 个班级，前后端校验 ≤2），
      由 ViewSet 同步 `campus_class.counselor_id`；不占数据库约束。
    """

    department_name = serializers.CharField(
        source="department.dept_name", read_only=True, default=None
    )
    username = serializers.CharField(source="user.username", read_only=True, default=None)
    user_id = serializers.IntegerField(source="user.id", read_only=True, default=None)
    nick_name = serializers.CharField(write_only=True, required=False, allow_blank=True,
                                      max_length=30, label="姓名")
    password = serializers.CharField(write_only=True, required=False, allow_blank=True,
                                     max_length=128, label="初始密码（默认 123456）")
    department_id = serializers.PrimaryKeyRelatedField(
        source="department", queryset=CampusDepartment.objects.all(),
        allow_null=True, required=False, write_only=False,
    )
    # 兼任辅导员（ADR-010）：写入 1~2 个班级 id；读取返回当前兼任班级
    is_counselor = serializers.BooleanField(write_only=True, required=False, default=False)
    counselor_class_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True, required=False, allow_empty=True,
        label="兼任班级 id（1~2 个）",
    )
    counselor_class_id_list = serializers.SerializerMethodField(read_only=True)
    counselor_class_names = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampusTeacher
        fields = [
            "id", "teacher_no", "nick_name", "username", "password",
            "title", "department_id", "department_name", "user_id",
            "is_counselor", "counselor_class_ids",
            "counselor_class_id_list", "counselor_class_names",
            "create_time",
        ]
        read_only_fields = ["id", "create_time"]
        extra_kwargs = {"teacher_no": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        """工号：缺失/留空自动生成唯一工号（T 前缀）；更新时留空保留原值。"""
        code = (attrs.get("teacher_no") or "").strip()
        if not code:
            code = (self.instance.teacher_no if self.instance is not None
                    else _gen_unique_code("T", CampusTeacher.objects.all(), "teacher_no", length=8))
        attrs["teacher_no"] = code
        return attrs

    def get_counselor_class_id_list(self, obj) -> list[int]:
        """当前兼任班级 id 列表（ADR-010，前端编辑回显）。"""
        return list(
            CampusClass.objects.filter(counselor_id=obj.user_id, del_flag="0")
            .values_list("id", flat=True)
        )

    def get_counselor_class_names(self, obj) -> list[str]:
        """当前兼任班级名称列表（展示用）。"""
        return list(
            CampusClass.objects.filter(counselor_id=obj.user_id, del_flag="0")
            .values_list("class_name", flat=True)
        )

    def create(self, validated_data):
        """创建：剔除联动字段（nick_name/password/is_counselor/counselor_class_ids 由 ViewSet 消费）。"""
        for f in ("nick_name", "password", "is_counselor", "counselor_class_ids"):
            validated_data.pop(f, None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """更新：剔除联动字段（同 create）。"""
        for f in ("nick_name", "password", "is_counselor", "counselor_class_ids"):
            validated_data.pop(f, None)
        return super().update(instance, validated_data)


class ScoreSerializer(serializers.ModelSerializer):
    """成绩（5.3.10 / T4-1）：管理端按教学班查看成绩列表（含学生/课程信息）。"""

    student_no = serializers.CharField(source="student.student_no", read_only=True)
    student_name = serializers.CharField(
        source="student.user.nick_name", read_only=True, default=None
    )
    course_name = serializers.CharField(
        source="offering.course.course_name", read_only=True, default=None
    )
    term_name = serializers.CharField(
        source="offering.term.term_name", read_only=True, default=None
    )
    class_name = serializers.CharField(
        source="offering.class_field.class_name", read_only=True, default=None
    )

    class Meta:
        model = CampusScore
        fields = [
            "id", "student_id", "student_no", "student_name",
            "offering_id", "course_name", "term_name", "class_name",
            "usual_score", "exam_score", "total_score",
            "usual_ratio", "exam_ratio", "is_published",
            "version", "publish_by", "publish_time", "update_time",
        ]
        read_only_fields = fields


class ScoreAuditSerializer(serializers.ModelSerializer):
    """成绩审计（5.3.11 / T4-1）：明细可还原（B-11）。"""

    student_no = serializers.CharField(source="student.student_no", read_only=True)
    student_name = serializers.CharField(
        source="student.user.nick_name", read_only=True, default=None
    )
    course_name = serializers.CharField(
        source="offering.course.course_name", read_only=True, default=None
    )
    operator_name = serializers.SerializerMethodField()

    class Meta:
        model = CampusScoreAudit
        fields = [
            "id", "student_id", "student_no", "student_name",
            "offering_id", "course_name",
            "old_score", "new_score", "old_detail", "new_detail",
            "operator_id", "operator_name", "operation", "operation_time",
        ]
        read_only_fields = fields

    def get_operator_name(self, obj):
        """操作人姓名（昵称优先）。"""
        if obj.operator_id is None:
            return None
        u = User.objects.filter(pk=obj.operator_id).first()
        return u.nick_name or u.username if u else None


class LeaveSerializer(serializers.ModelSerializer):
    """请假（5.3.12 / T5-6）：管理端查看全部记录。"""

    student_no = serializers.CharField(source="student.student_no", read_only=True)
    student_name = serializers.CharField(
        source="student.user.nick_name", read_only=True, default=None
    )
    approver_name = serializers.SerializerMethodField()

    class Meta:
        model = CampusLeave
        fields = [
            "id", "student_id", "student_no", "student_name",
            "leave_type", "reason", "start_time", "end_time",
            "leave_duration_minutes", "total_days", "status",
            "approver_id", "approver_name", "approve_time", "approve_comment",
            "attachment_id", "version", "create_time",
        ]
        read_only_fields = fields

    def get_approver_name(self, obj):
        """审批人姓名（昵称优先）。"""
        if obj.approver_id is None:
            return None
        u = User.objects.filter(pk=obj.approver_id).first()
        return u.nick_name or u.username if u else None


class AnnouncementSerializer(serializers.ModelSerializer):
    """公告（5.3.9 / T3-1）：类型/置顶/状态流转 + 单目标（4.2，P1-07）。

    **v2.5（ADR-011）**：移除班级公告类型——`ann_type` 仅 1校园/2院系，`target_class`
    字段随 migration 删除，序列化层不再暴露 `target_class_id`/`target_class_name`。

    - 院系公告（ann_type=2）必须选目标院系；
    - 校园公告（ann_type=1）不得指定目标院系；
    - publisher_id/publish_time 由服务端状态流转写入（只读，4.2 唯一发布方）。
    """

    target_department_name = serializers.CharField(
        source="target_department.dept_name", read_only=True, default=None
    )
    publisher_name = serializers.SerializerMethodField()

    target_department_id = serializers.PrimaryKeyRelatedField(
        source="target_department", queryset=CampusDepartment.objects.all(),
        allow_null=True, required=False, write_only=False,
    )

    class Meta:
        model = CampusAnnouncement
        fields = [
            "id", "title", "content", "ann_type",
            "target_department_id", "target_department_name",
            "publisher_id", "publisher_name",
            "is_top", "status", "publish_time", "create_time", "update_time",
        ]
        read_only_fields = ["id", "publisher_id", "publish_time", "create_time", "update_time"]

    def get_publisher_name(self, obj) -> str | None:
        """序列化发布人展示名（昵称优先，其次用户名）。"""
        if obj.publisher is None:
            return None
        return obj.publisher.nick_name or obj.publisher.username

    def validate_ann_type(self, value):
        """公告类型校验（v2.5：班级公告 3 已移除）。"""
        if value not in ("1", "2"):
            raise serializers.ValidationError("公告类型仅支持：1校园 2院系（班级公告已移除）")
        return value

    def validate(self, attrs):
        """目标类型与 ann_type 匹配校验（4.2：单目标发布，P1-07）。"""
        ann_type = attrs.get("ann_type")
        if ann_type == "2" and not attrs.get("target_department"):
            raise serializers.ValidationError({"target_department_id": "院系公告必须选择目标院系"})
        if ann_type == "1" and attrs.get("target_department"):
            raise serializers.ValidationError("校园公告无需指定目标院系")
        return attrs


class ScheduleSerializer(serializers.ModelSerializer):
    """排课（5.3.5）：基于教学班，星期/节次/起止周/地点（v1 不校验教室冲突，4.1）。"""

    offering_id = serializers.PrimaryKeyRelatedField(
        source="offering", queryset=CampusCourseOffering.objects.all()
    )

    class Meta:
        model = CampusCourseSchedule
        fields = [
            "id", "offering_id", "week_start", "week_end",
            "day_of_week", "period_start", "period_end", "location", "create_time",
        ]
        read_only_fields = ["id", "create_time"]

    def validate(self, attrs):
        """排课整体校验：周次/星期/节次范围与大小关系合法性。"""
        week_start = attrs.get("week_start")
        week_end = attrs.get("week_end")
        if week_start is not None and week_end is not None:
            if week_start < 1 or week_end < 1:
                raise serializers.ValidationError("周次必须为正整数")
            if week_end < week_start:
                raise serializers.ValidationError("结束周不能早于起始周")
        day = attrs.get("day_of_week")
        if day is not None and not (1 <= day <= 7):
            raise serializers.ValidationError("星期必须为 1~7")
        ps, pe = attrs.get("period_start"), attrs.get("period_end")
        if ps is not None and pe is not None:
            if ps < 1 or pe < ps:
                raise serializers.ValidationError("节次范围不合法（period_start ≤ period_end 且 ≥1）")
        return attrs


class KnowledgeSerializer(serializers.ModelSerializer):
    """知识库文档（T7-2，5.3.15/8.3）：CRUD + 发布/下架 + content_hash 变更检测。

    - category：1师资 2宿舍 3食堂 4制度 5招生 6设施 7其他；
    - status：0草稿 1发布（发布即触发向量化，任务写入见 knowledge_flow）；
    - content_hash 只读：服务端对剥离 HTML 后的正文（含标题）取 SHA-256（P0-09）。
    """

    publisher_name = serializers.SerializerMethodField()

    class Meta:
        model = CampusKnowledge
        fields = [
            "id", "title", "category", "content", "tags",
            "content_hash", "status",
            "publisher", "publisher_name", "create_time", "update_time",
        ]
        read_only_fields = ["id", "content_hash", "publisher", "create_time", "update_time"]

    def get_publisher_name(self, obj) -> str | None:
        """发布人展示名（昵称优先）。"""
        if obj.publisher is None:
            return None
        return obj.publisher.nick_name or obj.publisher.username

    def validate_category(self, value):
        """分类校验（5.3.15 枚举）。"""
        if value not in ("1", "2", "3", "4", "5", "6", "7"):
            raise serializers.ValidationError("分类仅支持：1师资 2宿舍 3食堂 4制度 5招生 6设施 7其他")
        return value

    def validate_status(self, value):
        """状态校验（0草稿 1发布）。"""
        if value not in ("0", "1"):
            raise serializers.ValidationError("状态仅支持：0草稿 1发布")
        return value

    def validate(self, attrs):
        """标题/正文必填（向量化数据源完整性）。"""
        title = attrs.get("title", getattr(self.instance, "title", None))
        content = attrs.get("content", getattr(self.instance, "content", None))
        if not (title or "").strip():
            raise serializers.ValidationError({"title": "标题不能为空"})
        if not (content or "").strip():
            raise serializers.ValidationError({"content": "正文不能为空"})
        return attrs
