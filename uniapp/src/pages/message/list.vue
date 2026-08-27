<template>
  <view class="msg-page">
    <!-- 未读 Tab -->
    <view class="card-shell">
      <view class="card-core tab-core">
        <view
          v-for="t in tabs"
          :key="t.value"
          class="tab-item"
          :class="{ active: current === t.value }"
          @tap="onTab(t.value)"
        >
          <text class="tab-text">
            {{ t.name }}<text v-if="t.value === '0' && unread" class="tab-dot"> {{ unread }}</text>
          </text>
        </view>
      </view>
    </view>

    <view v-if="list.length">
      <view v-for="m in list" :key="m.id" class="card-shell">
        <view class="card-core msg-card" @tap="onRead(m)">
          <view class="msg-head">
            <text class="msg-type">{{ m.msg_type_name }}</text>
            <text v-if="m.is_read === '0'" class="msg-unread">未读</text>
            <text class="msg-time">{{ format(m.create_time) }}</text>
          </view>
          <text class="msg-title">{{ m.title }}</text>
          <text class="msg-content">{{ m.content }}</text>
        </view>
      </view>
    </view>

    <view v-if="loaded && !list.length" class="empty">
      <text class="empty-title">暂无消息</text>
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
        { value: '0', name: '未读' },
        { value: '', name: '全部' }
      ],
      current: '0',
      list: [],
      unread: 0,
      loaded: false
    }
  },
  onShow() {
    this.load()
    this.loadUnread()
  },
  onPullDownRefresh() {
    Promise.all([this.load(), this.loadUnread()]).finally(() => uni.stopPullDownRefresh())
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
        const data = await get('/api/messages', {
          unread_only: this.current === '0' ? 1 : 0,
          page_size: 50
        })
        this.list = data.list || []
        this.loaded = true
      } catch (err) {
        this.toast(err.message || '加载失败')
        this.loaded = true
      }
    },
    async loadUnread() {
      try {
        const data = await get('/api/messages/unread-count')
        this.unread = data.count || 0
      } catch (e) {
        // 忽略
      }
    },
    onTab(v) {
      if (this.current === v) return
      this.current = v
      this.load()
    },
    async onRead(m) {
      if (m.is_read === '1') return
      try {
        await put(`/api/messages/${m.id}/read`)
        m.is_read = '1'
        this.loadUnread()
      } catch (e) {
        // 忽略
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.msg-page {
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
.tab-dot {
  color: $err;
  font-weight: 600;
}

.msg-head {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.msg-type {
  font-size: 20rpx;
  padding: 4rpx 14rpx;
  border-radius: $radius-pill;
  color: $brand-deep;
  background: $brand-soft;
}
.msg-unread {
  font-size: 20rpx;
  color: $err;
  font-weight: 600;
}
.msg-time {
  margin-left: auto;
  font-size: 20rpx;
  color: $ink-2;
}

.msg-title {
  display: block;
  margin-top: 12rpx;
  font-size: $fs-14;
  font-weight: 600;
  color: $ink;
}
.msg-content {
  display: block;
  margin-top: 8rpx;
  font-size: $fs-12;
  color: $ink-2;
  line-height: 1.6;
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
