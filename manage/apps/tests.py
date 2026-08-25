"""管理端测试（T2-1/T2-2/T2-3）。

覆盖验收要点（13.6/13.7）：
- 院系/班级/课程/学期 CRUD + 编码唯一；
- 班级指定辅导员/年级/专业/院系；
- 学期 is_current 事务切换（任意时刻仅一个）；
- 教学班唯一约束 (term, class, course) 冲突 → 4091；
- 排课班级冲突/教师冲突拒绝保存（4091）、无冲突通过；
- 非 admin 角色访问 /admin/api/** → 4031。
"""
import threading

from django.contrib.auth import get_user_model

from rest_framework.test import APIClient, APITestCase
from django.test import TransactionTestCase

from .models import (
    CampusClass,
    CampusCourse,
    CampusCourseOffering,
    CampusCourseSchedule,
    CampusDepartment,
    CampusTerm,
)

User = get_user_model()


class AdminBaseTestCase(APITestCase):
    """构造管理端测试环境：admin 用户 + 基础数据。"""

    def setUp(self):
        """构造测试环境：创建 admin/teacher/counselor 用户及院系/班级/课程/学期基础数据。"""
        self.admin = User.objects.create_user(
            username="admin_t2", password="pass1234", nick_name="管理员",
            role_code="admin", is_superuser=True, create_time=None,
        )
        self.teacher = User.objects.create_user(
            username="teacher_t2", password="pass1234", nick_name="张老师",
            role_code="teacher",
        )
        self.counselor = User.objects.create_user(
            username="counselor_t2", password="pass1234", nick_name="李导员",
            role_code="counselor",
        )

        self.dept = CampusDepartment.objects.create(
            dept_name="计算机学院", dept_code="CS", del_flag="0"
        )
        self.cls = CampusClass.objects.create(
            class_name="计科2301", class_code="CS2301", grade="2023",
            major="计算机科学与技术", department=self.dept, counselor=self.counselor,
            del_flag="0",
        )
        self.course = CampusCourse.objects.create(
            course_name="高等数学", course_code="MATH101",
            credit="4.0", hours=64, department=self.dept, del_flag="0",
        )
        self.term = CampusTerm.objects.create(
            term_name="2025-2026学年第一学期", start_date="2025-09-01",
            end_date="2026-01-18", total_weeks=20, is_current="1", del_flag="0",
        )
        self.client.force_authenticate(user=self.admin)


