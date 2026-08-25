<template>
  <view class="tt-page">
    <!-- 学期信息 + 周次切换 -->
    <view class="card-shell tt-head">
      <view class="card-core">
        <view class="head-top">
          <text class="term-name">{{ termName || '当前学期' }}</text>
          <text class="week-status" :class="weekStatusClass">{{ weekStatusText }}</text>
        </view>
        <view class="week-switch">
          <view class="arrow-btn" :class="{ disabled: currentWeek <= 1 }" @tap="prevWeek">
            <text class="arrow">‹</text>
          </view>
          <view class="week-info">
            <text class="week-label">第 {{ currentWeek }} 周</text>
            <text class="week-total">共 {{ totalWeeks }} 周</text>
          </view>
          <view class="arrow-btn" :class="{ disabled: currentWeek >= totalWeeks }" @tap="nextWeek">
            <text class="arrow">›</text>
          </view>
        </view>
        <picker v-if="classes.length > 1" :range="classNames" @change="onClassChange">
          <view class="picker-box">
            <text class="picker-name">{{ currentClassName }}</text>
            <text class="picker-arrow">⌄</text>
          </view>
        </picker>
      </view>
    </view>

    <!-- 周视图网格：周一~周日 × 第 1~12 节 -->
    <view class="card-shell tt-grid">
      <view class="card-core grid-core">
        <view class="day-header">
          <view class="corner"></view>
          <view
            v-for="d in days"
            :key="d.value"
            class="day-cell"
            :class="{ today: d.value === todayWeek }"
          >
            <text class="day-name" :class="{ 'today-text': d.value === todayWeek }">{{ d.name }}</text>
            <view v-if="d.value === todayWeek" class="today-dot"></view>
          </view>
        </view>
        <view class="grid-body">
          <view class="period-col">
            <view v-for="p in periods" :key="p" class="period-cell">
              <text class="period-num">{{ p }}</text>
            </view>
          </view>
          <view class="days-body">
            <view
              v-for="d in days"
              :key="d.value"
              class="day-col"
              :class="{ 'col-today': d.value === todayWeek }"
            >
              <view
                v-for="c in itemsOfDay(d.value)"
                :key="c.key"
                class="lesson"
                :class="{ 'lesson-today': d.value === todayWeek }"
                :style="lessonStyle(c)"
              >
                <text class="lesson-course">{{ c.course_name }}</text>
                <text class="lesson-teacher">{{ c.teacher_name }}</text>
                <text class="lesson-loc">{{ c.location }}</text>
              </view>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 空态 / 加载态 -->
    <view v-if="loaded && !items.length" class="empty">
      <text class="empty-title">本周暂无课程</text>
      <text class="empty-sub">换个教学周看看，或联系教务确认排课</text>
    </view>
    <view v-if="!loaded" class="empty">
      <text class="empty-sub">课表加载中...</text>
    </view>
  </view>
</template>

<script>
import { get } from '../../utils/request'

const DAYS = [
  { value: 1, name: '一' },
  { value: 2, name: '二' },
  { value: 3, name: '三' },
  { value: 4, name: '四' },
  { value: 5, name: '五' },
  { value: 6, name: '六' },
  { value: 7, name: '日' }
]
const ROW_H = 96 // 每节高度（rpx）
const MAX_PERIOD = 12 // 第 1~12 节

