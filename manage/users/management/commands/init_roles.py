"""T1-1 四角色 + 演示账号初始化管理命令。

创建 student / teacher / counselor / admin 四个角色的演示账号（幂等）：
- admin      / admin123456（管理员，Django Admin 可用，P1-10：admin 仅管理端）
- student    / 123456（学生）
- teacher    / 123456（教师）
- counselor  / 123456（辅导员）

用法：
  cd bysj/manage && ../server/venv_wsl/bin/python manage.py init_roles
"""
from django.core.management.base import BaseCommand

from users.models import CustomUser

DEMO_USERS = [
    {"username": "admin", "password": "admin123456", "nick_name": "系统管理员",
     "role_code": "admin", "is_superuser": True},
    {"username": "student01", "password": "123456", "nick_name": "演示学生",
     "role_code": "student", "is_superuser": False},
    {"username": "teacher01", "password": "123456", "nick_name": "演示教师",
     "role_code": "teacher", "is_superuser": False},
    {"username": "counselor01", "password": "123456", "nick_name": "演示辅导员",
     "role_code": "counselor", "is_superuser": False},
]


class Command(BaseCommand):
    help = "初始化四角色演示账号（幂等：已存在则跳过/重置密码）"

    def handle(self, *args, **options):
        """执行命令：按 DEMO_USERS 创建/更新四角色演示账号（幂等）。"""
        created, updated = 0, 0
        for u in DEMO_USERS:
            username = u.pop("username")
            password = u.pop("password")
            user, is_new = CustomUser.objects.get_or_create(username=username, defaults=u)
            if not is_new:
                for k, v in u.items():
                    setattr(user, k, v)
                updated += 1
            user.set_password(password)
            user.save()
            self.stdout.write(f"  {'创建' if is_new else '更新'} {username} (role={u['role_code']})")
            created += 1 if is_new else 0
        self.stdout.write(self.style.SUCCESS(
            f"完成：创建 {created}，更新 {updated}（共 {len(DEMO_USERS)} 个演示账号）"
        ))
