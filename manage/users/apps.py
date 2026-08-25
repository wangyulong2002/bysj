"""用户 App 配置（T0-2）：CustomUser 映射共享库 campus.sys_user（P1-8）。"""
from django.apps import AppConfig


class UsersConfig(AppConfig):
    """users App 配置：系统用户模型（sys_user）。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
