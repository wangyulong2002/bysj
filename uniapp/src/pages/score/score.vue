<template>
  <view class="score-page">
    <!-- 学期筛选 -->
    <view class="card-shell">
      <view class="card-core term-core">
        <picker :range="termNames" @change="onTermChange">
          <view class="term-picker">
            <text class="term-label">{{ termNames[termIndex] || '全部学期' }}</text>
            <text class="term-arrow">›</text>
          </view>
        </picker>
      </view>
    </view>

    <!-- 成绩列表（仅已发布） -->
    <view v-if="list.length" class="score-list">
      <view v-for="s in list" :key="s.score_id" class="card-shell">
        <view class="card-core score-card">
          <view class="score-head">
            <text class="score-course">{{ s.course_name }}</text>
            <text class="score-term">{{ s.term_name }}</text>
          </view>
          <view class="score-grid">
            <view class="score-item">
              <text class="score-label">平时</text>
              <text class="score-value">{{ s.usual_score != null ? s.usual_score : '—' }}</text>
            </view>
            <view class="score-item">
              <text class="score-label">考试</text>
              <text class="score-value">{{ s.exam_score != null ? s.exam_score : '—' }}</text>
            </view>
            <view class="score-item">
              <text class="score-label">总评</text>
              <text class="score-value" :class="s.pass ? 'pass' : 'fail'">{{ s.total_score != null ? s.total_score : '—' }}</text>
            </view>
            <view class="score-item">
              <text class="score-label">状态</text>
              <text class="score-value" :class="s.pass ? 'pass' : 'fail'">{{ s.pass ? '及格' : '不及格' }}</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view v-if="loaded && !list.length" class="empty">
      <text class="empty-title">暂无已发布成绩</text>
      <text class="empty-sub">成绩发布后可见</text>
    </view>
    <view v-if="!loaded" class="empty">
      <text class="empty-sub">加载中...</text>
    </view>
  </view>
</template>

<script>
import { get } from '../../utils/request'

export default {
  data() {
    return {
      list: [],
      terms: [],
      termIndex: 0,
      loaded: false
    }
  },
  computed: {
    termNames() {
      return ['全部学期', ...this.terms.map((t) => t.term_name)]
    }
  },
  onShow() {
    this.loadTerms()
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    async loadTerms() {
      try {
        // 从成绩数据中聚合学期选项（简化：先拉全部成绩再按学期分组）
        const data = await get('/api/scores/mine', { page_size: 100 })
        this.list = data.list || []
        const seen = new Map()
        ;(data.list || []).forEach((s) => {
          if (!seen.has(s.term_id)) seen.set(s.term_id, s.term_name)
        })
        this.terms = [...seen.entries()].map(([id, name]) => ({ term_id: id, term_name: name }))
        this.loaded = true
      } catch (err) {
        this.toast(err.message || '成绩加载失败')
        this.loaded = true
      }
    },
    async onTermChange(e) {
      this.termIndex = Number(e.detail.value)
      const term = this.terms[this.termIndex - 1]
      try {
        const data = await get('/api/scores/mine', { page_size: 100, term_id: term ? term.term_id : undefined })
        this.list = data.list || []
      } catch (err) {
        this.toast(err.message || '加载失败')
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.score-page {
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

.term-picker {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16rpx 8rpx;
}
.term-label {
  font-size: $fs-14;
  color: $ink;
}
.term-arrow {
  font-size: $fs-20;
  color: $ink-2;
}

.score-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.score-course {
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.score-term {
  font-size: $fs-12;
  color: $ink-2;
}

.score-grid {
  display: flex;
  margin-top: 20rpx;
  background: $bg;
  border-radius: $radius-ctrl;
  padding: 20rpx 0;
}
.score-item {
  flex: 1;
  text-align: center;
}
.score-label {
  display: block;
  font-size: 20rpx;
  color: $ink-2;
}
.score-value {
  display: block;
  margin-top: 8rpx;
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.score-value.pass {
  color: $ok;
}
.score-value.fail {
  color: $err;
}

.empty {
  padding: 120rpx 32rpx;
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
