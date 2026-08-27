<template>
  <div>
    <div class="page-header">
      <div>
        <div class="page-title">院系管理</div>
        <div class="page-desc">院系信息维护（设计 5.3.1）</div>
      </div>
      <el-button type="primary" :icon="Plus" @click="openDialog()">新增院系</el-button>
    </div>

    <div class="card-shell">
      <div class="card-core">
        <div class="toolbar">
          <el-input v-model="query.keyword" placeholder="搜索院系名称/编码" clearable @keyup.enter="load" @clear="load" />
          <el-button :icon="Search" @click="load">查询</el-button>
        </div>

        <el-table v-loading="loading" :data="rows" stripe>
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column prop="dept_name" label="院系名称" min-width="160" />
          <el-table-column prop="dept_code" label="院系编码" min-width="120" />
          <el-table-column prop="create_time" label="创建时间" min-width="160" />
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑院系' : '新增院系'" width="420px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="院系名称" prop="dept_name">
          <el-input v-model="form.dept_name" placeholder="如：计算机学院" />
        </el-form-item>
        <el-form-item label="院系编码" prop="dept_code">
          <el-input v-model="form.dept_code" placeholder="如：CS" />
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
import { departmentApi } from '../../api/modules'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, keyword: '' })

const dialogVisible = ref(false)
const formRef = ref()
const form = reactive({ id: null, dept_name: '', dept_code: '' })
const rules = {
  dept_name: [{ required: true, message: '请输入院系名称', trigger: 'blur' }],
  dept_code: [{ required: true, message: '请输入院系编码', trigger: 'blur' }]
}

async function load() {
  loading.value = true
  try {
    const data = await departmentApi.list({
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
  Object.assign(form, row ? { id: row.id, dept_name: row.dept_name, dept_code: row.dept_code } : { id: null, dept_name: '', dept_code: '' })
  dialogVisible.value = true
}

async function onSave() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (form.id) {
      await departmentApi.update(form.id, form)
      ElMessage.success('院系已更新')
    } else {
      await departmentApi.create(form)
      ElMessage.success('院系已创建')
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
  ElMessageBox.confirm(`确定删除院系「${row.dept_name}」吗？`, '提示', { type: 'warning' })
    .then(async () => {
      await departmentApi.remove(row.id)
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
