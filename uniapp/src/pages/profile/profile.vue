<template>
  <view class="profile-page">
    <!-- 头像 + 基本信息（T6-1 信息展示） -->
    <view class="card-shell">
      <view class="card-core head-core">
        <image
          v-if="profile.avatar"
          class="avatar"
          :src="profile.avatar"
          mode="aspectFill"
          @tap="onChangeAvatar"
        />
        <view v-else class="avatar avatar-empty" @tap="onChangeAvatar">
          <text class="avatar-text">{{ (profile.name || '?').slice(0, 1) }}</text>
        </view>
        <view class="head-info">
          <text class="head-name">{{ profile.name || '—' }}</text>
          <view class="head-tags">
            <text class="tag">{{ ROLE_NAMES[profile.role_code] || profile.role_code }}</text>
            <text v-if="profile.role_code === 'student' && profile.student_no" class="tag tag-muted">{{ profile.student_no }}</text>
            <text v-else-if="profile.role_code === 'teacher' && profile.teacher_no" class="tag tag-muted">{{ profile.teacher_no }}</text>
          </view>
          <text class="head-sub">点击头像可更换</text>
        </view>
      </view>
    </view>

    <!-- 档案信息（角色扩展：班级/院系/职称/课程） -->
    <view class="card-shell">
      <view class="card-core">
        <view class="row">
          <text class="row-label">账号</text>
          <text class="row-value">{{ profile.username || '—' }}</text>
        </view>
        <view class="row">
          <text class="row-label">手机号</text>
          <text class="row-value">{{ profile.masked_phone || '未设置' }}</text>
        </view>
        <view v-if="profile.role_code === 'student'" class="row">
          <text class="row-label">班级</text>
          <text class="row-value">{{ profile.class_name || '—' }}</text>
        </view>
        <view v-if="profile.role_code === 'teacher'" class="row">
          <text class="row-label">职称</text>
          <text class="row-value">{{ profile.title || '—' }}</text>
        </view>
        <view v-if="profile.role_code === 'teacher'" class="row">
          <text class="row-label">所属院系</text>
          <text class="row-value">{{ profile.department_name || '—' }}</text>
        </view>
        <view class="row">
          <text class="row-label">邮箱</text>
          <text class="row-value">{{ profile.email || '—' }}</text>
        </view>
        <view v-if="profile.courses && profile.courses.length" class="row row-col">
          <text class="row-label">课程</text>
          <view class="course-list">
            <text v-for="c in profile.courses" :key="c.course_id" class="tag tag-course">{{ c.course_name }}</text>
          </view>
        </view>
        <view class="row">
          <text class="row-label">微信绑定</text>
          <text class="row-value">{{ profile.wechat_bound ? '已绑定' : '未绑定' }}</text>
        </view>
      </view>
    </view>

    <!-- 手机号编辑（T6-1：手机号修改） -->
    <view class="card-shell">
      <view class="card-core">
        <view class="edit-title">修改手机号</view>
        <view class="edit-row">
          <input
            v-model="phoneDraft"
            class="edit-input"
            type="number"
            maxlength="11"
            placeholder="输入 11 位手机号"
            placeholder-class="edit-placeholder"
          />
          <view class="btn btn-primary" :class="{ 'btn-disabled': saving }" @tap="onSavePhone">
            {{ saving ? '保存中' : '保存' }}
          </view>
        </view>
      </view>
    </view>

    <!-- 账号操作 -->
    <view class="card-shell">
      <view class="card-core">
        <view class="op-row" @tap="goUpdatePassword">
          <text class="op-label">修改密码</text>
          <text class="op-arrow">›</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { API_BASE_URL, STORAGE_KEYS } from '../../utils/config'
import { get, put } from '../../utils/request'

const ROLE_NAMES = { student: '学生', teacher: '教师', admin: '管理员' }

