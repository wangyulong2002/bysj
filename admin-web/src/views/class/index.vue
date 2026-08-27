<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">班级管理</div>
        <div class="page-desc">班级信息维护（设计 5.3.2）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增班级</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索班级名称/编码" clearable @keyup.enter="load" @clear="load" />
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="class_name" label="班级名称" min-width="140" />
          <el-table-column prop="class_code" label="班级编码" min-width="110" />
          <el-table-column prop="grade" label="年级" width="80" />
          <el-table-column prop="major" label="专业" min-width="100" />
          <el-table-column prop="department_name" label="所属院系" min-width="120" />
          <el-table-column prop="counselor_name" label="辅导员" min-width="100" />
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑班级' : '新增班级'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="班级名称" prop="class_name">
          <el-input v-model="form.class_name" placeholder="如：计科2301" />
        </el-form-item>
        <el-form-item label="班级编码" prop="class_code">
          <el-input v-model="form.class_code" placeholder="如：CS2301" />
        </el-form-item>
        <el-form-item label="年级" prop="grade">
          <el-input v-model="form.grade" placeholder="如：2023" />
        </el-form-item>
        <el-form-item label="专业" prop="major">
          <el-input v-model="form.major" placeholder="如：计算机科学与技术" />
        </el-form-item>
        <el-form-item label="所属院系" prop="department_id">
          <el-select v-model="form.department_id" placeholder="选择院系" clearable filterable style="width: 100%">
            <el-option v-for="d in deptOptions" :key="d.id" :label="d.dept_name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="辅导员" prop="counselor_id">
          <el-select v-model="form.counselor_id" placeholder="选择辅导员" clearable filterable style="width: 100%">
            <el-option v-for="u in counselorOptions" :key="u.id" :label="u.name" :value="u.id" />
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
import { classApi, departmentApi } from '../../api/modules'
import request from '../../utils/request'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })
const deptOptions = ref([])
const counselorOptions = ref([])

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, class_name: '', class_code: '', grade: '', major: '',
  department_id: null, counselor_id: null
})
const rules = {
  class_name: [{ required: true, message: '请输入班级名称', trigger: 'blur' }],
  class_code: [{ required: true, message: '请输入班级编码', trigger: 'blur' }],
  grade: [{ required: true, message: '请输入年级', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await classApi.list({
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
  // v2.4 无专职辅导员：班级辅导员由教师兼任（role_code=teacher）
  const [depts, counselors] = await Promise.all([
    departmentApi.list({ page_size: 100 }),
    request.get('/users/options', { params: { role: 'teacher' } })
  ])
  deptOptions.value = depts.results || []
  counselorOptions.value = counselors || []
}

function openDialog(row) {
  Object.assign(form, row
    ? {
        id: row.id, class_name: row.class_name, class_code: row.class_code,
        grade: row.grade, major: row.major,
        department_id: row.department_id, counselor_id: row.counselor_id
      }
    : { id: null, class_name: '', class_code: '', grade: '', major: '', department_id: null, counselor_id: null })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (form.id) {
      await classApi.update(form.id, form)
      ElMessage.success('班级已更新')
    } else {
      await classApi.create(form)
      ElMessage.success('班级已创建')
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
  ElMessageBox.confirm(`确定删除班级「${row.class_name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await classApi.remove(row.id)
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
