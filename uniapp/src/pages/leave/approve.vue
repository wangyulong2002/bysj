<template>
  <view class="approve-page">
    <view v-if="list.length">
      <view v-for="l in list" :key="l.leave_id" class="card-shell">
        <view class="card-core approve-card">
          <view class="app-head">
            <text class="app-student">{{ l.student_name }}</text>
            <text class="app-no">{{ l.student_no }}</text>
            <text class="app-type">{{ TYPE_NAMES[l.leave_type] }}</text>
          </view>
          <text class="app-reason">{{ l.reason }}</text>
          <view class="app-time">{{ format(l.start_time) }} ~ {{ format(l.end_time) }}</view>
          <view class="app-duration">时长 {{ l.total_days }} 天</view>

          <view v-if="l.status === '0'" class="app-actions">
            <input
              class="app-comment"
              style="display:block;"
              v-model="comments[l.leave_id]"
              placeholder="审批意见（选填）"
            />
            <view class="app-btns">
              <button class="btn-ok" size="mini" @tap="onApprove(l, '1')">通过</button>
              <button class="btn-reject" size="mini" @tap="onApprove(l, '2')">驳回</button>
            </view>
          </view>
          <view v-else class="app-result">
            已{{ l.status_name === '通过' ? '通过' : l.status_name }}
            <text v-if="l.approve_comment">：{{ l.approve_comment }}</text>
          </view>
        </view>
      </view>
    </view>

    <view v-if="loaded && !list.length" class="empty">
      <text class="empty-title">暂无待审批申请</text>
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
      TYPE_NAMES: { 1: '事假', 2: '病假', 3: '其他' },
      list: [],
      comments: {},
      loaded: false
    }
  },
  onShow() {
    this.load()
  },
  onPullDownRefresh() {
    this.load().finally(() => uni.stopPullDownRefresh())
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    format(t) {
      if (!t) return ''
      return String(t).replace('T', ' ').slice(0, 16)
    },
    async load() {
      try {
        const data = await get('/api/leaves/pending', { page_size: 50 })
        this.list = data.list || []
        this.loaded = true
      } catch (err) {
        this.toast(err.message || '加载失败')
        this.loaded = true
      }
    },
    async onApprove(l, approve) {
      const comment = (this.comments[l.leave_id] || '').trim()
      uni.showModal({
        title: approve === '1' ? '通过申请' : '驳回申请',
        content: approve === '1' ? '确定通过该请假申请吗？' : '确定驳回该请假申请吗？',
        success: async (res) => {
          if (!res.confirm) return
          try {
            await put(`/api/leaves/${l.leave_id}/approve`, { approve, comment })
            this.toast(approve === '1' ? '已通过' : '已驳回')
            this.load()
          } catch (err) {
            this.toast(err.message || '操作失败')
          }
        }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.approve-page {
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

.app-head {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.app-student {
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.app-no {
  font-size: 20rpx;
  color: $ink-2;
}
.app-type {
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: $radius-pill;
  color: $brand-deep;
  background: $brand-soft;
}

.app-reason {
  display: block;
  margin-top: 14rpx;
  font-size: $fs-14;
  color: $ink;
  line-height: 1.6;
}
.app-time {
  margin-top: 10rpx;
  font-size: 20rpx;
  color: $ink-2;
}
.app-duration {
  margin-top: 6rpx;
  font-size: 20rpx;
  color: $ink-2;
}

.app-comment {
  margin-top: 16rpx;
  height: 72rpx;
  padding: 0 16rpx;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  font-size: $fs-12;
  color: $ink;
}
.app-btns {
  display: flex;
  gap: 16rpx;
  margin-top: 16rpx;
}
.btn-ok {
  flex: 1;
  background: $brand;
  color: #ffffff;
  border-radius: $radius-pill;
}
.btn-reject {
  flex: 1;
  background: rgba(220, 38, 38, 0.08);
  color: $err;
  border-radius: $radius-pill;
}
.app-result {
  margin-top: 14rpx;
  font-size: $fs-12;
  color: $ink-2;
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
