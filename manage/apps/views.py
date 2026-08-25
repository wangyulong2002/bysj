"""管理端 DRF 视图集（T2-1/T2-2/T2-3）。

设计基线：v2.2 4.1（排课冲突）、5.1（is_current 唯一/逻辑删除/事务）、6.4（/admin/api/**）。
- 统一权限：仅 admin 角色可访问（DRF 权限类，6.4/P1-10）。
- 删除一律逻辑删除（del_flag='2'，5.1，不物理删除被引用记录）。
- 学期 is_current 切换：事务内先将旧学期置 0，再置新学期为 1（5.1/P1-04）。
- 教学班唯一约束：(term, class, course) 数据库兜底 + 友好提示（T2-2）。
- 排课冲突（4.1 P0-06/B-04/P1-13）：班级冲突 + 教师冲突；
  冲突校验与写入同事务，固定 MySQL `SELECT ... FOR UPDATE`，
  按 class_id/teacher_id 升序锁行，补死锁重试（OperationalError 1213）。
"""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.utils import OperationalError
from django.utils import timezone

from rest_framework import viewsets
from rest_framework.exceptions import (
    ErrorDetail,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .models import (
    CampusClass,
    CampusCourse,
    CampusCourseOffering,
    CampusCourseSchedule,
    CampusDepartment,
    CampusTerm,
)
from .renderers import _extract_message
from .serializers import (
    ClassSerializer,
    CourseSerializer,
    DepartmentSerializer,
    OfferingSerializer,
    ScheduleSerializer,
    TermSerializer,
)


# ===== 权限（6.4/P1-10：仅 admin 角色）=====

class IsAdminRole:
    """DRF 权限类：仅 role_code=admin 可访问 /admin/api/**。"""

    def has_permission(self, request, view) -> bool:
        """视图级权限：仅登录且 role_code=admin 可访问（6.4/P1-10）。"""
        user = request.user
        return bool(user and user.is_authenticated and user.role_code == "admin")

    def has_object_permission(self, request, view, obj) -> bool:
        """对象级权限：queryset 已按逻辑删除过滤，admin 角色即可访问。"""
        # 对象级权限：queryset 已按逻辑删除过滤，admin 角色即可访问
        return self.has_permission(request, view)


# ===== 统一异常处理（6.4：返回格式与应用端一致）=====

class ScheduleConflictError(Exception):
    """排课冲突（4.1 P0-06）：班级/教师时间重叠，转 4091。"""

    def __init__(self, message: str):
        super().__init__(message)


def _validation_codes(detail) -> set:
    """收集 ValidationError detail 中的所有错误码（DRF ErrorDetail.code）。"""
    codes: set = set()

    def _walk(node):
        """递归遍历 DRF detail 树，收集 ErrorDetail.code。"""
        if isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                if hasattr(v, "code"):
                    codes.add(v.code)
                elif isinstance(v, (dict, list, tuple)):
                    _walk(v)
        elif isinstance(node, ErrorDetail):
            codes.add(node.code)

    _walk(detail)
    return codes


def api_exception_handler(exc, context):
    """DRF 统一异常处理：业务异常返回 HTTP 200 + { code, message, data }（与应用端一致）。"""
    if isinstance(exc, ScheduleConflictError):
        return Response({"code": 4091, "message": str(exc), "data": None}, status=200)
    if isinstance(exc, IntegrityError):
        return Response(
            {"code": 4091, "message": "数据已存在：唯一编码或组合重复，请检查", "data": None},
            status=200,
        )
    if isinstance(exc, ValidationError):
        # 唯一约束（UniqueValidator/UniqueTogetherValidator code='unique'）→ 4091 冲突
        if "unique" in _validation_codes(exc.detail):
            return Response(
                {"code": 4091, "message": "数据已存在：唯一编码或组合重复，请检查", "data": None},
                status=200,
            )
        return Response(
            {"code": 4001, "message": _extract_message(exc.detail), "data": None}, status=200
        )
    if isinstance(exc, NotAuthenticated):
        return Response({"code": 4011, "message": "未登录或登录已过期", "data": None}, status=200)
    if isinstance(exc, PermissionDenied):
        return Response({"code": 4031, "message": "无操作权限", "data": None}, status=200)
    if isinstance(exc, NotFound):
        return Response({"code": 4001, "message": "记录不存在", "data": None}, status=200)
    return drf_exception_handler(exc, context)


# ===== 排课冲突校验与 FOR UPDATE 锁定（4.1 / B-04 / P1-13）=====

def _time_overlap_q(ps: int, pe: int) -> Q:
    """时间段重叠判定：A 与 B 重叠 ⟺ A.start ≤ B.end AND B.start ≤ A.end。"""
    return Q(period_start__lte=pe) & Q(period_end__gte=ps)


def _check_schedule_conflict(term_id, class_id, teacher_id, day_of_week,
                             period_start, period_end, exclude_id=None) -> None:
    """班级冲突 + 教师冲突检查（v1 仅校验这两类，4.1 P0-06）。冲突抛 ScheduleConflictError。"""
    qs = CampusCourseSchedule.objects.filter(
        offering__term_id=term_id,
        day_of_week=day_of_week,
        del_flag="0",
    ).exclude(pk=exclude_id)
    if not qs.exists():
        return

    class_conflict = qs.filter(offering__class_field_id=class_id).filter(
        _time_overlap_q(period_start, period_end)
    ).select_related("offering", "offering__class_field", "offering__course").first()
    if class_conflict is not None:
        off = class_conflict.offering
        raise ScheduleConflictError(
            f"班级冲突：{off.class_field.class_name} 在星期{day_of_week} 第"
            f"{class_conflict.period_start}~{class_conflict.period_end}节已有课程"
            f"《{off.course.course_name}》（第{class_conflict.week_start}~{class_conflict.week_end}周），"
            f"与本次节次 {period_start}~{period_end} 重叠"
        )

    teacher_conflict = qs.filter(offering__teacher_id=teacher_id).filter(
        _time_overlap_q(period_start, period_end)
    ).select_related("offering", "offering__course").first()
    if teacher_conflict is not None:
        off = teacher_conflict.offering
        raise ScheduleConflictError(
            f"教师冲突：该教师星期{day_of_week} 第"
            f"{teacher_conflict.period_start}~{teacher_conflict.period_end}节已有课程"
            f"《{off.course.course_name}》（第{teacher_conflict.week_start}~{teacher_conflict.week_end}周），"
            f"与本次节次 {period_start}~{period_end} 重叠"
        )


def _lock_conflict_offering_rows(term_id, class_id, teacher_id) -> None:
    """FOR UPDATE 锁定涉及的教学班（offering）行（B-04/P1-13，设计原文"锁定涉及的教学班"）。

    按 class_id/teacher_id 数值升序依次加锁：
    1) 班级维度：该学期该班级的全部教学班行（走 uk(term,class,course) 唯一索引）；
    2) 教师维度：该学期该教师的全部教学班行。
    并发排课必须引用已存在的教学班，因此同班/同教师同时段的两个事务
    都会锁到相同的 offering 行 → 互斥串行化；后到事务在锁内重新执行冲突
    检查（当前读）即可发现先到事务已插入的排课（防幻读）。
    所有事务按同一升序加锁，避免加锁顺序死锁。
    """
    for kind, value in sorted((("class", class_id), ("teacher", teacher_id)), key=lambda kv: kv[1]):
        qs = CampusCourseOffering.objects.filter(
            term_id=term_id,
            **({"class_field_id": value} if kind == "class" else {"teacher_id": value}),
        ).order_by("id")
        # 当前读 + 行/间隙锁：必须消费结果集才真正加锁
        list(qs.select_for_update())


# ===== 基类：审计字段 + 逻辑删除 =====

class AdminModelViewSet(viewsets.ModelViewSet):
    """管理端 ViewSet 基类：仅 admin、逻辑删除、自动填充审计字段。"""

    permission_classes = [IsAdminRole]

    def get_queryset(self):
        """返回未逻辑删除的记录集，并保证稳定排序（分页需要）。"""
        qs = super().get_queryset().filter(del_flag="0")
        if not qs.ordered:  # 分页需稳定排序，避免 UnorderedObjectListWarning
            qs = qs.order_by("id")
        return qs

    def perform_create(self, serializer):
        """创建时自动填充审计字段（create_by/create_time/update_by/update_time/del_flag）。"""
        now = timezone.now()
        uid = self.request.user.id
        serializer.save(create_by=uid, create_time=now,
                        update_by=uid, update_time=now, del_flag="0")

    def perform_update(self, serializer):
        """更新时自动填充 update_by/update_time。"""
        serializer.save(update_by=self.request.user.id, update_time=timezone.now())

    def perform_destroy(self, instance):
        """逻辑删除（5.1：删除走 del_flag，不物理删除被引用记录）。"""
        instance.del_flag = "2"
        instance.update_by = self.request.user.id
        instance.update_time = timezone.now()
        instance.save(update_fields=["del_flag", "update_by", "update_time"])


# ===== T2-1：院系 / 班级 / 课程 / 学期 =====

class DepartmentViewSet(AdminModelViewSet):
    """院系管理（T2-1，/admin/api/departments）。"""

    queryset = CampusDepartment.objects.all()
    serializer_class = DepartmentSerializer


class ClassViewSet(AdminModelViewSet):
    """班级管理（T2-1，/admin/api/classes）：指定辅导员/年级/专业/院系。"""

    queryset = CampusClass.objects.select_related("department", "counselor").all()
    serializer_class = ClassSerializer


class CourseViewSet(AdminModelViewSet):
    """课程管理（T2-1，/admin/api/courses）。"""

    queryset = CampusCourse.objects.select_related("department").all()
    serializer_class = CourseSerializer


class TermViewSet(AdminModelViewSet):
    """学期管理（T2-1，/admin/api/terms）：is_current 事务切换（5.1/P1-04）。"""

    queryset = CampusTerm.objects.all()
    serializer_class = TermSerializer

    def _set_current(self, obj) -> None:
        """置为当前学期时，先清旧学期（事务内保证任意时刻仅一个）。"""
        if obj.is_current == "1":
            CampusTerm.objects.filter(is_current="1").exclude(pk=obj.pk).update(is_current="0")

    def perform_create(self, serializer):
        """创建学期（事务内保证 is_current 唯一，5.1/P1-04）。"""
        now = timezone.now()
        uid = self.request.user.id
        with transaction.atomic():
            obj = serializer.save(create_by=uid, create_time=now,
                                  update_by=uid, update_time=now, del_flag="0")
            self._set_current(obj)

    def perform_update(self, serializer):
        """更新学期（事务内保证 is_current 唯一，5.1/P1-04）。"""
        with transaction.atomic():
            obj = serializer.save(update_by=self.request.user.id, update_time=timezone.now())
            self._set_current(obj)


# ===== T2-2：教学班 =====

class OfferingViewSet(AdminModelViewSet):
    """教学班管理（T2-2，/admin/api/offerings）：唯一约束 (term, class, course)。

    查询层先做唯一校验给出友好提示；数据库唯一索引兜底（IntegrityError → 4091）。
    """

    queryset = CampusCourseOffering.objects.select_related(
        "course", "term", "class_field", "teacher"
    ).all()
    serializer_class = OfferingSerializer


# ===== T2-3：排课（冲突校验 + FOR UPDATE）=====

class ScheduleViewSet(AdminModelViewSet):
    """排课管理（T2-3，/admin/api/schedules）：班级/教师冲突校验（4.1 P0-06）。"""

    queryset = CampusCourseSchedule.objects.select_related("offering").all()
    serializer_class = ScheduleSerializer

    def _save_with_conflict_check(self, serializer) -> CampusCourseSchedule:
        """冲突校验 + FOR UPDATE 锁定 + 写入同一事务；死锁重试（B-04/P1-13）。"""
        data = serializer.validated_data
        instance = serializer.instance

        offering = data.get("offering") or (instance.offering if instance else None)
        if offering is None:
            raise ValidationError({"offering_id": "教学班不能为空"})

        term_id = offering.term_id
        class_id = offering.class_field_id
        teacher_id = offering.teacher_id
        day = data.get("day_of_week")
        ps, pe = data.get("period_start"), data.get("period_end")
        exclude_id = instance.pk if instance else None

        for attempt in range(3):  # 死锁重试（上限 3 次，B-04）
            try:
                with transaction.atomic():
                    _lock_conflict_offering_rows(term_id, class_id, teacher_id)
                    _check_schedule_conflict(
                        term_id, class_id, teacher_id, day, ps, pe, exclude_id
                    )
                    return self._commit_serializer(serializer)
            except OperationalError as exc:
                # 1213 = deadlock found；重试
                if exc.args and exc.args[0] == 1213 and attempt < 2:
                    continue
                raise

    def _commit_serializer(self, serializer):
        """按创建/更新分别填充审计字段并落库。"""
        now = timezone.now()
        uid = self.request.user.id
        if serializer.instance is None:
            return serializer.save(create_by=uid, create_time=now,
                                   update_by=uid, update_time=now, del_flag="0")
        return serializer.save(update_by=uid, update_time=now)

    def create(self, request, *args, **kwargs):
        """创建排课：冲突校验 + 保存，返回统一响应格式。"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self._save_with_conflict_check(serializer)
        return Response(
            {"code": 0, "message": "排课保存成功", "data": serializer.data}, status=200
        )

    def update(self, request, *args, **kwargs):
        """更新排课：冲突校验（排除自身）+ 保存，返回统一响应格式。"""
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self._save_with_conflict_check(serializer)
        return Response(
            {"code": 0, "message": "排课更新成功", "data": serializer.data}, status=200
        )
