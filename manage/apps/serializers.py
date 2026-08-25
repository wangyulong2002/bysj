"""DRF 序列化器（T2-1/T2-2/T2-3）。

设计基线：v2.2 5.3.1~5.3.6 表结构 + 6.4 /admin/api/** 管理接口。
- 字段与设计报告表结构一致（含唯一编码校验）；
- 外键关联展示名称（department_name/class_name/teacher_name 等）；
- 请求/响应统一用 DB 字段名（class_id/offering_id 等）。
"""
from django.contrib.auth import get_user_model

from rest_framework import serializers

from .models import (
    CampusClass,
    CampusCourse,
    CampusCourseOffering,
    CampusCourseSchedule,
    CampusDepartment,
    CampusTerm,
)

User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    """院系（5.3.1）：dept_name + dept_code（唯一）。"""

    class Meta:
        model = CampusDepartment
        fields = ["id", "dept_name", "dept_code", "create_time"]
        read_only_fields = ["id", "create_time"]

    def validate_dept_code(self, value: str) -> str:
        """院系编码校验：去空白且非空。"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("院系编码不能为空")
        return value


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

    class Meta:
        model = CampusClass
        fields = [
            "id", "class_name", "class_code", "grade", "major",
            "department_id", "department_name", "counselor_id", "counselor_name",
            "create_time",
        ]
        read_only_fields = ["id", "create_time"]

    def get_counselor_name(self, obj) -> str | None:
        """序列化辅导员展示名（昵称优先，其次用户名）。"""
        if obj.counselor is None:
            return None
        return obj.counselor.nick_name or obj.counselor.username

    def validate_class_code(self, value: str) -> str:
        """班级编码校验：去空白且非空。"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("班级编码不能为空")
        return value


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

    def validate_course_code(self, value: str) -> str:
        """课程编码校验：去空白且非空。"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError("课程编码不能为空")
        return value


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
