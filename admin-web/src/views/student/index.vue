<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">学生管理</div>
        <div class="page-desc">学生档案与登录账号联动（5.3.7，方案 B：创建时自动开通账号）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增学生</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索学号/姓名/班级" clearable @keyup.enter="load" @clear="load" />
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="student_no" label="学号" min-width="110" />
          <el-table-column prop="nick_name" label="姓名" min-width="90" />
          <el-table-column prop="username" label="登录账号" min-width="110" />
          <el-table-column prop="class_name" label="班级" min-width="120" />
          <el-table-column prop="enroll_year" label="入学年份" width="90" />
          <el-table-column prop="create_time" label="创建时间" min-width="150" />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
              <el-button link type="danger" @click="onRemove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          class="pager"
          layout="total, prev, pager, next, sizes"
          :total="total"
          :page-size="query.page_size"
          :current-page="query.page"
          :page-sizes="[10, 20, 50]"
          @current-change="(p) => { query.page = p; load() }"
          @size-change="(s) => { query.page_size = s; query.page = 1; load() }"
        />
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑学生' : '新增学生'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="学号" prop="student_no">
          <el-input v-model="form.student_no" placeholder="留空自动生成（同时作为登录账号）" :disabled="!!form.id" />
        </el-form-item>
        <el-form-item label="姓名" prop="nick_name">
          <el-input v-model="form.nick_name" placeholder="学生姓名" />
        </el-form-item>
        <el-form-item label="班级" prop="class_id">
          <el-select v-model="form.class_id" placeholder="选择班级" clearable filterable style="width: 100%">
            <el-option v-for="c in classOptions" :key="c.id" :label="c.class_name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="入学年份" prop="enroll_year">
          <el-input v-model="form.enroll_year" placeholder="如：2026" />
        </el-form-item>
        <el-form-item v-if="!form.id" label="初始密码" prop="password">
          <el-input v-model="form.password" placeholder="留空默认 123456" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { studentApi, classApi } from '../../api/modules'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const classOptions = ref([])

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, student_no: '', nick_name: '', class_id: null, enroll_year: '', password: ''
})
const rules = {
  nick_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  class_id: [{ required: true, message: '请选择班级', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const data = await studentApi.list({
      page: query.page,
      page_size: query.page_size,
      search: query.keyword || undefined
    })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const classes = await classApi.list({ page_size: 200 })
  classOptions.value = classes.results || []
}

function openDialog(row) {
  Object.assign(form, row
    ? {
        id: row.id, student_no: row.student_no, nick_name: row.nick_name,
        class_id: row.class_id, enroll_year: row.enroll_year, password: ''
      }
    : { id: null, student_no: '', nick_name: '', class_id: null, enroll_year: '', password: '' })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      student_no: form.student_no, nick_name: form.nick_name,
      class_id: form.class_id, enroll_year: form.enroll_year
    }
    if (form.id) {
      await studentApi.update(form.id, payload)
      ElMessage.success('学生已更新')
    } else {
      await studentApi.create({ ...payload, password: form.password || undefined })
      ElMessage.success('学生已创建（登录账号已自动开通）')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    // request 已 toast
  } finally {
    saving.value = false
  }
}

function onRemove(row) {
  ElMessageBox.confirm(`确定删除学生「${row.nick_name}（${row.student_no}）」吗？其登录账号将同时停用。`, '提示', { type: 'warning' })
    .then(async () => {
      await studentApi.remove(row.id)
      ElMessage.success('已删除')
      load()
    })
    .catch(() => {})
}

onMounted(() => {
  load()
  loadOptions()
})
</script>

<style lang="scss" scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
