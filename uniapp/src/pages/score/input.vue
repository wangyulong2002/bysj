<template>
  <view class="input-page">
    <!-- 教学班选择 -->
    <view class="card-shell">
      <view class="card-core">
        <picker :range="offeringLabels" @change="onOfferingChange">
          <view class="offering-picker">
            <text class="offering-label">{{ currentLabel || '选择教学班' }}</text>
            <text class="offering-arrow">›</text>
          </view>
        </picker>
      </view>
    </view>

    <!-- 学生成绩录入表 -->
    <view v-if="students.length" class="card-shell">
      <view class="card-core">
        <view v-for="s in students" :key="s.student_id" class="stu-row">
          <view class="stu-info">
            <text class="stu-name">{{ s.student_name }}</text>
            <text class="stu-no">{{ s.student_no }}</text>
          </view>
          <view class="stu-inputs">
            <view class="stu-field">
              <text class="stu-field-label">平时</text>
              <input
                class="stu-input"
                style="display:block;"
                type="digit"
                v-model="edits[s.student_id].usual"
                :disabled="s.is_published === '1'"
              />
            </view>
            <view class="stu-field">
              <text class="stu-field-label">考试</text>
              <input
                class="stu-input"
                style="display:block;"
                type="digit"
                v-model="edits[s.student_id].exam"
                :disabled="s.is_published === '1'"
              />
            </view>
            <text class="stu-total" :class="(s.total_score !== null && s.total_score < 60) ? 'fail' : ''">
              {{ s.total_score !== null ? s.total_score : '—' }}
            </text>
          </view>
        </view>
        <button class="save-btn" :disabled="saving" @click="onSave">
          {{ saving ? '保存中...' : '保存成绩' }}
        </button>
        <view class="tip">已发布成绩不可修改；保存后由管理员发布，学生端才可见。</view>
      </view>
    </view>

    <view v-if="loaded && !students.length" class="empty">
      <text class="empty-sub">请先选择教学班</text>
    </view>
  </view>
</template>

<script>
import { get, post } from '../../utils/request'

export default {
  data() {
    return {
      offerings: [],
      offeringIndex: -1,
      students: [],
      edits: {},
      saving: false,
      loaded: false
    }
  },
  computed: {
    offeringLabels() {
      return this.offerings.map((o) => `${o.course_name} · ${o.class_name}`)
    },
    currentLabel() {
      if (this.offeringIndex < 0) return ''
      const o = this.offerings[this.offeringIndex]
      return `${o.course_name} · ${o.class_name}`
    }
  },
  onShow() {
    this.loadOfferings()
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    async loadOfferings() {
      try {
        const data = await get('/api/scores/teacher-offerings')
        this.offerings = data.list || []
        this.loaded = true
      } catch (err) {
        this.toast(err.message || '教学班加载失败')
        this.loaded = true
      }
    },
    async onOfferingChange(e) {
      this.offeringIndex = Number(e.detail.value)
      const o = this.offerings[this.offeringIndex]
      try {
        const data = await get('/api/scores/course', { offering_id: o.offering_id })
        this.students = data.students || []
        this.edits = {}
        this.students.forEach((s) => {
          this.edits[s.student_id] = {
            usual: s.usual_score !== null ? String(s.usual_score) : '',
            exam: s.exam_score !== null ? String(s.exam_score) : ''
          }
        })
      } catch (err) {
        this.toast(err.message || '学生名单加载失败')
      }
    },
    async onSave() {
      const o = this.offerings[this.offeringIndex]
      const scores = this.students
        .filter((s) => s.is_published !== '1')
        .map((s) => {
          const e = this.edits[s.student_id]
          const payload = { student_id: s.student_id, version: s.version || 0 }
          if (e.usual !== '') payload.usual_score = Number(e.usual)
          if (e.exam !== '') payload.exam_score = Number(e.exam)
          return payload
        })
        .filter((x) => x.usual_score !== undefined && x.exam_score !== undefined)
      if (!scores.length) {
        this.toast('请先填写成绩')
        return
      }
      this.saving = true
      try {
        const data = await post('/api/scores', { offering_id: o.offering_id, version: 0, scores })
        this.toast(`已保存 ${data.updated} 条${data.warnings ? '（部分跳过）' : ''}`)
        this.onOfferingChange({ detail: { value: this.offeringIndex } })
      } catch (err) {
        this.toast(err.message || '保存失败')
      } finally {
        this.saving = false
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.input-page {
  min-height: 100vh;
  padding: 32rpx;
  background: $bg;
}

.card-shell {
  background: rgba(255, 255, 255, 0.6);
  border: 2rpx solid $line;
  border-radius: $radius-card;
  padding: 12rpx;
  box-shadow: $shadow-soft;
  margin-bottom: 24rpx;
}
.card-core {
  background: $surface;
  border-radius: calc(#{$radius-card} - 12rpx);
  box-shadow: inset 0 2rpx 0 rgba(255, 255, 255, 0.6);
  padding: 24rpx;
}

.offering-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 8rpx;
}
.offering-label {
  font-size: $fs-14;
  color: $ink;
}
.offering-arrow {
  font-size: $fs-20;
  color: $ink-2;
}

.stu-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20rpx 0;
  border-bottom: 2rpx solid $line;
}
.stu-row:last-child {
  border-bottom: none;
}
.stu-info {
  flex: 1;
}
.stu-name {
  display: block;
  font-size: $fs-14;
  font-weight: 600;
  color: $ink;
}
.stu-no {
  display: block;
  margin-top: 4rpx;
  font-size: 20rpx;
  color: $ink-2;
}

.stu-inputs {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.stu-field {
  width: 130rpx;
}
.stu-field-label {
  font-size: 20rpx;
  color: $ink-2;
}
.stu-input {
  height: 64rpx;
  padding: 0 12rpx;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  font-size: $fs-14;
  color: $ink;
}
.stu-total {
  width: 90rpx;
  text-align: right;
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.stu-total.fail {
  color: $err;
}

.save-btn {
  margin-top: 24rpx;
  background: $brand;
  color: #ffffff;
  border-radius: $radius-pill;
  font-size: $fs-16;
}
.tip {
  margin-top: 12rpx;
  font-size: 20rpx;
  color: $ink-2;
  text-align: center;
}

.empty {
  padding: 120rpx 32rpx;
  text-align: center;
}
.empty-sub {
  font-size: $fs-12;
  color: $ink-2;
}
</style>
