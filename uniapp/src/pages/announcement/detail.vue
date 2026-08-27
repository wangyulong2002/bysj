<template>
  <view class="detail-page">
    <view v-if="loaded && ann" class="card-shell">
      <view class="card-core detail-card">
        <view class="head-tags">
          <text v-if="ann.is_top === '1'" class="tag tag-top">置顶</text>
          <text class="tag">{{ ann.ann_type_name }}</text>
        </view>
        <text class="title">{{ ann.title }}</text>
        <view class="meta">
          <text class="meta-time">{{ formatTime(ann.publish_time) }}</text>
          <text v-if="ann.publisher_name" class="meta-pub">发布：{{ ann.publisher_name }}</text>
        </view>
        <view class="divider"></view>
        <text class="content">{{ ann.content || '（暂无内容）' }}</text>
      </view>
    </view>

    <view v-if="loaded && !ann" class="empty">
      <text class="empty-title">公告不存在或已下架</text>
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
      ann: null,
      loaded: false
    }
  },
  onLoad(options) {
    this.annId = Number(options.id)
    this.loadDetail()
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    formatTime(t) {
      // 发布时间展示：YYYY-MM-DD HH:mm
      if (!t) return ''
      const s = String(t).replace('T', ' ')
      return s.length >= 16 ? s.slice(0, 16) : s
    },
    async loadDetail() {
      try {
        this.ann = await get(`/api/announcements/${this.annId}`)
        uni.setNavigationBarTitle({ title: this.ann.title || '公告详情' })
      } catch (err) {
        this.toast(err.message || '公告加载失败')
      } finally {
        this.loaded = true
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.detail-page {
  min-height: 100vh;
  padding: 32rpx;
  background: $bg;
}

/* ===== 双边框卡片（青岚校园 7.3）===== */
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
  padding: 40rpx 32rpx;
}

.head-tags {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.tag {
  font-size: 20rpx;
  padding: 4rpx 14rpx;
  border-radius: $radius-pill;
  color: $brand-deep;
  background: $brand-soft;
  border: 2rpx solid rgba(14, 116, 144, 0.3);
}
.tag-top {
  color: $warn;
  border-color: rgba(217, 119, 6, 0.35);
  background: rgba(254, 243, 199, 0.5);
}

.title {
  display: block;
  margin-top: 24rpx;
  font-size: $fs-24;
  font-weight: 600;
  color: $ink;
  line-height: 1.45;
}

.meta {
  display: flex;
  align-items: center;
  gap: 24rpx;
  margin-top: 16rpx;
}
.meta-time,
.meta-pub {
  font-size: $fs-12;
  color: $ink-2;
}

.divider {
  height: 2rpx;
  background: $line;
  margin: 28rpx 0;
}

.content {
  display: block;
  font-size: $fs-14;
  color: $ink;
  line-height: 1.85;
  white-space: pre-wrap;
  word-break: break-all;
}

.empty {
  padding: 160rpx 32rpx;
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