class DepartmentTermTestCase(AdminBaseTestCase):
    """T2-1：院系/学期 CRUD + 编码唯一 + is_current 切换。"""

    def test_department_create_and_list(self):
        """院系创建与列表查询成功。"""
        resp = self.client.post("/admin/api/departments", {"dept_name": "外国语学院", "dept_code": "FL"}, format="json")
        self.assertIn(resp.status_code, (200, 201))
        self.assertEqual(resp.json()["code"], 0)
        resp = self.client.get("/admin/api/departments")
        self.assertEqual(resp.json()["code"], 0)
        body = resp.json()["data"]
        results = body.get("results", body)  # DRF 分页时 results 为列表
        names = [d["dept_name"] for d in results]
        self.assertIn("外国语学院", names)

    def test_department_code_unique(self):
        """院系编码重复 → 4091 冲突。"""
        resp = self.client.post("/admin/api/departments", {"dept_name": "重复院系", "dept_code": "CS"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["code"], 4091)

    def test_class_with_counselor_grade_major(self):
        """班级创建携带辅导员/年级/专业/院系，返回关联展示名。"""
        resp = self.client.post(
            "/admin/api/classes",
            {"class_name": "软工2302", "class_code": "SE2302", "grade": "2023",
             "major": "软件工程", "department_id": self.dept.pk, "counselor_id": self.counselor.pk},
            format="json",
        )
        self.assertEqual(resp.json()["code"], 0)
        data = resp.json()["data"]
        self.assertEqual(data["department_id"], self.dept.pk)
        self.assertEqual(data["counselor_id"], self.counselor.pk)
        self.assertEqual(data["department_name"], "计算机学院")
        self.assertEqual(data["counselor_name"], "李导员")

    def test_class_code_unique(self):
        """班级编码重复 → 4091 冲突。"""
        resp = self.client.post(
            "/admin/api/classes",
            {"class_name": "重复班级", "class_code": "CS2301", "grade": "2023"}, format="json",
        )
        self.assertEqual(resp.json()["code"], 4091)

    def test_term_is_current_switch_only_one(self):
        """新建当前学期时旧学期自动置 0，任意时刻仅一个 is_current=1。"""
        resp = self.client.post(
            "/admin/api/terms",
            {"term_name": "2025-2026学年第二学期", "start_date": "2026-02-23",
             "end_date": "2026-07-05", "total_weeks": 19, "is_current": "1"},
            format="json",
        )
        self.assertEqual(resp.json()["code"], 0)
        # 任意时刻仅一个 is_current=1
        count = CampusTerm.objects.filter(is_current="1").count()
        self.assertEqual(count, 1)
        self.assertEqual(CampusTerm.objects.filter(is_current="1").first().term_name,
                         "2025-2026学年第二学期")

    def test_term_update_is_current(self):
        """更新学期为当前学期后同样触发 is_current 唯一切换。"""
        term2 = CampusTerm.objects.create(
            term_name="2025-2026学年第二学期", start_date="2026-02-23",
            end_date="2026-07-05", total_weeks=19, is_current="0", del_flag="0",
        )
        resp = self.client.put(
            f"/admin/api/terms/{term2.pk}",
            {"term_name": term2.term_name, "start_date": "2026-02-23",
             "end_date": "2026-07-05", "total_weeks": 19, "is_current": "1"},
            format="json",
        )
        self.assertEqual(resp.json()["code"], 0)
        self.assertEqual(CampusTerm.objects.filter(is_current="1").count(), 1)
        self.assertEqual(CampusTerm.objects.get(pk=term2.pk).is_current, "1")


class OfferingTestCase(AdminBaseTestCase):
    """T2-2：教学班 CRUD + 唯一约束 (term, class, course)。"""

    def _create_offering(self):
        """构造教学班（课程+学期+班级+教师）。"""
        return CampusCourseOffering.objects.create(
            course=self.course, term=self.term, class_field=self.cls,
            teacher=self.teacher, del_flag="0",
        )

    def test_offering_create_with_names(self):
        """教学班创建成功并返回关联名称（课程/学期/班级/教师）。"""
        resp = self.client.post(
            "/admin/api/offerings",
            {"course_id": self.course.pk, "term_id": self.term.pk,
             "class_id": self.cls.pk, "teacher_id": self.teacher.pk},
            format="json",
        )
        self.assertEqual(resp.json()["code"], 0)
        data = resp.json()["data"]
        self.assertEqual(data["course_name"], "高等数学")
        self.assertEqual(data["term_name"], "2025-2026学年第一学期")
        self.assertEqual(data["class_name"], "计科2301")
        self.assertEqual(data["teacher_name"], "张老师")

    def test_offering_unique_constraint(self):
        """教学班 (term, class, course) 组合重复 → 4091 冲突。"""
        self._create_offering()
        resp = self.client.post(
            "/admin/api/offerings",
            {"course_id": self.course.pk, "term_id": self.term.pk,
             "class_id": self.cls.pk, "teacher_id": self.teacher.pk},
            format="json",
        )
        self.assertEqual(resp.json()["code"], 4091)

    def test_offering_requires_all_fields(self):
        """教学班缺必填字段 → 4001 参数错误。"""
        resp = self.client.post(
            "/admin/api/offerings", {"course_id": self.course.pk}, format="json",
        )
        self.assertEqual(resp.json()["code"], 4001)


class ScheduleConflictTestCase(AdminBaseTestCase):
    """T2-3：排课冲突校验（班级冲突/教师冲突/无冲突通过）。"""

    def setUp(self):
        """构造排课测试环境：两个同班同教师的教学班。"""
        super().setUp()
        self.offering = CampusCourseOffering.objects.create(
            course=self.course, term=self.term, class_field=self.cls,
            teacher=self.teacher, del_flag="0",
        )
        self.course2 = CampusCourse.objects.create(
            course_name="大学英语", course_code="ENG102",
            credit="2.0", hours=32, department=self.dept, del_flag="0",
        )
        self.offering2 = CampusCourseOffering.objects.create(
            course=self.course2, term=self.term, class_field=self.cls,
            teacher=self.teacher, del_flag="0",
        )

    def _post_schedule(self, offering, **overrides):
        """向 /admin/api/schedules 发起排课创建请求（可覆盖默认字段）。"""
        payload = {
            "offering_id": offering.pk,
            "week_start": 1,
            "week_end": 16,
            "day_of_week": 1,
            "period_start": 1,
            "period_end": 2,
            "location": "A-301",
        }
        payload.update(overrides)
        return self.client.post("/admin/api/schedules", payload, format="json")

    def test_schedule_create_ok(self):
        """无冲突排课创建成功。"""
        resp = self._post_schedule(self.offering)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["code"], 0)
        self.assertEqual(CampusCourseSchedule.objects.count(), 1)

    def test_class_conflict_rejected(self):
        """同班级同一天时间重叠 → 班级冲突 4091。"""
        self._post_schedule(self.offering)
        # 同班级 + 同一天 + 时间重叠 → 班级冲突
        resp = self._post_schedule(self.offering2)
        self.assertEqual(resp.json()["code"], 4091)
        self.assertIn("班级冲突", resp.json()["message"])

    def test_teacher_conflict_rejected(self):
        """另一班级 + 同教师 + 同一天时间重叠 → 教师冲突 4091。"""
        # 另一个班级 + 同教师 + 同一天 + 时间重叠 → 教师冲突
        cls2 = CampusClass.objects.create(
            class_name="计科2302", class_code="CS2302", grade="2023",
            major="计算机科学与技术", department=self.dept, counselor=self.counselor,
            del_flag="0",
        )
        offering3 = CampusCourseOffering.objects.create(
            course=self.course, term=self.term, class_field=cls2,
            teacher=self.teacher, del_flag="0",
        )
        self._post_schedule(self.offering)
        resp = self._post_schedule(offering3)
        self.assertEqual(resp.json()["code"], 4091)
        self.assertIn("教师冲突", resp.json()["message"])

    def test_non_overlap_period_allowed(self):
        """同班同教师但节次不重叠 → 允许创建。"""
        self._post_schedule(self.offering)
        # 同班级同教师，但节次不重叠 → 允许
        resp = self._post_schedule(self.offering2, period_start=3, period_end=4)
        self.assertEqual(resp.json()["code"], 0)
        self.assertEqual(CampusCourseSchedule.objects.count(), 2)

    def test_different_day_allowed(self):
        """同班同教师但星期不同 → 允许创建。"""
        self._post_schedule(self.offering)
        resp = self._post_schedule(self.offering2, day_of_week=2)
        self.assertEqual(resp.json()["code"], 0)

    def test_schedule_update_conflict(self):
        """更新排课为与已有记录重叠的节次 → 4091 冲突。"""
        CampusCourseSchedule.objects.create(
            offering=self.offering, week_start=1, week_end=16, day_of_week=1,
            period_start=1, period_end=2, location="A-301", del_flag="0",
        )
        other = CampusCourseSchedule.objects.create(
            offering=self.offering2, week_start=1, week_end=16, day_of_week=1,
            period_start=3, period_end=4, location="A-302", del_flag="0",
        )
        # 把 other 改成与同班级同教师 A 重叠的节次 → 拒绝
        resp = self.client.put(
            f"/admin/api/schedules/{other.pk}",
            {"offering_id": self.offering2.pk, "week_start": 1, "week_end": 16,
             "day_of_week": 1, "period_start": 1, "period_end": 2, "location": "B-201"},
            format="json",
        )
        self.assertEqual(resp.json()["code"], 4091)


