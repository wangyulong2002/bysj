<template>
  <view class="ann-page">
    <!-- 类型 Tab（校园/院系/班级，T3-4） -->
    <view class="card-shell">
      <view class="card-core tab-core">
        <view
          v-for="t in tabs"
          :key="t.value"
          class="tab-item"
          :class="{ active: currentType === t.value }"
          @tap="onTab(t.value)"
        >
          <text class="tab-text">{{ t.name }}</text>
        </view>
      </view>
    </view>

    <!-- 关键字搜索（T3-4） -->
    <view class="card-shell search-shell">
      <view class="card-core search-core">
        <input
          v-model="keyword"
          class="search-input"
          style="display:block;"
          placeholder="搜索公告标题"
          placeholder-class="search-ph"
          confirm-type="search"
          @confirm="onSearch"
        />
        <view class="search-btn" @tap="onSearch">
          <text class="search-btn-text">搜索</text>
        </view>
      </view>
    </view>

    <!-- 公告列表 -->
    <view v-if="list.length" class="ann-list">
      <view
        v-for="a in list"
        :key="a.id"
        class="card-shell"
        @tap="goDetail(a.id)"
      >
        <view class="card-core ann-card">
          <view class="ann-head">
            <view class="ann-tags">
              <text v-if="a.is_top === '1'" class="tag tag-top">置顶</text>
              <text class="tag" :class="tagClass(a.ann_type)">{{ a.ann_type_name }}</text>
            </view>
            <text class="ann-time">{{ formatTime(a.publish_time) }}</text>
          </view>
          <text class="ann-title">{{ a.title }}</text>
          <text v-if="a.content" class="ann-excerpt">{{ a.content }}</text>
        </view>
      </view>
      <view class="list-footer">
        <text class="footer-text">
          {{ hasMore ? '上拉加载更多' : (list.length ? '— 已全部加载 —' : '') }}
        </text>
      </view>
    </view>

    <!-- 空态 / 加载态 -->
    <view v-if="loaded && !list.length" class="empty">
      <text class="empty-title">暂无公告</text>
      <text class="empty-sub">换个类型或关键字试试</text>
    </view>
    <view v-if="!loaded" class="empty">
      <text class="empty-sub">公告加载中...</text>
    </view>
  </view>
</template>

<script>
import { get } from '../../utils/request'

const PAGE_SIZE = 10

export default {
  data() {
    return {
      tabs: [
        { value: '', name: '全部' },
        { value: '1', name: '校园' },
        { value: '2', name: '院系' },
        { value: '3', name: '班级' }
      ],
      currentType: '',
      keyword: '',
      list: [],
      pageNum: 1,
      total: 0,
      hasMore: true,
      loaded: false
    }
  },
  onLoad() {
    this.loadList(true)
  },
  onReachBottom() {
    // 触底加载下一页（T3-4 分页）
    if (this.hasMore) {
      this.loadList(false)
    }
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    tagClass(type) {
      // 类型标签配色（校园/院系/班级）
      return { '1': 'tag-school', '2': 'tag-dept', '3': 'tag-class' }[type] || ''
    },
    formatTime(t) {
      // 发布时间展示：YYYY-MM-DD
      if (!t) return ''
      return String(t).slice(0, 10)
    },
    async loadList(reset) {
      if (reset) {
        this.pageNum = 1
        this.list = []
        this.hasMore = true
        this.loaded = false
      }
      try {
        const data = await get('/api/announcements', {
          ann_type: this.currentType || undefined,
          keyword: this.keyword || undefined,
          page_num: this.pageNum,
          page_size: PAGE_SIZE
        })
        const items = data.list || []
        this.total = data.total || 0
        this.list = reset ? items : this.list.concat(items)
        this.hasMore = this.list.length < this.total
        this.pageNum += 1
      } catch (err) {
        this.toast(err.message || '公告加载失败')
      } finally {
        this.loaded = true
      }
    },
    onTab(type) {
      // 切换类型 Tab：重置并重新加载
      if (this.currentType === type) return
      this.currentType = type
      this.loadList(true)
    },
    onSearch() {
      // 关键字搜索：重置并重新加载
      this.loadList(true)
    },
    goDetail(id) {
      // 跳转公告详情
      uni.navigateTo({ url: `/pages/announcement/detail?id=${id}` })
    }
  }
}
</script>

<style lang="scss" scoped>
.ann-page {
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
  margin-bottom: 24rpx;
}
.card-core {
  background: $surface;
  border-radius: calc(#{$radius-card} - 12rpx);
  box-shadow: inset 0 2rpx 0 rgba(255, 255, 255, 0.6);
  padding: 24rpx;
}

/* ===== 类型 Tab ===== */
.tab-core {
  display: flex;
  background: $surface;
  padding: 8rpx;
}
.tab-item {
  flex: 1;
  text-align: center;
  padding: 16rpx 0;
  border-radius: $radius-ctrl;
  transition: background 0.25s $ease-premium, transform 0.25s $ease-premium;
  &:active {
    transform: scale(0.96);
  }
  &.active {
    background: $brand-soft;
  }
}
.tab-text {
  font-size: $fs-14;
  color: $ink-2;
  .tab-item.active & {
    color: $brand-deep;
    font-weight: 600;
  }
}

/* ===== 搜索 ===== */
.search-core {
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 16rpx 16rpx 16rpx 24rpx;
}
.search-input {
  flex: 1;
  font-size: $fs-14;
  color: $ink;
  height: 72rpx;
}
.search-ph {
  color: $ink-2;
}
.search-btn {
  padding: 12rpx 28rpx;
  background: $brand;
  border-radius: $radius-pill;
  transition: transform 0.25s $ease-premium, opacity 0.25s $ease-premium;
  &:active {
    transform: scale(0.94);
    opacity: 0.9;
  }
}
.search-btn-text {
  color: #ffffff;
  font-size: $fs-12;
  font-weight: 600;
}

/* ===== 公告卡片 ===== */
.ann-card {
  padding: 24rpx;
}
.ann-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.ann-tags {
  display: flex;
  align-items: center;
  gap: 12rpx;
}
.tag {
  font-size: 20rpx;
  padding: 4rpx 14rpx;
  border-radius: $radius-pill;
  background: $bg;
  color: $ink-2;
  border: 2rpx solid $line;
}
.tag-top {
  color: $warn;
  border-color: rgba(217, 119, 6, 0.35);
  background: rgba(254, 243, 199, 0.5);
}
.tag-school {
  color: $brand-deep;
  border-color: rgba(14, 116, 144, 0.3);
  background: $brand-soft;
}
.tag-dept {
  color: $brand-deep;
  border-color: rgba(14, 116, 144, 0.3);
  background: $brand-soft;
}
.tag-class {
  color: $brand-deep;
  border-color: rgba(14, 116, 144, 0.3);
  background: $brand-soft;
}
.ann-time {
  font-size: 20rpx;
  color: $ink-2;
}
.ann-title {
  display: block;
  margin-top: 16rpx;
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
  line-height: 1.45;
}
.ann-excerpt {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  margin-top: 10rpx;
  font-size: $fs-12;
  color: $ink-2;
  line-height: 1.6;
}

/* ===== 列表底部 ===== */
.list-footer {
  padding: 20rpx 0 40rpx;
  text-align: center;
}
.footer-text {
  font-size: $fs-12;
  color: $ink-2;
}

/* ===== 空态 ===== */
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
