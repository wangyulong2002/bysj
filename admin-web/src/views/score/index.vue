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
          <el-select v-model="query.offering_id" placeholder="选择教学班" clearable filterable style="width: 260px" @change="load">
            <el-option v-for="o in offeringOptions" :key="o.id" :label="`${o.course_name} · ${o.class_name}`" :value="o.id" />
          </el-select>
          <el-button :icon="Search" @click="load">查询</el-button>
          <el-upload
            :show-file-list="false"
            :http-request="onImport"
            accept=".xlsx,.xls"
          >
            <el-button :icon="Upload" :loading="importing">Excel 导入</el-button>
          </el-upload>
          <el-button :icon="Tickets" @click="openAudit">审计查询</el-button>
          <span class="text-muted">录入由教师应用端（草稿）完成；管理端负责导入与发布</span>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
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
import { Plus, Search, Upload, Tickets } from '@element-plus/icons-vue'
import { offeringApi } from '../../api/modules'
import request from '../../utils/request'

const OP_NAMES = { 1: '录入', 2: '修改', 3: '发布', 4: '撤销发布' }

const loading = ref(false)
const importing = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, offering_id: null })
const offeringOptions = ref([])

const auditVisible = ref(false)
const auditLoading = ref(false)
const auditRows = ref([])

async function load() {
  loading.value = true
  try {
    const data = await request.get('/scores', { params: { page: query.page, page_size: query.page_size, offering_id: query.offering_id || undefined } })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

async function loadOfferings() {
  const data = await offeringApi.list({ page_size: 200 })
  offeringOptions.value = data.results || []
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
  if (!query.offering_id) {
    ElMessage.warning('请先选择教学班')
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await request.post(`/scores/import?offering_id=${query.offering_id}`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
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
    const data = await request.get('/score-audits', { params: { offering_id: query.offering_id || undefined, page_size: 100 } })
    auditRows.value = data.results || []
  } finally {
    auditLoading.value = false
  }
}

onMounted(() => {
  loadOfferings()
  load()
})
</script>

<style lang="scss" scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.text-muted {
  color: $ink-2;
  font-size: 12px;
}

.fail {
  color: $err;
  font-weight: 600;
}
</style>