export default {
  data() {
    return {
      days: DAYS,
      periods: Array.from({ length: MAX_PERIOD }, (_, i) => i + 1),
      todayWeek: this.calcTodayWeek(),
      termName: '',
      totalWeeks: 20,
      currentWeek: 1,
      weekStatus: 'ongoing',
      classes: [],
      currentClassId: null,
      currentClassName: '',
      items: [],
      loaded: false
    }
  },
  computed: {
    classNames() {
      return this.classes.map((c) => c.class_name)
    },
    weekStatusText() {
      return { before_start: '未开学', ongoing: '进行中', after_end: '已结束' }[this.weekStatus] || ''
    },
    weekStatusClass() {
      return {
        before_start: 'st-before',
        ongoing: 'st-ongoing',
        after_end: 'st-after'
      }[this.weekStatus] || ''
    }
  },
  onShow() {
    // 页面展示时加载全部数据
    this.loadAll()
  },
  methods: {
    calcTodayWeek() {
      // 计算今天是周几（周一=1 ... 周日=7）
      return ((new Date().getDay() + 6) % 7) + 1
    },
    toast(title) {
      // 轻提示（不阻塞图标）
      uni.showToast({ title, icon: 'none' })
    },
    async loadAll() {
      // 并行加载当前周信息 + 我的班级，随后加载课表
      this.loaded = false
      try {
        const [week, classes] = await Promise.all([
          get('/api/timetable/current-week'),
          get('/api/classes/mine')
        ])
        this.termName = week.term_name || ''
        this.totalWeeks = week.total_weeks || 20
        this.weekStatus = week.semester_status || 'ongoing'
        this.currentWeek = Math.max(1, Math.min(week.current_week || 1, this.totalWeeks))
        this.classes = classes || []
        if (this.classes.length) {
          this.currentClassId = this.classes[0].class_id
          this.currentClassName = this.classes[0].class_name
        }
        await this.loadTimetable()
      } catch (err) {
        this.toast(err.message || '课表加载失败')
      } finally {
        this.loaded = true
      }
    },
    async loadTimetable() {
      // 按班级 + 周次请求课表数据，并为每条记录生成唯一 key
      if (!this.currentClassId) {
        this.items = []
        return
      }
      try {
        const data = await get('/api/timetable', {
          class_id: this.currentClassId,
          week: this.currentWeek
        })
        this.items = (data.items || []).map((c, idx) => ({
          ...c,
          key: `${c.day_of_week}-${c.period_start}-${idx}`
        }))
      } catch (err) {
        this.toast(err.message || '课表加载失败')
      }
    },
    itemsOfDay(day) {
      // 筛出某一天的课程
      return this.items.filter((c) => c.day_of_week === day)
    },
    lessonStyle(c) {
      // 依据节次计算课程块在网格中的定位（top/height）
      const top = (c.period_start - 1) * ROW_H
      const height = (c.period_end - c.period_start + 1) * ROW_H - 6
      return {
        top: `${top}rpx`,
        height: `${height}rpx`
      }
    },
    prevWeek() {
      // 上一周（不早于第 1 周）
      if (this.currentWeek <= 1) return
      this.currentWeek -= 1
      this.loadTimetable()
    },
    nextWeek() {
      // 下一周（不晚于总周数）
      if (this.currentWeek >= this.totalWeeks) return
      this.currentWeek += 1
      this.loadTimetable()
    },
    onClassChange(e) {
      // 切换班级后重新加载课表
      const idx = Number(e.detail.value)
      const cls = this.classes[idx]
      if (cls) {
        this.currentClassId = cls.class_id
        this.currentClassName = cls.class_name
        this.loadTimetable()
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.tt-page {
  min-height: 100vh;
  padding: 32rpx;
  background: $bg;
}

/* ===== 双边框卡片（青岚校园 7.3）===== */
.card-shell {
  background: rgba(255, 255, 255, 0.6);
  border: 2rpx solid $line;
  border-radius: $radius-card;
  padding: 12rpx;
  box-shadow: $shadow-soft;
  margin-bottom: 32rpx;
}
.card-core {
  background: $surface;
  border-radius: calc(#{$radius-card} - 12rpx);
  box-shadow: inset 0 2rpx 0 rgba(255, 255, 255, 0.6);
  padding: 28rpx;
}

/* ===== 头部 ===== */
.head-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 4rpx 4rpx 24rpx;
}
.term-name {
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.week-status {
  font-size: $fs-12;
  padding: 4rpx 16rpx;
  border-radius: $radius-pill;
}
.st-ongoing {
  color: $brand-deep;
  background: $brand-soft;
}
.st-before,
.st-after {
  color: $ink-2;
  background: $bg;
}

.week-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  padding: 12rpx;
}
.arrow-btn {
  width: 72rpx;
  height: 72rpx;
  border-radius: $radius-ctrl;
  background: $surface;
  border: 2rpx solid $line;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.25s $ease-premium, opacity 0.25s $ease-premium;
  &:active {
    transform: scale(0.94);
  }
  &.disabled {
    opacity: 0.35;
    pointer-events: none;
  }
}
.arrow {
  font-size: $fs-20;
  color: $brand-deep;
  line-height: 1;
}
.week-info {
  text-align: center;
  flex: 1;
}
.week-label {
  display: block;
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.week-total {
  display: block;
  margin-top: 4rpx;
  font-size: $fs-12;
  color: $ink-2;
}

.picker-box {
  margin-top: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8rpx;
  padding: 16rpx 0;
}
.picker-name {
  font-size: $fs-14;
  color: $brand-deep;
}
.picker-arrow {
  font-size: $fs-12;
  color: $ink-2;
}

/* ===== 周视图网格 ===== */
.grid-core {
  padding: 20rpx 16rpx 24rpx;
}
.day-header {
  display: flex;
  align-items: center;
  padding-bottom: 16rpx;
}
.corner {
  width: 64rpx;
  flex-shrink: 0;
}
.day-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6rpx;
  padding: 8rpx 0;
  border-radius: $radius-ctrl;
  &.today {
    background: $brand-soft;
  }
}
.day-name {
  font-size: $fs-12;
  color: $ink-2;
  &.today-text {
    color: $brand-deep;
    font-weight: 600;
  }
}
.today-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: $radius-pill;
  background: $brand;
}

.grid-body {
  display: flex;
}
.period-col {
  width: 64rpx;
  flex-shrink: 0;
}
.period-cell {
  height: 96rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.period-num {
  font-size: $fs-12;
  color: $ink-2;
}
.days-body {
  flex: 1;
  display: flex;
  gap: 6rpx;
}
.day-col {
  flex: 1;
  position: relative;
  height: 1152rpx; /* 12 × 96rpx */
  background: $bg;
  border: 2rpx solid $line;
  border-radius: 16rpx;
  overflow: hidden;
}
.col-today {
  border-color: $brand;
  background: rgba(224, 242, 254, 0.25);
}
.lesson {
  position: absolute;
  left: 6rpx;
  right: 6rpx;
  padding: 12rpx 10rpx;
  background: $brand-soft;
  border: 2rpx solid rgba(14, 116, 144, 0.28);
  border-radius: 14rpx;
  box-shadow: inset 0 2rpx 0 rgba(255, 255, 255, 0.5);
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  overflow: hidden;
}
.lesson-today {
  border-color: $brand;
  box-shadow: inset 0 2rpx 0 rgba(255, 255, 255, 0.6), 0 4rpx 12rpx rgba(14, 116, 144, 0.16);
}
.lesson-course {
  font-size: $fs-12;
  font-weight: 600;
  color: $brand-deep;
  line-height: 1.35;
}
.lesson-teacher,
.lesson-loc {
  margin-top: 4rpx;
  font-size: 20rpx;
  color: $ink-2;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ===== 空态 ===== */
.empty {
  padding: 96rpx 32rpx;
  text-align: center;
}
.empty-title {
  display: block;
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.empty-sub {
  display: block;
  margin-top: 12rpx;
  font-size: $fs-12;
  color: $ink-2;
}
</style>
