<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">请假管理</div>
        <div class="page-desc">全部请假记录与管理员状态干预（P1-15：干预必须填写原因）</div>
      </div>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.student_no" placeholder="搜索学号" clearable style="width: 160px" @keyup.enter="load" @clear="load" />
          <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 130px" @change="load">
            <el-option label="待审批" value="0" />
            <el-option label="通过" value="1" />
            <el-option label="驳回" value="2" />
            <el-option label="撤销" value="3" />
          </el-select>
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="student_no" label="学号" width="110" />
          <el-table-column prop="student_name" label="姓名" width="90" />
          <el-table-column label="类型" width="80">
            <template #default="{ row }">{{ TYPE_NAMES[row.leave_type] }}</template>
          </el-table-column>
          <el-table-column prop="reason" label="事由" min-width="180" show-overflow-tooltip />
          <el-table-column label="时段" min-width="240">
            <template #default="{ row }">
              <span class="text-muted">{{ row.start_time?.slice(0, 16) }} ~ {{ row.end_time?.slice(0, 16) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="时长" width="100">
            <template #default="{ row }">{{ row.total_days }} 天</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :class="statusClass(row.status)" effect="plain" size="small">{{ STATUS_NAMES[row.status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="approve_comment" label="审批/干预意见" min-width="140" show-overflow-tooltip />
          <el-table-column prop="create_time" label="提交时间" min-width="150" />
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openIntervene(row)">干预</el-button>
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

    <!-- 干预弹窗（P1-15） -->
    <el-dialog v-model="dialogVisible" title="管理员干预状态" width="460px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="当前状态">
          <el-tag effect="plain">{{ STATUS_NAMES[cur.status] }}</el-tag>
        </el-form-item>
        <el-form-item label="调整至" prop="status">
          <el-select v-model="form.status" placeholder="选择目标状态" style="width: 100%">
            <el-option label="待审批" value="0" />
            <el-option label="通过" value="1" />
            <el-option label="驳回" value="2" />
            <el-option label="撤销" value="3" />
          </el-select>
        </el-form-item>
        <el-form-item label="干预原因" prop="reason">
          <el-input v-model="form.reason" type="textarea" :rows="3" placeholder="必填：说明干预原因（P1-15）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">确认干预</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import request from '../../utils/request'

const TYPE_NAMES = { 1: '事假', 2: '病假', 3: '其他' }
const STATUS_NAMES = { 0: '待审批', 1: '通过', 2: '驳回', 3: '撤销' }

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, status: '', student_no: '' })

const dialogVisible = ref(false)
const formRef = ref()
const cur = ref({})
const form = reactive({ status: '', reason: '' })
const rules = {
  status: [{ required: true, message: '请选择目标状态', trigger: 'change' }],
  reason: [{ required: true, message: '干预必须填写原因（P1-15）', trigger: 'blur' }]
}

function statusClass(status) {
  return { 0: 'tag-status-draft', 1: 'tag-status-publish', 2: 'tag-status-offline', 3: 'tag-status-offline' }[status] || ''
}

async function load() {
  loading.value = true
  try {
    const data = await request.get('/leaves', { params: { page: query.page, page_size: query.page_size, status: query.status || undefined, student_no: query.student_no || undefined } })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

function openIntervene(row) {
  cur.value = row
  form.status = ''
  form.reason = ''
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    await request.post(`/leaves/${cur.value.id}/intervene`, { status: form.status, reason: form.reason })
    ElMessage.success('状态已干预')
    dialogVisible.value = false
    load()
  } catch (e) {
    // request 已 toast
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.text-muted {
  color: $ink-2;
}
</style>
