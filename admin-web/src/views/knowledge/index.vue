<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">知识库管理</div>
        <div class="page-desc">RAG 专题知识库（8.3 数据源二）：发布即自动向量化，供 AI 校园助手引用</div>
      </div>
      <div>
        <el-button :icon="Refresh" class="rag-btn" @click="loadIndex">索引状态</el-button>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增知识</el-button>
      </div>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索标题/标签/正文" clearable @keyup.enter="load" @clear="load" />
          <el-select v-model="query.category" placeholder="全部分类" clearable style="width: 130px" @change="load">
            <el-option v-for="(name, c) in CATEGORY_NAMES" :key="c" :label="name" :value="c" />
          </el-select>
          <el-select v-model="query.status" placeholder="全部状态" clearable style="width: 130px" @change="load">
            <el-option label="草稿" value="0" />
            <el-option label="已发布" value="1" />
          </el-select>
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
          <el-table-column label="分类" width="90">
            <template #default="{ row }">{{ CATEGORY_NAMES[row.category] || '—' }}</template>
          </el-table-column>
          <el-table-column prop="tags" label="标签" min-width="140" show-overflow-tooltip />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :class="statusClass(row.status)" effect="plain" size="small">{{ STATUS_NAMES[row.status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="update_time" label="更新时间" min-width="150" />
          <el-table-column prop="publisher_name" label="发布人" width="100" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status === '0'" link type="primary" @click="onPublish(row)">发布</el-button>
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑知识' : '新增知识'" width="640px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="知识标题（将作为检索标题）" maxlength="100" />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="form.category" placeholder="选择分类" style="width: 100%">
            <el-option v-for="(name, c) in CATEGORY_NAMES" :key="c" :label="name" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="逗号分隔，如：宿舍,新生" maxlength="200" />
        </el-form-item>
        <el-form-item label="正文" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="10"
            placeholder="支持纯文本或 HTML 富文本（发布时自动剥离标签切分向量化）"
          />
          <div class="form-tip">内容变更并保存后自动重新向量化；无变化不重复消耗向量化任务（P0-09）</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="indexVisible" title="RAG 索引状态" width="560px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="索引文档数（Redis）">{{ indexInfo.num_docs ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="已向量化分片（MySQL）">{{ indexInfo.chunk_total ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="重建中">
          <el-tag v-if="indexInfo.rebuilding" type="warning" size="small">重建中</el-tag>
          <el-tag v-else type="success" size="small">正常</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <div v-if="indexInfo.latest_tasks && indexInfo.latest_tasks.length" class="task-list">
        <div class="task-title">最近任务</div>
        <div v-for="t in indexInfo.latest_tasks" :key="t.id" class="task-row">
          <span>#{{ t.id }}</span>
          <span>{{ t.operation === '1' ? 'upsert' : 'delete' }}</span>
          <span>{{ t.source_type === '1' ? '公告' : '知识库' }}-{{ t.source_id }}</span>
          <span>{{ TASK_STATUS[t.status] || t.status }}</span>
        </div>
      </div>
      <template #footer>
        <el-button @click="indexVisible = false">关闭</el-button>
        <el-button type="warning" :loading="rebuilding" @click="onRebuild">全量重建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'
import { knowledgeApi, ragIndexApi } from '../../api/modules'

const CATEGORY_NAMES = { 1: '师资', 2: '宿舍', 3: '食堂', 4: '制度', 5: '招生', 6: '设施', 7: '其他' }
const STATUS_NAMES = { 0: '草稿', 1: '已发布' }
const TASK_STATUS = { 0: '待处理', 1: '处理中', 2: '成功', 3: '失败' }

const loading = ref(false)
const saving = ref(false)
const rebuilding = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '', category: '', status: '' })

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ id: null, title: '', category: '2', content: '', tags: '' })
const rules = {
  title: [{ required: true, message: '请输入知识标题', trigger: 'blur' }],
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  content: [{ required: true, message: '请输入正文', trigger: 'blur' }]
}

const indexVisible = ref(false)
const indexInfo = reactive({ num_docs: null, chunk_total: 0, rebuilding: null, latest_tasks: [] })

function statusClass(status) {
  return { 0: 'tag-status-draft', 1: 'tag-status-publish' }[status] || ''
}

async function load() {
  loading.value = true
  try {
    const data = await knowledgeApi.list({
      page: query.page,
      page_size: query.page_size,
      search: query.keyword || undefined,
      category: query.category || undefined,
      status: query.status || undefined
    })
    rows.value = data.results || []
    total.value = data.count || 0
  } finally {
    loading.value = false
  }
}

function openDialog(row) {
  Object.assign(form, row
    ? { id: row.id, title: row.title, category: row.category, content: row.content || '', tags: row.tags || '' }
    : { id: null, title: '', category: '2', content: '', tags: '' })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    const payload = { title: form.title, category: form.category, content: form.content, tags: form.tags }
    if (form.id) {
      await knowledgeApi.update(form.id, payload)
      ElMessage.success('知识已更新（内容变化将自动重新向量化）')
    } else {
      await knowledgeApi.create({ ...payload, status: '0' })
      ElMessage.success('知识已创建（草稿）')
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
  ElMessageBox.confirm(`确定发布知识「${row.title}」吗？发布后将自动向量化供 AI 助手引用。`, '提示', { type: 'warning' })
    .then(async () => {
      await knowledgeApi.publish(row.id)
      ElMessage.success('已发布，将自动向量化')
      load()
    })
    .catch(() => {})
}

function onTakeDown(row) {
  ElMessageBox.confirm(`确定下架知识「${row.title}」吗？对应向量将从检索索引移除。`, '提示', { type: 'warning' })
    .then(async () => {
      await knowledgeApi.takeDown(row.id)
      ElMessage.success('已下架')
      load()
    })
    .catch(() => {})
}

function onRemove(row) {
  ElMessageBox.confirm(`确定删除知识「${row.title}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await knowledgeApi.remove(row.id)
      ElMessage.success('已删除')
      load()
    })
    .catch(() => {})
}

async function loadIndex() {
  indexVisible.value = true
  const data = await ragIndexApi.status()
  Object.assign(indexInfo, data)
}

function onRebuild() {
  ElMessageBox.confirm('全量重建将清空并重建向量索引（约 30s 内开始执行），确定继续吗？', '全量重建', { type: 'warning' })
    .then(async () => {
      rebuilding.value = true
      try {
        await ragIndexApi.rebuild()
        ElMessage.success('重建请求已提交，稍后刷新查看进度')
        await loadIndex()
      } finally {
        rebuilding.value = false
      }
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

.rag-btn {
  margin-right: 8px;
}

.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  margin-top: 4px;
}

.task-list {
  margin-top: 12px;

  .task-title {
    font-size: 13px;
    color: var(--el-text-color-secondary);
    margin-bottom: 6px;
  }

  .task-row {
    display: flex;
    gap: 12px;
    font-size: 13px;
    padding: 4px 0;
    border-bottom: 1px dashed var(--el-border-color-lighter);
  }
}
</style>
