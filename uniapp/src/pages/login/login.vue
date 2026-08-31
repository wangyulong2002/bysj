<template>
  <view class="login-page">
    <!-- 品牌区 -->
    <view class="brand">
      <view class="brand-mark">
        <view class="brand-mark-inner"></view>
      </view>
      <text class="brand-title">智慧校园</text>
      <text class="brand-sub">课表 · 成绩 · 公告 · 请假，一站掌握</text>
    </view>

    <!-- 双边框登录卡片 -->
    <view class="card-shell">
      <view class="card-core">
        <view class="field">
          <text class="field-label">账号</text>
          <input
            class="field-input"
            style="display:block;width:100%;height:96rpx;"
            v-model="username"
            placeholder="学号 / 工号"
            placeholder-class="field-placeholder"
            :disabled="binding"
          />
        </view>
        <view class="field">
          <text class="field-label">密码</text>
          <input
            class="field-input"
            style="display:block;width:100%;height:96rpx;"
            v-model="password"
            password
            placeholder="请输入密码"
            placeholder-class="field-placeholder"
            :disabled="binding"
            @confirm="onPasswordLogin"
          />
        </view>

        <button
          class="btn btn-primary"
          :disabled="submitting"
          :class="{ 'btn-disabled': submitting }"
          @tap="onPasswordLogin"
        >
          {{ submitting ? '登录中...' : '登 录' }}
        </button>

        <!-- 微信授权入口（设计报告 7.1：登录页含微信授权入口） -->
        <view class="divider">
          <view class="divider-line"></view>
          <text class="divider-text">其他方式</text>
          <view class="divider-line"></view>
        </view>

        <button
          class="btn btn-wechat"
          :disabled="wxLoading"
          :class="{ 'btn-disabled': wxLoading }"
          @tap="onWechatLogin"
        >
          <text class="wechat-icon"></text>
          {{ wxLoading ? '授权中...' : '微信一键登录' }}
        </button>
        <text v-if="!wechatOk" class="wechat-hint">微信登录仅小程序支持，当前平台请使用账号密码</text>
      </view>
    </view>

    <!-- 绑定面板（openid 未绑定 → 引导账号密码完成首次绑定，3.4） -->
    <view v-if="binding" class="bind-panel">
      <view class="bind-title">绑定微信账号</view>
      <view class="bind-desc">该微信尚未绑定账号，输入学号/工号和密码完成首次绑定</view>
      <input class="field-input bind-input" style="display:block;width:100%;height:96rpx;" v-model="bindUsername" placeholder="学号 / 工号" placeholder-class="field-placeholder" />
      <input class="field-input bind-input" style="display:block;width:100%;height:96rpx;" v-model="bindPassword" password placeholder="密码" placeholder-class="field-placeholder" />
      <view class="bind-actions">
        <button class="btn btn-ghost" @tap="binding = false">取消</button>
        <button class="btn btn-primary" :disabled="bindLoading" @tap="onBindSubmit">
          {{ bindLoading ? '绑定中...' : '确认绑定' }}
        </button>
      </view>
    </view>

    <!-- 游客公开入口（8.5/7.1：AI 校园助手无需登录） -->
    <view class="ai-entry" @tap="goAiChat">
      <text class="ai-entry-text">🤖 游客可先体验「AI 校园助手」</text>
      <text class="ai-entry-arrow">›</text>
    </view>

    <view class="footer">首次使用请先联系管理员开通账号</view>
  </view>
</template>

<script>
import { post } from '../../utils/request'
import { saveSession, isWechatSupported, wechatLoginCheckBind, bindWechat } from '../../utils/wechat-auth'

