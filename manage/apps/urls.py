"""管理端业务接口路由（T2-1/T2-2/T2-3/T3-1，6.4）。

统一前缀 /admin/api/，由 config/urls.py include。
- departments  → 院系管理
- classes      → 班级管理
- courses      → 课程管理
- terms        → 学期管理（is_current 切换）
- offerings    → 教学班管理（唯一约束）
- schedules    → 排课管理（冲突校验）
- announcements → 公告管理（发布/下架，唯一发布方，T3-1）
"""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AnnouncementViewSet,
    ClassOptionsView,
    ClassViewSet,
    CourseViewSet,
    DepartmentViewSet,
    LeaveViewSet,
    OfferingViewSet,
    ScheduleViewSet,
    ScoreAuditViewSet,
    ScoreViewSet,
    StudentViewSet,
    TeacherViewSet,
    TermViewSet,
    UserOptionsView,
)

router = SimpleRouter(trailing_slash=False)
router.register("departments", DepartmentViewSet, basename="department")
router.register("classes", ClassViewSet, basename="class")
router.register("courses", CourseViewSet, basename="course")
router.register("terms", TermViewSet, basename="term")
router.register("offerings", OfferingViewSet, basename="offering")
router.register("schedules", ScheduleViewSet, basename="schedule")
router.register("announcements", AnnouncementViewSet, basename="announcement")
router.register("students", StudentViewSet, basename="student")
router.register("teachers", TeacherViewSet, basename="teacher")
router.register("scores", ScoreViewSet, basename="score")
router.register("score-audits", ScoreAuditViewSet, basename="score-audit")
router.register("leaves", LeaveViewSet, basename="leave")

# 非 ViewSet 路由（下拉选项，供自建管理前端表单使用）
urlpatterns = [
    path("users/options", UserOptionsView.as_view(), name="user-options"),
    path("classes/options", ClassOptionsView.as_view(), name="class-options"),
] + router.urls
