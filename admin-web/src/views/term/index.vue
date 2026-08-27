<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">学期管理</div>
        <div class="page-desc">学期与当前学期切换（设计 5.3.6 / 5.1）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增学期</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索学期名称" clearable @keyup.enter="load" @clear="load" />
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="term_name" label="学期名称" min-width="200" />
          <el-table-column prop="start_date" label="开始日期" width="110" />
          <el-table-column prop="end_date" label="结束日期" width="110" />
          <el-table-column prop="total_weeks" label="总周数" width="80" />
          <el-table-column label="当前学期" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.is_current === '1'" type="success" effect="light">当前</el-tag>
              <el-tag v-else type="info" effect="plain">否</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.is_current !== '1'" link type="primary" @click="onSetCurrent(row)">设为当前</el-button>
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑学期' : '新增学期'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="学期名称" prop="term_name">
          <el-input v-model="form.term_name" placeholder="如：2025-2026学年第一学期" />
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker v-model="form.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="总周数" prop="total_weeks">
          <el-input-number v-model="form.total_weeks" :min="1" :max="30" />
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
import { termApi } from '../../api/modules'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ id: null, term_name: '', start_date: '', end_date: '', total_weeks: 20 })
const rules = {
  term_name: [{ required: true, message: '请输入学期名称', trigger: 'blur' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }]
}

async function load() {
  loading.value = true
  try {
    const data = await termApi.list({
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

function openDialog(row) {
  Object.assign(form, row
    ? {
        id: row.id, term_name: row.term_name, start_date: row.start_date,
        end_date: row.end_date, total_weeks: row.total_weeks
      }
    : { id: null, term_name: '', start_date: '', end_date: '', total_weeks: 20 })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (form.id) {
      await termApi.update(form.id, form)
      ElMessage.success('学期已更新')
    } else {
      await termApi.create(form)
      ElMessage.success('学期已创建')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    // request 已 toast
  } finally {
    saving.value = false
  }
}

function onSetCurrent(row) {
  ElMessageBox.confirm(`确定将「${row.term_name}」设为当前学期吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await termApi.update(row.id, { ...row, is_current: '1' })
      ElMessage.success('当前学期已切换')
      load()
    })
    .catch(() => {})
}

function onRemove(row) {
  ElMessageBox.confirm(`确定删除学期「${row.term_name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await termApi.remove(row.id)
      ElMessage.success('已删除')
      load()
    })
    .catch(() => {})
}

onMounted(load)
</script>

<style lang="scss" scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
