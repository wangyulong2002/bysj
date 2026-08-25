<script>
import { STORAGE_KEYS } from './utils/config'

export default {
  onLaunch() {
    // 应用启动：恢复登录态（token 持久化，刷新后保持登录态，T1-7）
    const token = uni.getStorageSync(STORAGE_KEYS.token)
    if (token) {
      this.globalData.token = token
    }
    this.globalData.userInfo = uni.getStorageSync(STORAGE_KEYS.userInfo) || null
  },
  globalData: {
    token: '',
    userInfo: null
  }
}
</script>

<style>
/* 青岚校园（Teal Campus，设计报告 7.3）：全局基础样式 */
page {
  background-color: #F8FAFC;
  color: #0F172A;
  font-size: 28rpx;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}

view,
text,
input,
button {
  box-sizing: border-box;
}

/* 按钮去默认样式，统一交给页面组件控制 */
button::after {
  border: none;
}
</style>
