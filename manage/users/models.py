"""CustomUser（P1-8）：映射共享库 campus.sys_user。

设计依据：v2.2 3.4（P1-8）/ 5.2
- `db_table='sys_user'`，与 FastAPI 只读模型共享同一张表。
- 首次迁移前必须定义本模型并写死 AUTH_USER_MODEL（settings 已配置）。
- 密码哈希：Django 默认 PBKDF2（必要时切 BCrypt），FastAPI 侧可校验同一格式。
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class CustomUserManager(BaseUserManager):
    """CustomUser 管理器：提供 create_user / get_by_natural_key 等。"""

    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError("username 必填")
        user = self.model(username=username, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", "0")
        extra_fields.setdefault("role_code", "admin")
        return self.create_user(username, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """系统用户（sys_user），管理端唯一写入方，FastAPI 只读引用。"""

    # 登录账号与密码（AbstractBaseUser 已含 password；username 自定义）
    username = models.CharField(max_length=30, unique=True, verbose_name="登录账号")
    nick_name = models.CharField(max_length=30, blank=True, null=True, verbose_name="姓名")
    gender = models.CharField(max_length=1, blank=True, null=True, verbose_name="性别（0未知 1男 2女）")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="手机号（展示脱敏，B-09/P1-17）")
    email = models.EmailField(max_length=50, blank=True, null=True, verbose_name="邮箱")
    avatar = models.CharField(max_length=255, blank=True, null=True, verbose_name="头像（campus_file 签名 URL）")
    status = models.CharField(max_length=1, default="0", verbose_name="账号状态：0正常 1停用")

    # 扩展字段（设计 5.2）
    student_no = models.CharField(max_length=20, blank=True, null=True, db_index=True, verbose_name="学号（展示冗余）")
    teacher_no = models.CharField(max_length=20, blank=True, null=True, db_index=True, verbose_name="工号（展示冗余）")
    wechat_openid = models.CharField(max_length=64, blank=True, null=True, unique=True, verbose_name="微信 openid")
    role_code = models.CharField(max_length=20, blank=True, null=True, db_index=True,
                                 verbose_name="角色标识（student/teacher/counselor/admin）")
    password_version = models.IntegerField(default=0, verbose_name="密码版本号（改密自增）")

    # 审计字段（5.1）
    create_by = models.BigIntegerField(blank=True, null=True, verbose_name="创建人")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_by = models.BigIntegerField(blank=True, null=True, verbose_name="更新人")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    del_flag = models.CharField(max_length=1, default="0", verbose_name="逻辑删除：0正常 2删除")

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []

    objects = CustomUserManager()

    class Meta:
        db_table = "sys_user"
        verbose_name = "系统用户"
        verbose_name_plural = verbose_name
        ordering = ["id"]

    def __str__(self) -> str:  # pragma: no cover
        return self.username

    @property
    def is_active(self) -> bool:
        """Django 需要 is_active；与 status='0'（正常）对齐。"""
        return self.status == "0"

    @property
    def is_staff(self) -> bool:
        """Admin 访问判定：超级用户或 admin 角色。"""
        return self.is_superuser or self.role_code == "admin"
