<template>
  <view class="apply-page">
    <view class="card-shell">
      <view class="card-core">
        <!-- 请假类型 -->
        <view class="type-row">
          <view
            v-for="t in types"
            :key="t.value"
            class="type-item"
            :class="{ active: form.leave_type === t.value }"
            @tap="form.leave_type = t.value"
          >
            <text class="type-text">{{ t.name }}</text>
          </view>
        </view>

        <!-- 起止时间 -->
        <view class="field">
          <text class="field-label">开始时间</text>
          <view class="picker-row">
            <picker mode="date" :value="startDate" @change="onStartDate">
              <view class="picker-item">{{ startDate }}</view>
            </picker>
            <picker mode="time" :value="startTime" @change="onStartTime">
              <view class="picker-item">{{ startTime }}</view>
            </picker>
          </view>
        </view>
        <view class="field">
          <text class="field-label">结束时间</text>
          <view class="picker-row">
            <picker mode="date" :value="endDate" @change="onEndDate">
              <view class="picker-item">{{ endDate }}</view>
            </picker>
            <picker mode="time" :value="endTime" @change="onEndTime">
              <view class="picker-item">{{ endTime }}</view>
            </picker>
          </view>
        </view>

        <!-- 事由 -->
        <view class="field">
          <text class="field-label">请假事由</text>
          <textarea
            class="reason-input"
            v-model="form.reason"
            placeholder="请填写请假事由（500 字内）"
            maxlength="500"
          />
        </view>

        <!-- 附件 -->
        <view class="field">
          <text class="field-label">附件</text>
          <view class="attach-row">
            <button class="attach-btn" size="mini" @click="onChooseImage">选择图片</button>
            <text class="attach-name">{{ attachmentName || '可选' }}</text>
          </view>
        </view>

        <button class="submit-btn" :disabled="submitting" @click="onSubmit">
          {{ submitting ? '提交中...' : '提交申请' }}
        </button>
      </view>
    </view>
  </view>
</template>

<script>
import { post } from '../../utils/request'

function pad(n) {
  return n < 10 ? `0${n}` : `${n}`
}

export default {
  data() {
    const now = new Date()
    return {
      types: [
        { value: '1', name: '事假' },
        { value: '2', name: '病假' },
        { value: '3', name: '其他' }
      ],
      form: { leave_type: '1', reason: '', attachment_id: null },
      startDate: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
      startTime: '08:00',
      endDate: `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`,
      endTime: '18:00',
      attachmentName: '',
      submitting: false
    }
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    onStartDate(e) { this.startDate = e.detail.value },
    onStartTime(e) { this.startTime = e.detail.value },
    onEndDate(e) { this.endDate = e.detail.value },
    onEndTime(e) { this.endTime = e.detail.value },
    onChooseImage() {
      uni.chooseImage({
        count: 1,
        success: (res) => {
          const file = res.tempFiles[0]
          uni.uploadFile({
            url: `${require('../../utils/config').API_BASE_URL}/api/files`,
            filePath: file.path,
            name: 'file',
            header: { Authorization: `Bearer ${uni.getStorageSync('token')}` },
            success: (up) => {
              const body = JSON.parse(up.data)
              if (body.code === 0) {
                this.form.attachment_id = body.data.id
                this.attachmentName = body.data.original_name || '已上传'
              } else {
                this.toast(body.message || '上传失败')
              }
            },
            fail: () => this.toast('上传失败')
          })
        }
      })
    },
    async onSubmit() {
      if (!this.form.reason.trim()) {
        this.toast('请填写请假事由')
        return
      }
      this.submitting = true
      try {
        const data = await post('/api/leaves', {
          leave_type: this.form.leave_type,
          reason: this.form.reason.trim(),
          start_time: `${this.startDate}T${this.startTime}:00+08:00`,
          end_time: `${this.endDate}T${this.endTime}:00+08:00`,
          attachment_id: this.form.attachment_id || undefined
        })
        this.toast(`已提交（${data.total_days} 天）`)
        setTimeout(() => uni.navigateBack(), 800)
      } catch (err) {
        this.toast(err.message || '提交失败')
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.apply-page {
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
}
.card-core {
  background: $surface;
  border-radius: calc(#{$radius-card} - 12rpx);
  box-shadow: inset 0 2rpx 0 rgba(255, 255, 255, 0.6);
  padding: 32rpx 24rpx;
}

.type-row {
  display: flex;
  gap: 16rpx;
  margin-bottom: 24rpx;
}
.type-item {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
}
.type-item.active {
  background: $brand-soft;
  border-color: $brand;
}
.type-text {
  font-size: $fs-14;
  color: $ink-2;
  .type-item.active & {
    color: $brand-deep;
    font-weight: 600;
  }
}

.field {
  margin-bottom: 24rpx;
}
.field-label {
  display: block;
  margin-bottom: 10rpx;
  font-size: $fs-12;
  color: $ink-2;
}
.picker-row {
  display: flex;
  gap: 16rpx;
}
.picker-item {
  padding: 14rpx 20rpx;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  font-size: $fs-14;
  color: $ink;
}

.reason-input {
  width: 100%;
  height: 140rpx;
  padding: 16rpx;
  background: $bg;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  font-size: $fs-14;
  color: $ink;
}

.attach-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.attach-btn {
  margin: 0;
  background: $brand-soft;
  color: $brand-deep;
  border-radius: $radius-pill;
  font-size: $fs-12;
}
.attach-name {
  font-size: $fs-12;
  color: $ink-2;
}

.submit-btn {
  margin-top: 16rpx;
  background: $brand;
  color: #ffffff;
  border-radius: $radius-pill;
  font-size: $fs-16;
}
</style>