class AdminPermissionTestCase(AdminBaseTestCase):
    """T2-1 配置：非 admin 角色访问 /admin/api/** → 4031。"""

    def test_non_admin_denied(self):
        """非 admin 角色访问 /admin/api/** → 4031。"""
        self.client.force_authenticate(user=self.counselor)
        resp = self.client.get("/admin/api/departments")
        self.assertEqual(resp.json()["code"], 4031)
        resp = self.client.get("/admin/api/schedules")
        self.assertEqual(resp.json()["code"], 4031)


class ScheduleConcurrentTestCase(TransactionTestCase):
    """T2-3 并发（B-04/P1-13，验收标准 17）：并发保存重叠时段仅一方成功。

    使用 TransactionTestCase（真实提交事务），两线程同时 POST 同班级/同教师
    同一天重叠节次的排课，验证 FOR UPDATE 锁 + 冲突校验在并发下仍生效。
    """

    def setUp(self):
        """构造并发测试环境：两个同班同教师的教学班。"""
        self.admin = User.objects.create_user(
            username="admin_t2c", password="pass1234", nick_name="管理员",
            role_code="admin", is_superuser=True,
        )
        self.teacher = User.objects.create_user(
            username="teacher_t2c", password="pass1234", nick_name="张老师",
            role_code="teacher",
        )
        self.dept = CampusDepartment.objects.create(dept_name="计算机学院", dept_code="CSC", del_flag="0")
        self.cls = CampusClass.objects.create(
            class_name="计科2301", class_code="CS2301C", grade="2023",
            major="计算机科学与技术", department=self.dept, del_flag="0",
        )
        self.term = CampusTerm.objects.create(
            term_name="2025-2026学年第一学期", start_date="2025-09-01",
            end_date="2026-01-18", total_weeks=20, is_current="1", del_flag="0",
        )
        self.course1 = CampusCourse.objects.create(
            course_name="高等数学", course_code="MATH101C",
            credit="4.0", hours=64, department=self.dept, del_flag="0",
        )
        self.course2 = CampusCourse.objects.create(
            course_name="大学英语", course_code="ENG102C",
            credit="2.0", hours=32, department=self.dept, del_flag="0",
        )
        self.offering1 = CampusCourseOffering.objects.create(
            course=self.course1, term=self.term, class_field=self.cls,
            teacher=self.teacher, del_flag="0",
        )
        self.offering2 = CampusCourseOffering.objects.create(
            course=self.course2, term=self.term, class_field=self.cls,
            teacher=self.teacher, del_flag="0",
        )

    def test_concurrent_overlap_only_one_succeeds(self):
        """两线程并发提交重叠排课：FOR UPDATE 锁下仅一方成功、另一方 4091。"""
        results = {}
        barrier = threading.Barrier(2)

        def _post(offering_id, key):
            """线程内发起排课请求，记录响应 code。"""
            client = APIClient()
            client.force_authenticate(user=self.admin)
            barrier.wait()  # 尽量同时发起
            resp = client.post(
                "/admin/api/schedules",
                {"offering_id": offering_id, "week_start": 1, "week_end": 16,
                 "day_of_week": 1, "period_start": 1, "period_end": 2, "location": "A-301"},
                format="json",
            )
            results[key] = resp.json()["code"]

        threads = [
            threading.Thread(target=_post, args=(self.offering1.pk, "a")),
            threading.Thread(target=_post, args=(self.offering2.pk, "b")),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sorted(results.values()), [0, 4091], f"并发结果应为一方成功一方冲突，实际 {results}")
        self.assertEqual(CampusCourseSchedule.objects.count(), 1)
