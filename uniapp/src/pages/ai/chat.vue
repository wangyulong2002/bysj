<template>
  <view class="chat-page">
    <!-- 消息区（T7-6：游客公开，8.5） -->
    <scroll-view
      class="msg-scroll"
      scroll-y
      :scroll-top="scrollTop"
      scroll-with-animation
    >
      <view class="msg-list">
        <!-- 欢迎语 + 推荐问题（首屏，降低输入门槛） -->
        <view class="ai-welcome">
          <text class="welcome-title">你好，我是 AI 校园助手</text>
          <text class="welcome-sub">可以问我宿舍、食堂、选课、奖学金、报到流程等校园问题～</text>
          <view class="suggest-wrap">
            <view
              v-for="q in suggests"
              :key="q"
              class="suggest-chip"
              @tap="send(q)"
            >
              <text class="suggest-text">{{ q }}</text>
            </view>
          </view>
        </view>

        <view v-for="(m, i) in messages" :key="i" class="msg-block">
          <!-- 用户气泡（右） -->
          <view v-if="m.role === 'user'" class="row row-user">
            <view class="bubble bubble-user">
              <text class="bubble-text">{{ m.text }}</text>
            </view>
          </view>

          <!-- AI 气泡（左） -->
          <view v-else class="row row-ai">
            <view class="bubble bubble-ai" :class="{ 'bubble-refuse': m.refused }">
              <text class="bubble-text">{{ m.text }}</text>
            </view>
          </view>

          <!-- 引用来源卡片（拒答态不渲染，T7-6/8.4.1） -->
          <view v-if="m.role === 'ai' && !m.refused && m.sources && m.sources.length" class="sources">
            <view
              v-for="(s, si) in m.sources"
              :key="si"
              class="source-chip"
              @tap="openSource(s)"
            >
              <text class="source-tag" :class="s.type === 'knowledge' ? 'tag-knowledge' : 'tag-announcement'">
                {{ s.type === 'knowledge' ? '知识库' : '公告' }}
              </text>
              <text class="source-title">{{ s.title }}</text>
              <text v-if="canJump(s)" class="source-arrow">›</text>
            </view>
          </view>

          <!-- 反馈（赞/踩，T7-5 接口） -->
          <view v-if="m.role === 'ai' && !m.refused && m.logId" class="fb-row">
            <text v-if="m.feedbackDone" class="fb-done">已反馈，谢谢～</text>
            <template v-else>
              <view class="fb-btn" @tap="onFeedback(i, 1)"><text class="fb-text">👍 有用</text></view>
              <view class="fb-btn" @tap="onFeedback(i, 2)"><text class="fb-text">👎 没用</text></view>
            </template>
          </view>

          <!-- 拒答态：引导推荐问题（v2.6/8.4.1） -->
          <view v-if="m.role === 'ai' && m.refused" class="refuse-guide">
            <text v-if="m.refuseReason === 'out_of_scope'" class="guide-hint">
              我可以回答：宿舍 / 食堂 / 选课 / 奖学金 / 报到流程…
            </text>
            <view class="suggest-wrap">
              <view
                v-for="q in suggestGuide"
                :key="q"
                class="suggest-chip"
                @tap="send(q)"
              >
                <text class="suggest-text">{{ q }}</text>
              </view>
            </view>
          </view>

          <!-- 5001 降级：展示检索资料列表（不编造） -->
          <view v-if="m.role === 'ai' && m.degraded && m.sources && m.sources.length" class="sources">
            <view v-for="(s, si) in m.sources" :key="'d' + si" class="source-chip" @tap="openSource(s)">
              <text class="source-tag" :class="s.type === 'knowledge' ? 'tag-knowledge' : 'tag-announcement'">
                {{ s.type === 'knowledge' ? '知识库' : '公告' }}
              </text>
              <text class="source-title">{{ s.title }}</text>
              <text v-if="canJump(s)" class="source-arrow">›</text>
            </view>
          </view>
        </view>

        <!-- 加载态（骨架屏，禁转圈 spinner） -->
        <view v-if="pending" class="row row-ai">
          <view class="bubble bubble-ai bubble-typing">
            <view class="dot"></view>
            <view class="dot"></view>
            <view class="dot"></view>
          </view>
        </view>
      </view>
    </scroll-view>

    <!-- 输入区 -->
    <view class="input-bar">
      <view class="input-shell">
        <input
          v-model="draft"
          class="chat-input"
          style="display:block;"
          :maxlength="500"
          placeholder="输入你的校园问题（最多 500 字）"
          placeholder-class="chat-ph"
          confirm-type="send"
          :disabled="pending"
          @confirm="onSend"
        />
        <view class="send-btn" :class="{ 'send-disabled': pending || !draft.trim() }" @tap="onSend">
          <text class="send-text">发送</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { get, post } from '../../utils/request'

