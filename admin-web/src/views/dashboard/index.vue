<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">数据看板</div>
        <div class="page-desc">智慧校园信息管理系统 · 管理端总览</div>
      </div>
    </div>

    <!-- 数据卡片（统计 API 实时数据） -->
    <div class="stat-grid">
      <div v-for="s in stats" :key="s.label" class="card-shell">
        <div class="card-core stat-card">
          <div class="stat-icon" :style="{ background: s.bg, color: s.color }">
            <el-icon :size="22"><component :is="s.icon" /></el-icon>
          </div>
          <div>
            <div class="stat-value">{{ s.value }}</div>
            <div class="stat-label">{{ s.label }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 快速入口 -->
    <div class="card-shell">
      <div class="card-core">
        <div class="quick-title">快捷入口</div>
        <div class="quick-grid">
          <div
            v-for="m in quickMenus"
            :key="m.path"
            class="quick-item"
            @click="$router.push(m.path)"
          >
            <el-icon :size="22"><component :is="m.icon" /></el-icon>
            <span>{{ m.title }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { departmentApi, classApi, courseApi, termApi, announcementApi } from '../../api/modules'

const stats = ref([
  { label: '院系', value: '-', icon: 'OfficeBuilding', bg: '#E0F2FE', color: '#0E7490' },
  { label: '班级', value: '-', icon: 'User', bg: '#FEF3C7', color: '#D97706' },
  { label: '课程', value: '-', icon: 'Reading', bg: '#DCFCE7', color: '#16A34A' },
  { label: '学期', value: '-', icon: 'Calendar', bg: '#EDE9FE', color: '#7C3AED' },
  { label: '公告', value: '-', icon: 'Bell', bg: '#FEE2E2', color: '#DC2626' }
])

const quickMenus = [
  { path: '/departments', title: '院系管理', icon: 'OfficeBuilding' },
  { path: '/classes', title: '班级管理', icon: 'User' },
  { path: '/courses', title: '课程管理', icon: 'Reading' },
  { path: '/terms', title: '学期管理', icon: 'Calendar' },
  { path: '/offerings', title: '教学班管理', icon: 'Collection' },
  { path: '/schedules', title: '排课管理', icon: 'Grid' },
  { path: '/announcements', title: '公告管理', icon: 'Bell' }
]

function setValue(label, count) {
  const s = stats.value.find((x) => x.label === label)
  if (s) s.value = count ?? '-'
}

onMounted(async () => {
  try {
    const [depts, classes, courses, terms, anns] = await Promise.all([
      departmentApi.list({ page_size: 1 }),
      classApi.list({ page_size: 1 }),
      courseApi.list({ page_size: 1 }),
      termApi.list({ page_size: 50 }),
      announcementApi.list({ page_size: 1 })
    ])
    setValue('院系', depts?.count)
    setValue('班级', classes?.count)
    setValue('课程', courses?.count)
    setValue('学期', terms?.count)
    setValue('公告', anns?.count)
  } catch (e) {
    // 看板加载失败不阻塞（request 已 toast）
  }
})
</script>

<style lang="scss" scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: $radius-ctrl;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-value {
  font-size: $fs-24;
  font-weight: 600;
  color: $ink;
  line-height: 1.2;
}

.stat-label {
  font-size: $fs-13;
  color: $ink-2;
}

.quick-title {
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
  margin-bottom: 16px;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 18px 8px;
  background: $bg;
  border: 1px solid $line;
  border-radius: $radius-ctrl;
  color: $brand-deep;
  font-size: $fs-13;
  cursor: pointer;
  transition: transform 0.2s $ease-premium, box-shadow 0.2s $ease-premium;

  &:hover {
    transform: translateY(-2px);
    box-shadow: $shadow-soft;
  }
}
</style>
