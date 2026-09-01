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
              <text v-if="m.text" class="bubble-text">{{ m.text }}</text>
              <!-- T7-8：流式首帧未到时显示打字态（骨架点，禁转圈） -->
              <view v-if="m.streaming && !m.text" class="dot-row">
                <view class="dot"></view>
                <view class="dot"></view>
                <view class="dot"></view>
              </view>
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
            <!-- :key 用简单索引（勿用字符串拼接表达式：uni-app 小程序编译器会将其
                 展开进 data-event-opts 生成非法 token，如 'd'+si；本 v-for 与上方
                 正常来源列表分属不同 v-if 分支，同索引即唯一） -->
            <view v-for="(s, si) in m.sources" :key="si" class="source-chip" @tap="openSource(s)">
              <text class="source-tag" :class="s.type === 'knowledge' ? 'tag-knowledge' : 'tag-announcement'">
                {{ s.type === 'knowledge' ? '知识库' : '公告' }}
              </text>
              <text class="source-title">{{ s.title }}</text>
              <text v-if="canJump(s)" class="source-arrow">›</text>
            </view>
          </view>
        </view>

        <!-- 加载态（骨架屏，禁转圈 spinner；流式气泡出现后由其打字态接管） -->
        <view v-if="typing" class="row row-ai">
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
import { API_BASE_URL } from '../../utils/config'

const MAX_QUESTION = 500

/** 生成会话 id（campus_rag_log.session_id，为 T7-8 多轮预留） */
function genSessionId() {
  const s4 = () => Math.floor((1 + Math.random()) * 0x10000).toString(16).slice(1)
  return `${s4()}${s4()}-${s4()}-${s4()}-${s4()}-${s4()}${s4()}${s4()}`
}

/** 在字节数组中查找 SSE 帧分隔 "\n\n"（0x0A0A），找不到返回 -1。
 * 0x0A 不会出现在 UTF-8 多字节序列内部，字节级分帧跨 chunk 安全（T7-8）。 */
function findDoubleLf(arr) {
  for (let i = 0; i + 1 < arr.length; i++) {
    if (arr[i] === 10 && arr[i + 1] === 10) return i
  }
  return -1
}

