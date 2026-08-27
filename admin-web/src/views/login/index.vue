<template>
  <div class="login-page">
    <div class="card-shell login-card">
      <div class="card-core login-core">
        <div class="login-brand">
          <div class="login-logo">
            <div class="login-logo-inner"></div>
          </div>
          <div class="login-title">智慧校园 · 管理后台</div>
          <div class="login-sub">课表 · 成绩 · 公告 · 请假，一站式管理</div>
        </div>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          size="large"
          @keyup.enter="onLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="管理员账号"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              :prefix-icon="Lock"
              show-password
            />
          </el-form-item>
          <el-button
            type="primary"
            class="login-btn"
            :loading="loading"
            @click="onLogin"
          >
            {{ loading ? '登录中...' : '登 录' }}
          </el-button>
        </el-form>
      </div>
    </div>
    <div class="login-footer">智慧校园信息管理系统 · 管理端</div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '../../stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const formRef = ref()
const loading = ref(false)
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入管理员账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

async function onLogin() {
  await formRef.value.validate()
  loading.value = true
  try {
    await userStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (err) {
    ElMessage.error(err.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: $bg;
  padding: 20px;
}

.login-card {
  width: 380px;
}

.login-core {
  padding: 36px 32px;
}

.login-brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 28px;
}

.login-logo {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  background: $brand-soft;
  border: 1px solid $brand;
  padding: 5px;
  margin-bottom: 16px;
}

.login-logo-inner {
  width: 100%;
  height: 100%;
  border-radius: 12px;
  background: linear-gradient(135deg, $brand, $brand-deep);
}

.login-title {
  font-size: $fs-20;
  font-weight: 600;
  color: $ink;
  letter-spacing: 2px;
}

.login-sub {
  margin-top: 8px;
  font-size: $fs-13;
  color: $ink-2;
}

.login-btn {
  width: 100%;
  height: 44px;
  font-size: $fs-16;
  border-radius: $radius-pill;
  margin-top: 8px;
}

.login-footer {
  margin-top: 24px;
  font-size: $fs-12;
  color: $ink-2;
}
</style>
