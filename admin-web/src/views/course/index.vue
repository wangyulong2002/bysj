<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">课程管理</div>
        <div class="page-desc">课程信息维护（设计 5.3.3）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增课程</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索课程名称/编码" clearable @keyup.enter="load" @clear="load" />
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="course_name" label="课程名称" min-width="150" />
          <el-table-column prop="course_code" label="课程编码" min-width="110" />
          <el-table-column prop="credit" label="学分" width="80" />
          <el-table-column prop="hours" label="学时" width="80" />
          <el-table-column prop="department_name" label="开课院系" min-width="120" />
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑课程' : '新增课程'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="课程名称" prop="course_name">
          <el-input v-model="form.course_name" placeholder="如：数据结构" />
        </el-form-item>
        <el-form-item label="课程编码" prop="course_code">
          <el-input v-model="form.course_code" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="学分" prop="credit">
          <el-input-number v-model="form.credit" :min="0.5" :max="10" :step="0.5" />
        </el-form-item>
        <el-form-item label="学时" prop="hours">
          <el-input-number v-model="form.hours" :min="1" :max="200" />
        </el-form-item>
        <el-form-item label="开课院系" prop="department_id">
          <el-select v-model="form.department_id" placeholder="选择院系" clearable filterable style="width: 100%">
            <el-option v-for="d in deptOptions" :key="d.id" :label="d.dept_name" :value="d.id" />
          </el-select>
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
import { courseApi, departmentApi } from '../../api/modules'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const deptOptions = ref([])

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, course_name: '', course_code: '', credit: 3, hours: 48, department_id: null
})
const rules = {
  course_name: [{ required: true, message: '请输入课程名称', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await courseApi.list({
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
  const depts = await departmentApi.list({ page_size: 100 })
  deptOptions.value = depts.results || []
}

function openDialog(row) {
  Object.assign(form, row
    ? {
        id: row.id, course_name: row.course_name, course_code: row.course_code,
        credit: row.credit, hours: row.hours, department_id: row.department_id
      }
    : { id: null, course_name: '', course_code: '', credit: 3, hours: 48, department_id: null })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (form.id) {
      await courseApi.update(form.id, form)
      ElMessage.success('课程已更新')
    } else {
      await courseApi.create(form)
      ElMessage.success('课程已创建')
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
  ElMessageBox.confirm(`确定删除课程「${row.course_name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await courseApi.remove(row.id)
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