/** 完整 UTF-8 字节块 → 字符串（帧级解码，规避小程序无 TextDecoder） */
function utf8ToStr(u8) {
  let out = ''
  let i = 0
  while (i < u8.length) {
    const b = u8[i]
    if (b < 0x80) {
      out += String.fromCharCode(b)
      i += 1
    } else if (b < 0xe0) {
      out += String.fromCharCode(((b & 0x1f) << 6) | (u8[i + 1] & 0x3f))
      i += 2
    } else if (b < 0xf0) {
      out += String.fromCharCode(((b & 0x0f) << 12) | ((u8[i + 1] & 0x3f) << 6) | (u8[i + 2] & 0x3f))
      i += 3
    } else {
      const cp = ((b & 0x07) << 18) | ((u8[i + 1] & 0x3f) << 12) | ((u8[i + 2] & 0x3f) << 6) | (u8[i + 3] & 0x3f)
      out += String.fromCodePoint(cp)
      i += 4
    }
  }
  return out
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
  computed: {
    /** 骨架屏仅在"未收到首个流式帧"阶段显示（流式气泡的打字态接管后隐藏） */
    typing() {
      return this.pending && !this.messages.some((m) => m.role === 'ai' && m.streaming)
    }
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
    /** 发送入口（T7-8）：优先 SSE 流式（POST /api/rag/chat/stream），
     *  平台不支持/建流失败时回退 JSON 通道（原 T7-6 逻辑） */
    send(question) {
      if (this.pending) return
      this.draft = ''
      this.messages.push({ role: 'user', text: question })
      this.pending = true
      this.scrollToBottom()
      this.sendStream(question)
        .then((ok) => (ok ? null : this.sendByJson(question)))
        .then(() => {
          this.pending = false
          this.scrollToBottom()
        })
    },

    /** JSON 通道兜底（T7-6 原逻辑；错误处理与多端一致） */
    async sendByJson(question) {
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
      }
    },

    /** SSE 帧处理（T7-8 分片契约）：delta 增量 / done 权威文本 / error 降级 */
    handleSseFrame(frame, aiMsg) {
      if (frame.type === 'delta') {
        aiMsg.text += frame.content
        this.scrollToBottom()
        return
      }
      if (frame.type === 'done') {
        // done.answer 为 L2/L3 清洗后的权威文本（哨兵拒答/引用清洗时覆盖流式增量）
        if (typeof frame.answer === 'string') aiMsg.text = frame.answer
        aiMsg.sources = frame.sources || []
        aiMsg.refused = !!frame.refused
        aiMsg.refuseReason = frame.refuse_reason || null
        aiMsg.logId = frame.log_id || null
        aiMsg.completed = true
        this.scrollToBottom()
        return
      }
      if (frame.type === 'error') {
        aiMsg.streaming = false
        aiMsg.completed = true
        if (frame.code === 5001) {
          // 降级（9.7）：不编造答案，展示检索资料列表
          aiMsg.text = frame.message || 'AI 服务暂不可用，以下为相关资料：'
          aiMsg.degraded = true
          aiMsg.sources = (frame.data && frame.data.sources) || []
        } else {
          aiMsg.text = frame.message || '问答失败，请稍后再试'
          aiMsg.refused = true
        }
        this.scrollToBottom()
      }
    },

    /** SSE 流式发送（T7-8）：H5 用 fetch+ReadableStream，微信小程序用
     *  uni.request enableChunked（基础库 2.20+）；未收到任何帧时 resolve(false)
     *  交由 JSON 通道兜底。多轮上下文由 sessionId 串联（后端 _load_history）。 */
    sendStream(question) {
      return new Promise((resolve) => {
        const aiMsg = {
          role: 'ai', text: '', refused: false, refuseReason: null,
          sources: [], logId: null, feedbackDone: false,
          degraded: false, streaming: true, completed: false
        }
        this.messages.push(aiMsg)
        this.scrollToBottom()
        let gotFrame = false
        let settled = false
        const handleBlock = (block) => {
          const line = block.split('\n').find((l) => l.indexOf('data:') === 0)
          if (!line) return
          let frame
          try {
            frame = JSON.parse(line.slice(5).trim())
          } catch (e) {
            return
          }
          gotFrame = true
          this.handleSseFrame(frame, aiMsg)
          if (frame.type === 'done' || frame.type === 'error') finish()
        }
        const finish = () => {
          if (settled) return
          settled = true
          aiMsg.streaming = false
          if (!gotFrame) {
            // 无任何帧（不支持/网络失败）：撤占位气泡 → JSON 兜底
            if (!aiMsg.text) {
              const i = this.messages.indexOf(aiMsg)
              if (i !== -1) this.messages.splice(i, 1)
            }
            resolve(false)
          } else {
            if (!aiMsg.completed) aiMsg.text += '\n（连接中断，请重试）'
            resolve(true)
          }
        }
        // #ifdef H5
        fetch(API_BASE_URL + '/api/rag/chat/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question, session_id: this.sessionId })
        }).then((resp) => {
          const ct = resp.headers.get('content-type') || ''
          if (!resp.ok || ct.indexOf('text/event-stream') === -1) {
            // 建流前错误（4001/4291/5002 等）走 JSON 兜底分支统一处理
            return resp.json().then((body) => {
              const err = new Error(body.message || '问答失败，请稍后再试')
              err.code = body.code
              err.data = body.data
              throw err
            })
          }
          const reader = resp.body.getReader()
          const decoder = new TextDecoder('utf-8')
          let buffer = ''
          const pump = () => reader.read().then((r) => {
            if (r.done) {
              finish()
              return
            }
            buffer += decoder.decode(r.value, { stream: true })
            let idx
            while ((idx = buffer.indexOf('\n\n')) !== -1) {
              handleBlock(buffer.slice(0, idx))
              buffer = buffer.slice(idx + 2)
            }
            return pump()
          })
          return pump()
        }).catch(() => finish())
        // #endif
        // #ifdef MP-WEIXIN
        let byteBuf = []
        const task = uni.request({
          url: API_BASE_URL + '/api/rag/chat/stream',
          method: 'POST',
          data: { question, session_id: this.sessionId },
          header: { 'Content-Type': 'application/json' },
          enableChunked: true,   // 基础库 2.20+，onChunkReceived 分片接收
          responseType: 'arraybuffer',
          success: () => finish(),
          fail: () => finish()
        })
        if (task && typeof task.onChunkReceived === 'function') {
          task.onChunkReceived((res) => {
            // 字节级找 "\n\n" 分帧（0x0A 不在 UTF-8 多字节序列内，跨块安全），
            // 帧内字节完整后再解码，规避多字节字符被 chunk 截断
            byteBuf = byteBuf.concat(Array.prototype.slice.call(new Uint8Array(res.data)))
            let idx = findDoubleLf(byteBuf)
            while (idx !== -1) {
              handleBlock(utf8ToStr(byteBuf.slice(0, idx)))
              byteBuf = byteBuf.slice(idx + 2)
              idx = findDoubleLf(byteBuf)
            }
          })
        } else {
          finish()  // 低版本基础库不支持 → JSON 兜底
        }
        // #endif
        // #ifndef H5 || MP-WEIXIN
        finish()  // 其余平台暂不支持流式 → JSON 兜底
        // #endif
      })
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
/* 流式首帧前的行内打字态（T7-8） */
.dot-row {
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
