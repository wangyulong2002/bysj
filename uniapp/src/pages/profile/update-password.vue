<template>
  <view class="pwd-page">
    <view class="card-shell">
      <view class="card-core">
        <view class="field">
          <text class="field-label">原密码</text>
          <input
            v-model="oldPwd"
            class="field-input"
            password
            placeholder="请输入原密码"
            placeholder-class="field-placeholder"
          />
        </view>
        <view class="field">
          <text class="field-label">新密码</text>
          <input
            v-model="newPwd"
            class="field-input"
            password
            placeholder="6~32 位新密码"
            placeholder-class="field-placeholder"
          />
        </view>
        <view class="field">
          <text class="field-label">确认密码</text>
          <input
            v-model="confirmPwd"
            class="field-input"
            password
            placeholder="再次输入新密码"
            placeholder-class="field-placeholder"
          />
        </view>

        <view class="btn btn-primary" :class="{ 'btn-disabled': submitting }" @tap="onSubmit">
          {{ submitting ? '提交中' : '确认修改' }}
        </view>
        <text class="pwd-tip">修改成功后需使用新密码重新登录（原登录状态将失效）</text>
      </view>
    </view>
  </view>
</template>

<script>
import { STORAGE_KEYS } from '../../utils/config'
import { put } from '../../utils/request'

export default {
  data() {
    return {
      oldPwd: '',
      newPwd: '',
      confirmPwd: '',
      submitting: false
    }
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    async onSubmit() {
      if (!this.oldPwd) {
        this.toast('请输入原密码')
        return
      }
      if (this.newPwd.length < 6 || this.newPwd.length > 32) {
        this.toast('新密码需为 6~32 位')
        return
      }
      if (this.newPwd !== this.confirmPwd) {
        this.toast('两次输入的新密码不一致')
        return
      }
      this.submitting = true
      try {
        await put('/api/auth/password', { old_password: this.oldPwd, new_password: this.newPwd })
        // 改密成功：清理本地 token 与用户信息，重新登录（T6-2）
        uni.removeStorageSync(STORAGE_KEYS.token)
        uni.removeStorageSync(STORAGE_KEYS.userInfo)
        uni.showToast({ title: '密码已修改，请重新登录', icon: 'none', duration: 1500 })
        setTimeout(() => {
          uni.reLaunch({ url: '/pages/login/login' })
        }, 1200)
      } catch (err) {
        this.toast(err.message || '修改失败')
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.pwd-page {
  min-height: 100vh;
  padding: 40rpx;
  background: $bg;
}

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
  padding: 32rpx;
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
  height: 88rpx;
  padding: 0 24rpx;
  background: $bg;
  border-radius: $radius-ctrl;
  font-size: $fs-14;
  color: $ink;
}
.field-placeholder {
  color: $ink-2;
}

.btn {
  height: 88rpx;
  border-radius: $radius-ctrl;
  font-size: $fs-16;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-primary {
  background: $brand;
  color: #fff;
}
.btn-disabled {
  opacity: 0.6;
}

.pwd-tip {
  display: block;
  margin-top: 24rpx;
  font-size: $fs-12;
  color: $ink-2;
  text-align: center;
}
</style>
