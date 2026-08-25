"""管理端业务 App 配置（T2-1/T2-2/T2-3）。"""
from django.apps import AppConfig


class AppsConfig(AppConfig):
    """apps App 配置：管理端业务模型（院系/班级/课程/学期/教学班/排课等）。"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps'
