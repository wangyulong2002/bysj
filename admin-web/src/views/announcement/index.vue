<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">公告管理</div>
        <div class="page-desc">公告发布/下架（4.2 状态机：草稿→发布→下架）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增公告</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索公告标题" clearable @keyup.enter="load" @clear="load" />
          <el-select v-model="query.ann_type" placeholder="全部类型" clearable style="width: 130px" @change="load">
            <el-option label="校园公告" value="1" />
            <el-option label="院系公告" value="2" />
            <el-option label="班级公告" value="3" />
          </el-select>
          <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 130px" @change="load">
            <el-option label="草稿" value="0" />
            <el-option label="已发布" value="1" />
            <el-option label="已下架" value="2" />
          </el-select>
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">{{ TYPE_NAMES[row.ann_type] }}</template>
          </el-table-column>
          <el-table-column label="目标" min-width="120">
            <template #default="{ row }">
              {{ row.ann_type === '3' ? row.target_class_name : (row.ann_type === '2' ? row.target_department_name : '—') }}
            </template>
          </el-table-column>
          <el-table-column label="置顶" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_top === '1'" class="tag-top" effect="plain" size="small">顶</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :class="statusClass(row.status)" effect="plain" size="small">{{ STATUS_NAMES[row.status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="publish_time" label="发布时间" min-width="150" />
          <el-table-column prop="publisher_name" label="发布人" width="100" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status === '0' || row.status === '2'" link type="primary" @click="onPublish(row)">发布</el-button>
              <el-button v-if="row.status === '1'" link type="warning" @click="onTakeDown(row)">下架</el-button>
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑公告' : '新增公告'" width="620px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="公告标题" maxlength="100" />
        </el-form-item>
        <el-form-item label="类型" prop="ann_type">
          <el-select v-model="form.ann_type" placeholder="选择类型" style="width: 100%" @change="onTypeChange">
            <el-option label="校园公告" value="1" />
            <el-option label="院系公告" value="2" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.ann_type === '2'" label="目标院系" prop="target_department_id">
          <el-select v-model="form.target_department_id" placeholder="选择目标院系" filterable clearable style="width: 100%">
            <el-option v-for="d in deptOptions" :key="d.id" :label="d.dept_name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="置顶">
          <el-switch v-model="form.is_top" active-value="1" inactive-value="0" active-text="置顶" />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="5" placeholder="公告内容" />
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
import { announcementApi, departmentApi } from '../../api/modules'

// v2.5/ADR-011：班级公告类型已移除，类型仅 1校园 / 2院系
const TYPE_NAMES = { 1: '校园公告', 2: '院系公告' }
const STATUS_NAMES = { 0: '草稿', 1: '已发布', 2: '已下架' }

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '', ann_type: '', status: '' })
const deptOptions = ref([])

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({
  id: null, title: '', content: '', ann_type: '1',
  target_department_id: null, is_top: '0', status: '0'
})
const rules = {
  title: [{ required: true, message: '请输入公告标题', trigger: 'blur' }],
  ann_type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  content: [{ required: true, message: '请输入公告内容', trigger: 'blur' }]
}

function statusClass(status) {
  return { 0: 'tag-status-draft', 1: 'tag-status-publish', 2: 'tag-status-offline' }[status] || ''
}

async function load() {
  loading.value = true
  try {
    const data = await announcementApi.list({
      page: query.page,
      page_size: query.page_size,
      search: query.keyword || undefined,
      ann_type: query.ann_type || undefined,
      status: query.status || undefined
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

function onTypeChange() {
  form.target_department_id = null
}

function openDialog(row) {
  Object.assign(form, row
    ? {
        id: row.id, title: row.title, content: row.content, ann_type: row.ann_type,
        target_department_id: row.target_department_id,
        is_top: row.is_top, status: row.status
      }
    : { id: null, title: '', content: '', ann_type: '1', target_department_id: null, is_top: '0', status: '0' })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = {
      title: form.title, content: form.content, ann_type: form.ann_type, is_top: form.is_top
    }
    if (form.ann_type === '2') payload.target_department_id = form.target_department_id
    if (form.id) {
      await announcementApi.update(form.id, payload)
      ElMessage.success('公告已更新')
    } else {
      await announcementApi.create({ ...payload, status: '0' })
      ElMessage.success('公告已创建（草稿）')
    }
    dialogVisible.value = false
    load()
  } catch (e) {
    // request 已 toast
  } finally {
    saving.value = false
  }
}

function onPublish(row) {
  ElMessageBox.confirm(`确定发布公告「${row.title}」吗？发布后应用端实时可见。`, '提示', { type: 'warning' })
    .then(async () => {
      await announcementApi.publish(row.id)
      ElMessage.success('已发布')
      load()
    })
    .catch(() => {})
}

function onTakeDown(row) {
  ElMessageBox.confirm(`确定下架公告「${row.title}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await announcementApi.takeDown(row.id)
      ElMessage.success('已下架')
      load()
    })
    .catch(() => {})
}

function onRemove(row) {
  ElMessageBox.confirm(`确定删除公告「${row.title}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await announcementApi.remove(row.id)
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
