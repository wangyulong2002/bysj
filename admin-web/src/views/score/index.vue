<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">成绩管理</div>
        <div class="page-desc">按教学班查看成绩、Excel 导入、发布/撤销发布、审计追溯（4.3）</div>
      </div>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-select v-model="query.class_id" placeholder="班级" clearable filterable style="width: 150px" @change="onQueryClassChange">
            <el-option v-for="c in classOptions" :key="c.id" :label="c.class_name" :value="c.id" />
          </el-select>
          <el-select v-model="query.course_id" placeholder="课程（该班开设）" clearable filterable style="width: 180px">
            <el-option v-for="c in queryCourseOptions" :key="c.course_id" :label="c.course_name" :value="c.course_id" />
          </el-select>
          <el-button :icon="Search" @click="load">查询</el-button>
          <el-button :icon="Download" @click="openTemplateDialog">下载模板</el-button>
          <el-upload
            :show-file-list="false"
            :http-request="onImport"
            accept=".xlsx,.xls"
          >
            <el-button :icon="Upload" :loading="importing">Excel 导入</el-button>
          </el-upload>
          <el-button :icon="Tickets" @click="openAudit">审计查询</el-button>
          <span class="toolbar-spacer" />
          <el-button :icon="Select" :disabled="!selectedRows.length" @click="onBatchPublish">批量发布</el-button>
          <el-button :icon="RefreshLeft" :disabled="!selectedRows.length" @click="onBatchUnpublish">批量撤销</el-button>
        </div>
        <p class="toolbar-tip">工作流：下载模板（选班级+学科，自动带出全部学生）→ 只填平时/考试成绩 → 导入。录入由教师应用端（草稿）完成；管理端负责导入与发布。</p>

        <el-table v-loading="loading" :data="rows" stripe @selection-change="onSelectionChange">
          <el-table-column type="selection" width="46" />
          <el-table-column prop="student_no" label="学号" min-width="110" />
          <el-table-column prop="student_name" label="姓名" min-width="90" />
          <el-table-column prop="course_name" label="课程" min-width="130" />
          <el-table-column prop="term_name" label="学期" min-width="160" />
          <el-table-column prop="usual_score" label="平时" width="80" />
          <el-table-column prop="exam_score" label="考试" width="80" />
          <el-table-column label="总评" width="100">
            <template #default="{ row }">
              <span :class="{ fail: row.total_score !== null && row.total_score < 60 }">
                {{ row.total_score ?? '—' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :class="row.is_published === '1' ? 'tag-status-publish' : 'tag-status-draft'" effect="plain" size="small">
                {{ row.is_published === '1' ? '已发布' : '未发布' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="publish_time" label="发布时间" min-width="150" />
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.is_published === '0'" link type="primary" @click="onPublish(row)">发布</el-button>
              <el-button v-if="row.is_published === '1'" link type="warning" @click="onUnpublish(row)">撤销发布</el-button>
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

    <!-- 下载模板弹框：选择班级+课程，按教学班自动填充全部学生 -->
    <el-dialog v-model="dlgVisible" title="下载成绩导入模板" width="480px">
      <div class="dlg-form">
        <div class="dlg-row">
          <span class="dlg-label">班级</span>
          <el-select v-model="dlgQuery.class_id" placeholder="选择班级" clearable filterable style="width: 100%" @change="onDlgClassChange">
            <el-option v-for="c in classOptions" :key="c.id" :label="c.class_name" :value="c.id" />
          </el-select>
        </div>
        <div class="dlg-row">
          <span class="dlg-label">学科</span>
          <el-select v-model="dlgQuery.course_id" placeholder="选择学科（该班开设课程）" clearable filterable style="width: 100%">
            <el-option v-for="c in dlgCourseOptions" :key="c.course_id" :label="c.course_name" :value="c.course_id" />
          </el-select>
        </div>
        <p class="dlg-tip">模板将自动填入该班级全部学生的学号（班级/学科列已预填），只填平时成绩、考试成绩后即可导入。</p>
      </div>
      <template #footer>
        <el-button @click="dlgVisible = false">取消</el-button>
        <el-button type="primary" :loading="dlgDownloading" @click="downloadTemplate">下载</el-button>
      </template>
    </el-dialog>

    <!-- 审计查询弹窗 -->
    <el-dialog v-model="auditVisible" title="成绩审计" width="760px">
      <el-table v-loading="auditLoading" :data="auditRows" size="small" stripe>
        <el-table-column prop="student_no" label="学号" width="110" />
        <el-table-column prop="student_name" label="姓名" width="90" />
        <el-table-column label="操作" width="80">
          <template #default="{ row }">{{ OP_NAMES[row.operation] }}</template>
        </el-table-column>
        <el-table-column prop="old_score" label="旧总评" width="80" />
        <el-table-column prop="new_score" label="新总评" width="80" />
        <el-table-column label="明细" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.new_detail">平时 {{ row.new_detail.usual_score }} / 考试 {{ row.new_detail.exam_score }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作人" width="90" />
        <el-table-column prop="operation_time" label="时间" width="150" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, RefreshLeft, Search, Select, Tickets, Upload } from '@element-plus/icons-vue'
import axios from 'axios'
import { classApi, offeringApi } from '../../api/modules'
import request from '../../utils/request'

const OP_NAMES = { 1: '录入', 2: '修改', 3: '发布', 4: '撤销发布' }

const loading = ref(false)
const importing = ref(false)
const rows = ref([])
const total = ref(0)
const selectedRows = ref([])

function onSelectionChange(rows) {
  selectedRows.value = rows
}

async function onBatchPublish() {
  const ids = selectedRows.value.map((r) => r.id)
  ElMessageBox.confirm(`确定批量发布选中的 ${ids.length} 条成绩吗？发布后学生端可见。`, '提示', { type: 'warning' })
    .then(async () => {
      const data = await request.post('/scores/batch-publish', { ids })
      ElMessage.success(`已发布 ${data.published} 条${data.skipped ? `，跳过已发布 ${data.skipped} 条` : ''}`)
      load()
    })
    .catch(() => {})
}

async function onBatchUnpublish() {
  const ids = selectedRows.value.map((r) => r.id)
  ElMessageBox.confirm(`确定批量撤销发布选中的 ${ids.length} 条成绩吗？撤销后学生端不可见。`, '提示', { type: 'warning' })
    .then(async () => {
      const data = await request.post('/scores/batch-unpublish', { ids })
      ElMessage.success(`已撤销 ${data.unpublished} 条${data.skipped ? `，跳过未发布 ${data.skipped} 条` : ''}`)
      load()
    })
    .catch(() => {})
}
const query = reactive({ page: 1, page_size: 10, class_id: null, course_id: null })
const offeringOptions = ref([])
const classOptions = ref([])
const queryCourseOptions = ref([])

const dlgVisible = ref(false)
const dlgDownloading = ref(false)
const dlgQuery = reactive({ class_id: null, course_id: null })
const dlgCourseOptions = ref([])

const auditVisible = ref(false)
const auditLoading = ref(false)
const auditRows = ref([])

/** 从教学班列表过滤出某班级开设的课程（去重，返回课程对象而非教学班）。 */
function filterCourses(offerings, classId) {
  if (!classId) return []
  const map = new Map()
  offerings
    .filter((o) => o.class_id === classId)
    .forEach((o) => map.set(o.course_id, { course_id: o.course_id, course_name: o.course_name }))
  return [...map.values()]
}

async function load() {
  loading.value = true
  try {
    const data = await request.get('/scores', {
      params: {
        page: query.page,
        page_size: query.page_size,
        class_id: query.class_id || undefined,
        course_id: query.course_id || undefined
      }
    })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

function onQueryClassChange() {
  queryCourseOptions.value = filterCourses(offeringOptions.value, query.class_id)
  query.course_id = null
  load()
}

async function loadOfferings() {
  const data = await offeringApi.list({ page_size: 200 })
  offeringOptions.value = data.results || []
}

async function loadClasses() {
  const data = await classApi.list({ page_size: 200 })
  classOptions.value = data.results || []
}

function openTemplateDialog() {
  dlgVisible.value = true
  dlgQuery.class_id = null
  dlgQuery.course_id = null
  dlgCourseOptions.value = []
}

function onDlgClassChange() {
  dlgCourseOptions.value = filterCourses(offeringOptions.value, dlgQuery.class_id)
  dlgQuery.course_id = null
}

async function downloadTemplate() {
  if (!dlgQuery.class_id || !dlgQuery.course_id) {
    ElMessage.warning('请选择班级和课程')
    return
  }
  dlgDownloading.value = true
  try {
    const token = localStorage.getItem('admin_access')
    const resp = await axios.get('/admin/api/scores/import-template', {
      params: { class_id: dlgQuery.class_id, course_id: dlgQuery.course_id },
      headers: { Authorization: `Bearer ${token}` },
      responseType: 'blob'
    })
    const cls = classOptions.value.find((c) => c.id === dlgQuery.class_id)
    const course = dlgCourseOptions.value.find((c) => c.course_id === dlgQuery.course_id)
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `成绩导入模板_${cls?.class_name ?? ''}_${course?.course_name ?? ''}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('模板已下载')
    dlgVisible.value = false
  } catch (e) {
    // 非标准 JSON 错误由浏览器抛，提示网络问题
    ElMessage.error('模板下载失败，请检查 Django 管理端是否启动')
  } finally {
    dlgDownloading.value = false
  }
}

function onPublish(row) {
  ElMessageBox.confirm(`确定发布「${row.student_name}」的成绩吗？发布后学生端可见。`, '提示', { type: 'warning' })
    .then(async () => {
      await request.post(`/scores/${row.id}/publish`)
      ElMessage.success('已发布')
      load()
    })
    .catch(() => {})
}

function onUnpublish(row) {
  ElMessageBox.confirm(`确定撤销发布「${row.student_name}」的成绩吗？撤销后学生端不可见。`, '提示', { type: 'warning' })
    .then(async () => {
      await request.post(`/scores/${row.id}/unpublish`)
      ElMessage.success('已撤销发布')
      load()
    })
    .catch(() => {})
}

async function onImport({ file }) {
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await request.post('/scores/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success(`导入成功 ${data.imported} 条`)
    if (data.errors && data.errors.length) {
      ElMessageBox.alert(data.errors.map((e) => `第${e.row}行：${e.message}`).join('\n'), '导入错误行', { dangerouslyUseHTMLString: false })
    }
    load()
  } catch (e) {
    // request 已 toast
  } finally {
    importing.value = false
  }
}

async function openAudit() {
  auditVisible.value = true
  auditLoading.value = true
  try {
    const data = await request.get('/score-audits', {
      params: {
        class_id: query.class_id || undefined,
        course_id: query.course_id || undefined,
        page_size: 100
      }
    })
    auditRows.value = data.results || []
  } finally {
    auditLoading.value = false
  }
}

onMounted(() => {
  loadOfferings()
  loadClasses()
  load()
})
</script>

<style lang="scss" scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.toolbar-spacer {
  flex: 1;
}

.toolbar-label {
  color: $ink-2;
  font-size: 13px;
  margin-right: 4px;
}

.toolbar-tip {
  color: $ink-2;
  font-size: 12px;
  margin: 8px 0 0;
  line-height: 1.6;
}

.dlg-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.dlg-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dlg-label {
  width: 48px;
  color: $ink-2;
  font-size: 13px;
  flex-shrink: 0;
}

.dlg-tip {
  color: $ink-2;
  font-size: 12px;
  margin: 0;
  line-height: 1.6;
  background: $bg;
  padding: 8px 10px;
  border-radius: 6px;
}

.fail {
  color: $err;
  font-weight: 600;
}
</style>