export default {
  data() {
    return {
      username: '',
      password: '',
      submitting: false,
      wechatOk: isWechatSupported(),
      wxLoading: false,
      // 绑定面板
      binding: false,
      bindCode: '',
      bindUsername: '',
      bindPassword: '',
      bindLoading: false
    }
  },
  methods: {
    toast(title) {
      // 轻提示（不阻塞图标）
      uni.showToast({ title, icon: 'none' })
    },
    /** 账号密码登录（T1-2 接口） */
    async onPasswordLogin() {
      if (!this.username || !this.password) {
        this.toast('请输入账号和密码')
        return
      }
      this.submitting = true
      try {
        const data = await post('/api/auth/login', { username: this.username, password: this.password })
        saveSession(data)
        this.enterHome()
      } catch (err) {
        this.toast(err.message || '登录失败')
      } finally {
        this.submitting = false
      }
    },
    /** 微信授权登录（T1-4） */
    async onWechatLogin() {
      if (!this.wechatOk) {
        this.toast('当前平台不支持微信登录')
        return
      }
      this.wxLoading = true
      try {
        const result = await wechatLoginCheckBind()
        if (result.needBind) {
          // openid 未绑定 → 展开绑定面板
          this.binding = true
          this.bindCode = result.code
          this.toast('该微信尚未绑定账号，请绑定')
        } else {
          this.enterHome()
        }
      } catch (err) {
        this.toast(err.message || '微信登录失败')
      } finally {
        this.wxLoading = false
      }
    },
    /** 首次绑定提交 */
    async onBindSubmit() {
      if (!this.bindUsername || !this.bindPassword) {
        this.toast('请输入账号和密码')
        return
      }
      this.bindLoading = true
      try {
        await bindWechat(this.bindCode, this.bindUsername, this.bindPassword)
        this.toast('绑定成功')
        this.enterHome()
      } catch (err) {
        this.toast(err.message || '绑定失败')
      } finally {
        this.bindLoading = false
      }
    },
    enterHome() {
      // 延迟 300ms 后跳转首页（让提示展示完整）
      setTimeout(() => {
        uni.reLaunch({ url: '/pages/index/index' })
      }, 300)
    },
    goAiChat() {
      // AI 校园助手游客入口（T7-6：chat/suggest/feedback 均公开接口，未登录可直达）
      uni.navigateTo({ url: '/pages/ai/chat' })
    }
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  padding: 0 40rpx;
  background: $bg;
  display: flex;
  flex-direction: column;
}

/* 品牌区 */
.brand {
  padding: 120rpx 0 72rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.brand-mark {
  width: 112rpx;
  height: 112rpx;
  border-radius: 32rpx;
  background: $brand-soft;
  border: 2rpx solid $brand;
  padding: 10rpx;
  margin-bottom: 32rpx;
}
.brand-mark-inner {
  width: 100%;
  height: 100%;
  border-radius: 24rpx;
  background: linear-gradient(135deg, $brand, $brand-deep);
}
.brand-title {
  font-size: $fs-28;
  font-weight: 600;
  color: $ink;
  letter-spacing: 4rpx;
}
.brand-sub {
  margin-top: 16rpx;
  font-size: $fs-14;
  color: $ink-2;
}

/* 双边框卡片（7.3.4 Doppelrand） */
.card-shell {
  background: rgba(255, 255, 255, 0.6);
  border: 2rpx solid $line;
  border-radius: $radius-card;
  padding: 12rpx;
  box-shadow: $shadow-soft;
}
.card-core {
  background: $surface;
  border-radius: calc(#{$radius-card} - 12rpx);
  box-shadow: inset 0 2rpx 0 rgba(255, 255, 255, 0.6);
  padding: 40rpx 36rpx;
}

.field {
  margin-bottom: 32rpx;
}
.field-label {
  display: block;
  font-size: $fs-14;
  color: $ink-2;
  margin-bottom: 12rpx;
}
.field-input {
  width: 100%;
  height: 96rpx;
  padding: 0 28rpx;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  font-size: $fs-16;
  color: $ink;
  transition: border-color 300ms $ease-premium;
}
.field-input:focus {
  border-color: $brand;
}
.field-placeholder {
  color: #94a3b8;
}

/* 按钮（7.3.5） */
.btn {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  border-radius: $radius-pill;
  font-size: $fs-16;
  font-weight: 500;
  border: none;
  transition: transform 200ms $ease-premium, opacity 200ms;
}
.btn:active {
  transform: scale(0.98);
}
.btn-disabled {
  opacity: 0.5;
}
.btn-primary {
  background: $brand;
  color: #ffffff;
}
.btn-primary:active {
  background: $brand-deep;
}
.btn-wechat {
  background: #07c160;
  color: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12rpx;
}
.wechat-icon {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.9);
  position: relative;
}
.wechat-icon::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  width: 16rpx;
  height: 16rpx;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: #07c160;
}
.wechat-hint {
  display: block;
  margin-top: 16rpx;
  text-align: center;
  font-size: $fs-12;
  color: $ink-2;
}

/* 分隔线 */
.divider {
  display: flex;
  align-items: center;
  margin: 40rpx 0 32rpx;
}
.divider-line {
  flex: 1;
  height: 2rpx;
  background: $line;
}
.divider-text {
  padding: 0 24rpx;
  font-size: $fs-12;
  color: $ink-2;
}

/* 绑定面板 */
.bind-panel {
  margin-top: 32rpx;
  background: $surface;
  border: 2rpx solid $brand-soft;
  border-radius: $radius-card;
  padding: 32rpx;
  box-shadow: $shadow-soft;
  animation: slideUp 400ms $ease-premium;
}
@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(24rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
.bind-title {
  font-size: $fs-20;
  font-weight: 600;
  color: $ink;
}
.bind-desc {
  margin: 12rpx 0 28rpx;
  font-size: $fs-14;
  color: $ink-2;
  line-height: 1.6;
}
.bind-input {
  margin-bottom: 24rpx;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  height: 96rpx;
  padding: 0 28rpx;
  font-size: $fs-16;
}
.bind-actions {
  display: flex;
  gap: 24rpx;
}
.bind-actions .btn {
  flex: 1;
}
.btn-ghost {
  background: $brand-soft;
  color: $brand-deep;
}

.footer {
  margin-top: 48rpx;
  text-align: center;
  font-size: $fs-12;
  color: $ink-2;
}

/* AI 校园助手游客入口（T7-6） */
.ai-entry {
  margin-top: 32rpx;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 28rpx;
  background: $brand-soft;
  border: 2rpx solid rgba(14, 116, 144, 0.3);
  border-radius: $radius-ctrl;
  transition: transform 0.25s $ease-premium;
  &:active {
    transform: scale(0.98);
  }
}
.ai-entry-text {
  font-size: $fs-14;
  color: $brand-deep;
}
.ai-entry-arrow {
  font-size: $fs-20;
  color: $brand-deep;
}
</style>
