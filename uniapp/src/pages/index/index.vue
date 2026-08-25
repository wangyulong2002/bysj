<template>
  <view class="home-page">
    <view class="welcome">
      <text class="welcome-title">你好，{{ userInfo ? userInfo.name : '同学' }}</text>
      <text class="welcome-sub">欢迎使用智慧校园信息管理系统</text>
    </view>

    <!-- 快捷入口（T2-7：课表已挂载，其余模块待 T3/T4/T5） -->
    <view class="card-shell">
      <view class="card-core">
        <view class="entry-row">
          <view class="entry" @tap="goTimetable">课表</view>
          <view class="entry">成绩</view>
          <view class="entry">公告</view>
          <view class="entry">请假</view>
        </view>
      </view>
    </view>

    <!-- 账号操作（T1-4 解绑演示） -->
    <view class="card-shell">
      <view class="card-core">
        <view class="op-row" @tap="onUnbind">
          <text class="op-label">微信解绑</text>
          <text class="op-arrow">›</text>
        </view>
        <view class="op-row" @tap="onLogout">
          <text class="op-label">退出登录</text>
          <text class="op-arrow">›</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { STORAGE_KEYS } from '../../utils/config'
import { unbindWechat, clearSession } from '../../utils/wechat-auth'

export default {
  data() {
    return {
      userInfo: null
    }
  },
  onShow() {
    // 页面展示时刷新用户信息，并校验登录态（未登录跳转登录页）
    this.userInfo = uni.getStorageSync(STORAGE_KEYS.userInfo) || null
    const token = uni.getStorageSync(STORAGE_KEYS.token)
    if (!token) {
      uni.reLaunch({ url: '/pages/login/login' })
    }
  },
  methods: {
    toast(title) {
      // 轻提示（不阻塞图标）
      uni.showToast({ title, icon: 'none' })
    },
    goTimetable() {
      // 跳转课表页
      uni.navigateTo({ url: '/pages/timetable/timetable' })
    },
    async onUnbind() {
      // 微信解绑：二次确认后调用解绑接口，失败给出提示
      uni.showModal({
        title: '微信解绑',
        content: '解绑后该微信将无法直接登录，确定解绑吗？',
        success: async (res) => {
          if (!res.confirm) return
          try {
            await unbindWechat()
            this.toast('已解绑微信')
          } catch (err) {
            this.toast(err.message || '解绑失败')
          }
        }
      })
    },
    onLogout() {
      // 退出登录：二次确认后清除本地会话并回登录页
      uni.showModal({
        title: '退出登录',
        content: '确定退出当前账号吗？',
        success: (res) => {
          if (!res.confirm) return
          clearSession()
          uni.reLaunch({ url: '/pages/login/login' })
        }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.home-page {
  min-height: 100vh;
  padding: 40rpx;
  background: $bg;
}
.welcome {
  padding: 48rpx 8rpx 40rpx;
}
.welcome-title {
  font-size: $fs-28;
  font-weight: 600;
  color: $ink;
}
.welcome-sub {
  display: block;
  margin-top: 12rpx;
  font-size: $fs-14;
  color: $ink-2;
}

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
  padding: 32rpx;
}

.entry-row {
  display: flex;
  justify-content: space-between;
}
.entry {
  flex: 1;
  text-align: center;
  padding: 40rpx 0;
  margin: 0 12rpx;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  font-size: $fs-16;
  color: $brand-deep;
}

.op-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 28rpx 8rpx;
  border-bottom: 2rpx solid $line;
}
.op-row:last-child {
  border-bottom: none;
}
.op-label {
  font-size: $fs-16;
  color: $ink;
}
.op-arrow {
  font-size: $fs-20;
  color: $ink-2;
}
</style>