const MAX_QUESTION = 500

/** 生成会话 id（campus_rag_log.session_id，为 T7-8 多轮预留） */
function genSessionId() {
  const s4 = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).slice(1)
  return `${s4()}${s4()}-${s4()}-${s4()}-${s4()}-${s4()}${s4()}${s4()}`
}

export default {
  data() {
    return {
      suggests: [],
      suggestGuide: [],
      messages: [],
      draft: '',
      pending: false,
      sessionId: '',
      scrollTop: 0
    }
  },
  onLoad() {
    this.sessionId = genSessionId()
    this.loadSuggests()
  },
  methods: {
    toast(title) {
      uni.showToast({ title, icon: 'none' })
    },
    async loadSuggests() {
      // 首屏推荐问题（T7-5 接口，公开）
      try {
        const data = await get('/api/rag/suggest')
        this.suggests = data.items || []
        this.suggestGuide = this.suggests.slice(0, 3)
      } catch (err) {
        // 推荐问题加载失败不阻塞问答主流程
      }
    },
    onSend() {
      const q = (this.draft || '').trim()
      if (!q) {
        this.toast('请输入问题')
        return
      }
      if (q.length > MAX_QUESTION) {
        this.toast('问题不能超过 500 字')
        return
      }
      this.send(q)
    },
    async send(question) {
      if (this.pending) return
      this.draft = ''
      this.messages.push({ role: 'user', text: question })
      this.pending = true
      this.scrollToBottom()
      try {
        const data = await post('/api/rag/chat', {
          question,
          session_id: this.sessionId
        })
        this.messages.push({
          role: 'ai',
          text: data.answer,
          refused: !!data.refused,
          refuseReason: data.refuse_reason,
          sources: data.sources || [],
          logId: data.log_id,
          feedbackDone: false
        })
      } catch (err) {
        if (err.code === 4291) {
          this.toast('提问过于频繁，请稍后再试')
        } else if (err.code === 5001) {
          // 降级（9.7）：不编造答案，展示检索资料列表
          this.messages.push({
            role: 'ai',
            text: 'AI 服务暂不可用，以下为相关资料：',
            degraded: true,
            sources: (err.data && err.data.sources) || [],
            refused: false,
            logId: null
          })
        } else if (err.code === 5002) {
          this.toast('AI 助手暂不可用，请稍后再试')
        } else {
          this.toast(err.message || '问答失败，请稍后再试')
        }
      } finally {
        this.pending = false
        this.scrollToBottom()
      }
    },
    async onFeedback(index, feedback) {
      const m = this.messages[index]
      try {
        await post('/api/rag/feedback', { log_id: m.logId, feedback })
        m.feedbackDone = true
      } catch (err) {
        this.toast(err.message || '反馈失败')
      }
    },
    canJump(s) {
      // knowledge v1 无应用端详情页（6.2 未定义）→ 仅展示不跳转
      return !!(s && s.url && s.type === 'announcement')
    },
    openSource(s) {
      if (!this.canJump(s)) return
      // url 形如 /api/announcements/{id}
      const id = String(s.url).split('/').pop()
      if (id) {
        uni.navigateTo({ url: `/pages/announcement/detail?id=${id}` })
      }
    },
    scrollToBottom() {
      // 置底：取一个递增的大值触发 scroll-view 滚动
      this.$nextTick(() => {
        this.scrollTop = this.messages.length * 1000 + 9999
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.chat-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: $bg;
}

/* ===== 消息区 ===== */
.msg-scroll {
  flex: 1;
  height: 0;
}
.msg-list {
  padding: 32rpx;
  padding-bottom: 48rpx;
}

/* 欢迎语 + 推荐问题 */
.ai-welcome {
  background: rgba(255, 255, 255, 0.6);
  border: 2rpx solid $line;
  border-radius: $radius-card;
  padding: 12rpx;
  box-shadow: $shadow-soft;
  margin-bottom: 32rpx;
}
.welcome-title {
  display: block;
  margin: 20rpx 20rpx 8rpx;
  font-size: $fs-16;
  font-weight: 600;
  color: $ink;
}
.welcome-sub {
  display: block;
  margin: 0 20rpx 20rpx;
  font-size: $fs-12;
  color: $ink-2;
  line-height: 1.6;
}
.suggest-wrap {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  padding: 0 20rpx 20rpx;
}
.suggest-chip {
  padding: 12rpx 24rpx;
  background: $brand-soft;
  border: 2rpx solid rgba(14, 116, 144, 0.3);
  border-radius: $radius-pill;
  transition: transform 0.25s $ease-premium;
  &:active {
    transform: scale(0.95);
  }
}
.suggest-text {
  font-size: $fs-12;
  color: $brand-deep;
}

/* ===== 气泡 ===== */
.msg-block {
  margin-bottom: 24rpx;
}
.row {
  display: flex;
}
.row-user {
  justify-content: flex-end;
}
.row-ai {
  justify-content: flex-start;
}
.bubble {
  max-width: 82%;
  padding: 20rpx 28rpx;
  font-size: $fs-14;
  line-height: 1.6;
  word-break: break-all;
}
.bubble-user {
  background: $brand;
  color: #ffffff;
  border-radius: $radius-card $radius-card 8rpx $radius-card;
  box-shadow: $shadow-soft;
}
.bubble-ai {
  background: $surface;
  color: $ink;
  border: 2rpx solid $line;
  border-radius: $radius-card $radius-card $radius-card 8rpx;
  box-shadow: $shadow-soft;
}
.bubble-refuse {
  background: $brand-soft;
  border-color: rgba(14, 116, 144, 0.3);
  color: $brand-deep;
}
.bubble-text {
  font-size: $fs-14;
}

/* 打字中（骨架点，禁 spinner） */
.bubble-typing {
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 50%;
  background: $ink-2;
  opacity: 0.4;
  animation: blink 1.2s infinite $ease-premium;
}
.dot:nth-child(2) {
  animation-delay: 0.2s;
}
.dot:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%, 100% { opacity: 0.25; transform: translateY(0); }
  50% { opacity: 0.8; transform: translateY(-4rpx); }
}

/* ===== 引用来源卡片 ===== */
.sources {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
  margin-top: 16rpx;
}
.source-chip {
  display: flex;
  align-items: center;
  gap: 12rpx;
  padding: 14rpx 20rpx;
  background: $surface;
  border: 2rpx solid $line;
  border-radius: $radius-ctrl;
  box-shadow: $shadow-soft;
  transition: transform 0.25s $ease-premium;
  &:active {
    transform: scale(0.98);
  }
}
.source-tag {
  flex-shrink: 0;
  font-size: 20rpx;
  padding: 2rpx 12rpx;
  border-radius: $radius-pill;
}
.tag-announcement {
  color: $brand-deep;
  background: $brand-soft;
  border: 2rpx solid rgba(14, 116, 144, 0.3);
}
.tag-knowledge {
  color: $ink-2;
  background: $bg;
  border: 2rpx solid $line;
}
.source-title {
  flex: 1;
  font-size: $fs-12;
  color: $ink;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.source-arrow {
  font-size: $fs-16;
  color: $brand-deep;
}

/* ===== 反馈 ===== */
.fb-row {
  display: flex;
  align-items: center;
  gap: 16rpx;
  margin-top: 12rpx;
}
.fb-btn {
  padding: 6rpx 20rpx;
  border: 2rpx solid $line;
  border-radius: $radius-pill;
  background: $surface;
  transition: transform 0.25s $ease-premium;
  &:active {
    transform: scale(0.94);
  }
}
.fb-text {
  font-size: 20rpx;
  color: $ink-2;
}
.fb-done {
  font-size: 20rpx;
  color: $ink-2;
}

/* ===== 拒答引导 ===== */
.refuse-guide {
  margin-top: 16rpx;
  padding: 0 8rpx;
}
.guide-hint {
  display: block;
  margin-bottom: 12rpx;
  font-size: $fs-12;
  color: $ink-2;
}
.refuse-guide .suggest-wrap {
  padding: 0;
}

/* ===== 输入区 ===== */
.input-bar {
  padding: 16rpx 32rpx calc(16rpx + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, 0.6);
  border-top: 2rpx solid $line;
}
.input-shell {
  display: flex;
  align-items: center;
  gap: 16rpx;
  background: $surface;
  border: 2rpx solid $line;
  border-radius: $radius-pill;
  padding: 8rpx 8rpx 8rpx 28rpx;
  box-shadow: $shadow-soft;
}
.chat-input {
  flex: 1;
  height: 72rpx;
  font-size: $fs-14;
  color: $ink;
}
.chat-ph {
  color: #94a3b8;
}
.send-btn {
  padding: 14rpx 32rpx;
  background: $brand;
  border-radius: $radius-pill;
  transition: transform 0.25s $ease-premium, opacity 0.25s $ease-premium;
  &:active {
    transform: scale(0.94);
  }
}
.send-disabled {
  opacity: 0.5;
}
.send-text {
  font-size: $fs-14;
  font-weight: 600;
  color: #ffffff;
}
</style>
