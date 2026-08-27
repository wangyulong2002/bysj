<template>
  <el-container class="layout">
    <!-- 侧边栏（青岚校园：浅色 + teal 选中） -->
    <el-aside width="220px" class="layout-aside">
      <div class="layout-logo">
        <div class="layout-logo-mark"></div>
        <span class="layout-logo-title">智慧校园</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        class="layout-menu"
      >
        <el-menu-item v-for="m in menus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="layout-header">
        <div class="layout-header-title">{{ $route.meta.title }}</div>
        <div class="layout-header-user">
          <el-dropdown @command="onUserCommand">
            <span class="layout-user">
              <el-icon><UserFilled /></el-icon>
              {{ userStore.userInfo?.username || '管理员' }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menus = [
  { path: '/dashboard', title: '数据看板', icon: 'DataAnalysis' },
  { path: '/departments', title: '院系管理', icon: 'OfficeBuilding' },
  { path: '/classes', title: '班级管理', icon: 'User' },
  { path: '/students', title: '学生管理', icon: 'UserFilled' },
  { path: '/teachers', title: '教师管理', icon: 'Avatar' },
  { path: '/courses', title: '课程管理', icon: 'Reading' },
  { path: '/terms', title: '学期管理', icon: 'Calendar' },
  { path: '/offerings', title: '教学班管理', icon: 'Collection' },
  { path: '/schedules', title: '排课管理', icon: 'Grid' },
  { path: '/scores', title: '成绩管理', icon: 'DataLine' },
  { path: '/leaves', title: '请假管理', icon: 'Document' },
  { path: '/announcements', title: '公告管理', icon: 'Bell' }
]

function onUserCommand(cmd) {
  if (cmd === 'logout') {
    ElMessageBox.confirm('确定退出登录吗？', '提示', { type: 'warning' })
      .then(() => {
        userStore.logout()
        router.push('/login')
      })
      .catch(() => {})
  }
}
</script>

<style lang="scss" scoped>
.layout {
  height: 100vh;
}

.layout-aside {
  background: $surface;
  border-right: 1px solid $line;
  display: flex;
  flex-direction: column;
}

.layout-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px 20px 16px;
}

.layout-logo-mark {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, $brand, $brand-deep);
}

.layout-logo-title {
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}

.layout-menu {
  flex: 1;
  border-right: none;
  padding: 0 8px;

  .el-menu-item {
    border-radius: $radius-ctrl;
    margin-bottom: 4px;
    height: 44px;

    &.is-active {
      background: $brand-soft;
      color: $brand-deep;
      font-weight: 600;
    }
  }
}

.layout-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: $surface;
  border-bottom: 1px solid $line;
  height: 56px;
  padding: 0 24px;
}

.layout-header-title {
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}

.layout-user {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  color: $ink-2;
  font-size: $fs-14;
}

.layout-main {
  background: $bg;
  padding: 20px;
  overflow-y: auto;
}
</style>