export default {
  data() {
    return {
      profile: {},
      phoneDraft: '',
      saving: false,
      ROLE_NAMES
    }
  },
  onShow() {
    this.loadProfile()
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    async loadProfile() {
      try {
        this.profile = await get('/api/profile')
        this.phoneDraft = this.profile.masked_phone || ''
      } catch (err) {
        this.toast(err.message || '加载失败')
      }
    },
    async onSavePhone() {
      const phone = this.phoneDraft.replace(/\s+/g, '')
      if (!/^1\d{10}$/.test(phone)) {
        this.toast('请输入 1 开头的 11 位手机号')
        return
      }
      this.saving = true
      try {
        this.profile = await put('/api/profile', { phone })
        this.phoneDraft = this.profile.masked_phone || ''
        this.toast('手机号已更新')
      } catch (err) {
        this.toast(err.message || '保存失败')
      } finally {
        this.saving = false
      }
    },
    onChangeAvatar() {
      const token = uni.getStorageSync(STORAGE_KEYS.token)
      uni.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        success: async (res) => {
          const filePath = res.tempFilePaths[0]
          uni.showLoading({ title: '上传中', mask: true })
          try {
            const up = await new Promise((resolve, reject) => {
              uni.uploadFile({
                url: `${API_BASE_URL}/api/files?biz_type=avatar`,
                filePath,
                name: 'file',
                header: { Authorization: `Bearer ${token}` },
                success: (r) => {
                  try {
                    resolve(JSON.parse(r.data))
                  } catch (e) {
                    reject(new Error('上传响应解析失败'))
                  }
                },
                fail: (e) => reject(new Error(e.errMsg || '上传失败'))
              })
            })
            if (up.code !== 0) throw new Error(up.message || '上传失败')
            this.profile = await put('/api/profile', { avatar_file_id: up.data.id })
            this.toast('头像已更新')
          } catch (err) {
            this.toast(err.message || '头像更新失败')
          } finally {
            uni.hideLoading()
          }
        }
      })
    },
    goUpdatePassword() {
      uni.navigateTo({ url: '/pages/profile/update-password' })
    }
  }
}
</script>

<style lang="scss" scoped>
.profile-page {
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
  margin-bottom: 32rpx;
}
.card-core {
  background: $surface;
  border-radius: calc(#{$radius-card} - 12rpx);
  box-shadow: inset 0 2rpx 0 rgba(255, 255, 255, 0.6);
  padding: 32rpx;
}

/* 头像区 */
.head-core {
  display: flex;
  align-items: center;
  gap: 28rpx;
}
.avatar {
  width: 128rpx;
  height: 128rpx;
  border-radius: 50%;
  border: 2rpx solid $line;
  background: $brand-soft;
}
.avatar-empty {
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar-text {
  font-size: 56rpx;
  color: $brand;
  font-weight: 600;
}
.head-info {
  flex: 1;
}
.head-name {
  display: block;
  font-size: $fs-20;
  font-weight: 600;
  color: $ink;
}
.head-tags {
  display: flex;
  gap: 12rpx;
  margin-top: 12rpx;
  flex-wrap: wrap;
}
.tag {
  font-size: $fs-12;
  color: $brand;
  background: $brand-soft;
  border-radius: $radius-pill;
  padding: 4rpx 20rpx;
}
.tag-muted {
  color: $ink-2;
  background: $bg;
}
.tag-course {
  color: $ink-2;
  background: $bg;
}
.head-sub {
  display: block;
  margin-top: 12rpx;
  font-size: $fs-12;
  color: $ink-2;
}

/* 档案信息 */
.row {
  display: flex;
  align-items: center;
  padding: 20rpx 0;
  border-bottom: 2rpx solid $line;
}
.row:last-child {
  border-bottom: none;
}
.row-col {
  flex-direction: column;
  align-items: flex-start;
}
.row-label {
  width: 160rpx;
  font-size: $fs-14;
  color: $ink-2;
  flex-shrink: 0;
}
.row-value {
  flex: 1;
  font-size: $fs-14;
  color: $ink;
  text-align: right;
}
.course-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
  margin-top: 12rpx;
}

/* 手机号编辑 */
.edit-title {
  font-size: $fs-14;
  color: $ink-2;
  margin-bottom: 20rpx;
}
.edit-row {
  display: flex;
  align-items: center;
  gap: 20rpx;
}
.edit-input {
  flex: 1;
  height: 80rpx;
  padding: 0 24rpx;
  background: $bg;
  border-radius: $radius-ctrl;
  font-size: $fs-14;
  color: $ink;
}
.edit-placeholder {
  color: $ink-2;
}
.btn {
  height: 80rpx;
  padding: 0 40rpx;
  border-radius: $radius-ctrl;
  font-size: $fs-14;
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

/* 账号操作 */
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
  font-size: $fs-14;
  color: $ink;
}
.op-arrow {
  font-size: $fs-20;
  color: $ink-2;
}
</style>
