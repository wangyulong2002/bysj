<template>
  <view class="home-page">
    <view class="welcome">
      <text class="welcome-title">你好，{{ userInfo ? userInfo.name : '同学' }}</text>
      <text class="welcome-sub">欢迎使用智慧校园信息管理系统</text>
    </view>

    <!-- 置顶公告卡片（T3-4：首页热点展示，点击跳详情/列表） -->
    <view v-if="topAnnouncements.length" class="card-shell">
      <view class="card-core top-core">
        <view class="top-head" @tap="goAnnouncementList">
          <text class="top-title">公告</text>
          <text class="top-more">更多 ›</text>
        </view>
        <view
          v-for="a in topAnnouncements"
          :key="a.id"
          class="top-item"
          @tap="goAnnouncementDetail(a.id)"
        >
          <text class="top-badge">置顶</text>
          <text class="top-text">{{ a.title }}</text>
        </view>
      </view>
    </view>

    <!-- 快捷入口（T2-7 课表 / T3-4 公告 / M4 成绩 / M5 请假与消息） -->
    <view class="card-shell">
      <view class="card-core">
        <view class="entry-row">
          <view class="entry" @tap="goTimetable">课表</view>
          <view class="entry" @tap="goScore">成绩</view>
          <view class="entry" @tap="goAnnouncementList">公告</view>
          <view class="entry" @tap="goLeaveApply">请假</view>
        </view>
        <view class="entry-row entry-row-sub">
          <view class="entry" @tap="goLeaveList">我的请假</view>
          <view class="entry" @tap="goMessageList">消息</view>
          <view class="entry" @tap="goLeaveApprove">审批</view>
          <view class="entry entry-empty">·</view>
        </view>
      </view>
    </view>

    <!-- 账号操作（T1-4 解绑演示） -->
    <view class="card-shell">
      <view class="card-core">
        <view class="op-row" @tap="goProfile">
          <text class="op-label">个人信息</text>
          <text class="op-arrow">›</text>
        </view>
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
import { get } from '../../utils/request'
import { unbindWechat, clearSession } from '../../utils/wechat-auth'

export default {
  data() {
    return {
      userInfo: null,
      topAnnouncements: []
    }
  },
  onShow() {
    // 页面展示时刷新用户信息，并校验登录态（未登录跳转登录页）
    this.userInfo = uni.getStorageSync(STORAGE_KEYS.userInfo) || null
    const token = uni.getStorageSync(STORAGE_KEYS.token)
    if (!token) {
      uni.reLaunch({ url: '/pages/login/login' })
      return
    }
    this.loadTopAnnouncements()
  },
  methods: {
    toast(title) {
      // 轻提示（不阻塞图标）
      uni.showToast({ title, icon: 'none' })
    },
    async loadTopAnnouncements() {
      // 首页置顶公告（T3-4）：取置顶公告前 3 条
      try {
        const data = await get('/api/announcements', { is_top: '1', page_size: 3 })
        this.topAnnouncements = (data.list || []).slice(0, 3)
      } catch (err) {
        // 公告加载失败不影响首页其余功能
      }
    },
    goTimetable() {
      // 跳转课表页
      uni.navigateTo({ url: '/pages/timetable/timetable' })
    },
    goAnnouncementList() {
      // 跳转公告列表页
      uni.navigateTo({ url: '/pages/announcement/list' })
    },
    goAnnouncementDetail(id) {
      // 跳转公告详情页
      uni.navigateTo({ url: `/pages/announcement/detail?id=${id}` })
    },
    goScore() {
      // 成绩（学生：我的成绩；教师：成绩录入）
      const role = (this.userInfo && this.userInfo.role_code) || ''
      uni.navigateTo({ url: role === 'teacher' ? '/pages/score/input' : '/pages/score/score' })
    },
    goLeaveApply() {
      // 请假申请
      uni.navigateTo({ url: '/pages/leave/apply' })
    },
    goLeaveList() {
      // 我的请假
      uni.navigateTo({ url: '/pages/leave/list' })
    },
    goLeaveApprove() {
      // 请假审批（辅导员/兼任教师）
      uni.navigateTo({ url: '/pages/leave/approve' })
    },
    goMessageList() {
      // 消息中心
      uni.navigateTo({ url: '/pages/message/list' })
    },
    goProfile() {
      // 个人信息（M6-T6-2）
      uni.navigateTo({ url: '/pages/profile/profile' })
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

/* ===== 置顶公告（T3-4）===== */
.top-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 16rpx;
}
.top-title {
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.top-more {
  font-size: $fs-12;
  color: $brand-deep;
}
.top-item {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 16rpx 8rpx;
  border-bottom: 2rpx solid $line;
}
.top-item:last-child {
  border-bottom: none;
}
.top-badge {
  flex-shrink: 0;
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: $radius-pill;
  color: $warn;
  background: rgba(254, 243, 199, 0.5);
  border: 2rpx solid rgba(217, 119, 6, 0.35);
}
.top-text {
  flex: 1;
  font-size: $fs-14;
  color: $ink;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

/* ===== 快捷入口 ===== */
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
  transition: transform 0.25s $ease-premium;
  &:active {
    transform: scale(0.96);
  }
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
