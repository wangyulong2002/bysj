<template>
  <view class="leave-page">
    <!-- 状态筛选 -->
    <view class="card-shell">
      <view class="card-core tab-core">
        <view
          v-for="t in tabs"
          :key="t.value"
          class="tab-item"
          :class="{ active: current === t.value }"
          @tap="onTab(t.value)"
        >
          <text class="tab-text">{{ t.name }}</text>
        </view>
      </view>
    </view>

    <!-- 我的请假列表 -->
    <view v-if="list.length">
      <view v-for="l in list" :key="l.leave_id" class="card-shell">
        <view class="card-core leave-card">
          <view class="leave-head">
            <view class="leave-head-left">
              <text class="leave-type">{{ TYPE_NAMES[l.leave_type] }}</text>
              <text class="leave-status" :class="statusClass(l.status)">{{ l.status_name }}</text>
            </view>
            <text class="leave-duration">{{ l.total_days }} 天</text>
          </view>
          <text class="leave-reason">{{ l.reason }}</text>
          <view class="leave-time">
            {{ format(l.start_time) }} ~ {{ format(l.end_time) }}
          </view>
          <view v-if="l.approve_comment" class="leave-comment">审批意见：{{ l.approve_comment }}</view>
          <button
            v-if="l.status === '0'"
            class="cancel-btn"
            size="mini"
            @tap="onCancel(l)"
          >
            撤销申请
          </button>
        </view>
      </view>
    </view>

    <view v-if="loaded && !list.length" class="empty">
      <text class="empty-title">暂无请假记录</text>
    </view>
    <view v-if="!loaded" class="empty">
      <text class="empty-sub">加载中...</text>
    </view>
  </view>
</template>

<script>
import { get, put } from '../../utils/request'

export default {
  data() {
    return {
      tabs: [
        { value: '', name: '全部' },
        { value: '0', name: '待审批' },
        { value: '1', name: '通过' },
        { value: '2', name: '驳回' },
        { value: '3', name: '撤销' }
      ],
      current: '',
      TYPE_NAMES: { 1: '事假', 2: '病假', 3: '其他' },
      list: [],
      loaded: false
    }
  },
  onShow() {
    this.load()
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    statusClass(s) {
      return { 0: 'st-pending', 1: 'st-ok', 2: 'st-reject', 3: 'st-cancel' }[s] || ''
    },
    format(t) {
      if (!t) return ''
      return String(t).replace('T', ' ').slice(0, 16)
    },
    async load() {
      try {
        const data = await get('/api/leaves/mine', {
          status: this.current || undefined,
          page_size: 50
        })
        this.list = data.list || []
        this.loaded = true
      } catch (err) {
        this.toast(err.message || '加载失败')
        this.loaded = true
      }
    },
    onTab(v) {
      if (this.current === v) return
      this.current = v
      this.load()
    },
    onCancel(l) {
      uni.showModal({
        title: '撤销申请',
        content: '确定撤销这条待审批的请假吗？',
        success: async (res) => {
          if (!res.confirm) return
          try {
            await put(`/api/leaves/${l.leave_id}/cancel`)
            this.toast('已撤销')
            this.load()
          } catch (err) {
            this.toast(err.message || '撤销失败')
          }
        }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.leave-page {
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

.tab-core {
  display: flex;
  padding: 8rpx;
}
.tab-item {
  flex: 1;
  text-align: center;
  padding: 14rpx 0;
  border-radius: $radius-ctrl;
}
.tab-item.active {
  background: $brand-soft;
}
.tab-text {
  font-size: $fs-12;
  color: $ink-2;
  .tab-item.active & {
    color: $brand-deep;
    font-weight: 600;
  }
}

.leave-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.leave-head-left {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.leave-type {
  font-size: 20rpx;
  padding: 4rpx 14rpx;
  border-radius: $radius-pill;
  color: $brand-deep;
  background: $brand-soft;
}
.leave-status {
  font-size: 20rpx;
  font-weight: 600;
}
.st-pending { color: $warn; }
.st-ok { color: $ok; }
.st-reject { color: $err; }
.st-cancel { color: $ink-2; }
.leave-duration {
  font-size: $fs-14;
  font-weight: 600;
  color: $ink;
}

.leave-reason {
  display: block;
  margin-top: 16rpx;
  font-size: $fs-14;
  color: $ink;
  line-height: 1.6;
}
.leave-time {
  margin-top: 10rpx;
  font-size: 20rpx;
  color: $ink-2;
}
.leave-comment {
  margin-top: 10rpx;
  font-size: 20rpx;
  color: $ink-2;
}
.cancel-btn {
  margin: 16rpx 0 0 auto;
  background: rgba(220, 38, 38, 0.08);
  color: $err;
  border-radius: $radius-pill;
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
