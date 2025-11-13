<template>
  <div class="paper-management">
    

    <!-- 筛选区域 -->
    <el-card class="filter-card">
      <el-form :model="filterForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="期刊刊期">
              <el-select v-model="filterForm.issue" placeholder="请选择刊期" clearable>
                <el-option 
                  v-for="journal in journalList" 
                  :key="journal.id"
                  :label="journal.issue" 
                  :value="journal.issue" 
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="论文状态">
              <el-select v-model="filterForm.status" placeholder="请选择状态" clearable>
                <el-option label="待审核" value="pending" />
                <el-option label="已通过" value="approved" />
                <el-option label="需修改" value="need_revision" />
                <el-option label="已拒绝" value="rejected" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="关键词">
              <el-input v-model="filterForm.keyword" placeholder="输入关键词搜索" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item>
              <el-button class="search-btn" type="primary" @click="handleSearch">搜索</el-button>
              <el-button class="reset-btn" @click="resetFilter">重置</el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 论文列表 -->
    <el-card class="content-card">
      <template #header>
        <div class="card-header">
          <h3>论文列表</h3>
          <el-button class="add-paper-btn" type="primary" size="small" @click="handleAddPaper">添加论文</el-button>
        </div>
      </template>

      <!-- 批量操作按钮 -->
      <div class="batch-actions" v-if="selectedPapers.length > 0">
        <el-button size="small" type="danger" @click="handleBatchDelete">
          批量删除 ({{ selectedPapers.length }})
        </el-button>
        <el-button size="small" type="success" @click="handleBatchDownload">
          批量下载 ({{ selectedPapers.length }})
        </el-button>
      </div>

      <el-table 
        :data="pagedPaperList" 
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="title" label="论文标题" width="250" />
        <el-table-column prop="author" label="作者" width="100" />
        <el-table-column prop="journalIssue" label="期刊刊期" width="120" />
        <el-table-column prop="startPage" label="起始页" width="80" />
        <el-table-column prop="endPage" label="结束页" width="80" />
        <el-table-column prop="status" label="状态" width="150">
          <template #default="scope">
            <div v-if="scope.row.parsing_status === 'parsing'">
              <el-progress 
                :percentage="scope.row.parsing_progress || 0" 
                :show-text="false"
                :stroke-width="8"
                status="success"
              />
              <span style="font-size: 12px; color: #67c23a;">解析中...</span>
            </div>
            <div v-else-if="scope.row.parsing_status === 'failed'">
              <el-tag type="danger">解析失败</el-tag>
            </div>
            <div v-else>
              <el-tag :type="getStatusType(scope.row.status)">
                {{ scope.row.status }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="submitDate" label="提交日期" width="120" />
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button class="view-btn" size="small" @click="handleView(scope.row)">
              查看
            </el-button>
            <el-button class="edit-btn" size="small" @click="handleEdit(scope.row)">
              编辑
            </el-button>
            <el-button class="delete-btn" size="small" @click="handleDelete(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页控件 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :small="true"
          :background="true"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredPaperList.length"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { usePaperStore } from '@/stores/paperStore'
import type { Paper } from '@/api/paperService'

const paperStore = usePaperStore()

// 使用store中的状态和计算属性
const filterForm = computed(() => paperStore.filterForm)
const selectedPapers = computed(() => paperStore.selectedPapers)
const currentPage = computed({
  get: () => paperStore.currentPage,
  set: (value) => paperStore.setCurrentPage(value)
})
const pageSize = computed({
  get: () => paperStore.pageSize,
  set: (value) => paperStore.setPageSize(value)
})
const journalList = computed(() => paperStore.journalList)
const allPaperList = computed(() => paperStore.allPaperList)
const filteredPaperList = computed(() => paperStore.filteredPaperList)
const pagedPaperList = computed(() => paperStore.pagedPaperList)

const getStatusType = (status: string) => {
  const statusMap: Record<string, string> = {
    '待审核': 'warning',
    '已通过': 'success',
    '需修改': 'danger',
    '已拒绝': 'info'
  }
  return statusMap[status] || 'info'
}

const handleSearch = () => {
  paperStore.setCurrentPage(1) // 搜索时重置到第一页
  ElMessage.info('搜索完成')
}

const resetFilter = () => {
  paperStore.resetFilter()
  ElMessage.info('筛选已重置')
}

const handleSelectionChange = (selection: Paper[]) => {
  paperStore.setSelectedPapers(selection)
}

const handleSizeChange = (size: number) => {
  paperStore.setPageSize(size)
}

const handleCurrentChange = (page: number) => {
  paperStore.setCurrentPage(page)
}

const handleView = (paper: Paper) => {
  console.log('查看按钮点击，论文数据:', paper)
  
  // 检查是否有PDF文件路径
  if (!paper.file_path && !paper.stored_filename) {
    ElMessage.warning('该论文暂无PDF文件')
    return
  }
  
  // 从文件路径中提取文件名
  let filename = ''
  if (paper.file_path) {
    // 从文件路径中提取文件名
    const pathParts = paper.file_path.split(/[\\/]/)
    filename = pathParts[pathParts.length - 1]
  } else if (paper.stored_filename) {
    filename = paper.stored_filename
  }
  
  if (!filename) {
    ElMessage.error('无法获取PDF文件名')
    return
  }
  
  // 使用预览API访问PDF文件 - 不强制下载
  const pdfUrl = `/api/preview/${filename}`
  console.log('PDF预览URL:', pdfUrl)
  
  // 在新窗口打开PDF预览
  const previewWindow = window.open(pdfUrl, '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes')
  
  if (previewWindow) {
    ElMessage.success('正在打开PDF预览...')
  } else {
    ElMessage.error('无法打开预览窗口，请检查浏览器弹窗设置')
  }
}

const handleEdit = (paper: Paper) => {
  ElMessage.info(`编辑论文: ${paper.title}`)
}

const handleDelete = async (paper: Paper) => {
  try {
    await ElMessageBox.confirm(`确定要删除论文"${paper.title}"吗？`, '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    
    await paperStore.deletePaper(paper.id)
  } catch (error: any) {
    if (error === 'cancel' || error.message === 'cancel') {
      ElMessage.info('取消删除')
    } else {
      console.error('删除论文失败:', error)
      ElMessage.error(error.message)
    }
  }
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedPapers.value.length} 篇论文吗？`, '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    
    await paperStore.batchDeletePapers()
  } catch (error: any) {
    if (error === 'cancel' || error.message === 'cancel') {
      ElMessage.info('取消批量删除')
    } else {
      console.error('批量删除失败:', error)
      ElMessage.error(error.message)
    }
  }
}

const handleBatchDownload = async () => {
  await paperStore.batchDownloadPapers()
}

const handleBatchMove = () => {
  ElMessage.info('批量移动功能待实现')
}

const handleAddPaper = () => {
  // 创建文件输入元素，支持多选
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf'
  input.multiple = true
  input.style.display = 'none'
  
  input.onchange = async (event: any) => {
    const files = Array.from(event.target.files) as File[]
    if (!files || files.length === 0) return
    
    // 验证文件类型
    const invalidFiles = files.filter(file => file.type !== 'application/pdf')
    if (invalidFiles.length > 0) {
      ElMessage.error('请选择PDF文件')
      return
    }
    
    // 如果选择了多个文件，使用批量上传
    if (files.length > 1) {
      await paperStore.batchUploadPapers(files)
    } else {
      // 单个文件上传
      const file = files[0]
      await paperStore.uploadPaper(file)
    }
  }
  
  // 触发文件选择
  document.body.appendChild(input)
  input.click()
  document.body.removeChild(input)
}

// 页面加载时获取数据
onMounted(() => {
  paperStore.loadJournals()
  paperStore.loadPapers(true) // 只在初始加载时显示成功消息
})
</script>

<style scoped>
.paper-management {
  padding: 20px;
  width: 100%;
  box-sizing: border-box;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  color: #333;
  margin-bottom: 8px;
}

.page-header p {
  color: #666;
  margin: 0;
}

.filter-card {
  margin-bottom: 20px;
}

.content-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.card-header h3 {
  margin: 0;
  color: #333;
}

.batch-actions {
  margin-bottom: 15px;
  padding: 10px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 翻页组件当前页码自定义颜色 */
:deep(.el-pagination.is-background .el-pager li.is-active) {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

:deep(.el-pagination.is-background .el-pager li.is-active:hover) {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
  color: white !important;
}

/* 搜索按钮自定义样式 */
.search-btn {
  background-color: #9c0e0e !important;
  border-color: #9c0e0e !important;
  color: white !important;
}

.search-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

/* 重置按钮自定义样式 */
.reset-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

.reset-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #3f4041ff !important;
  color: #7a7d80ff !important;
}

/* 添加论文按钮自定义样式 */
.add-paper-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.add-paper-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

/* 查看按钮自定义样式 */
.view-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

.view-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #3f4041ff !important;
  color: #7a7d80ff !important;
}

/* 编辑按钮自定义样式 */
.edit-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

.edit-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #3f4041ff !important;
  color: #7a7d80ff !important;
}

/* 删除按钮自定义样式 */
.delete-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

/* 批量下载按钮自定义样式 */
.batch-actions .el-button--success {
  background-color: #67c23a !important;
  border-color: #67c23a !important;
  color: white !important;
}

.batch-actions .el-button--success:hover {
  background-color: #5daf34 !important;
  border-color: #5daf34 !important;
}

.delete-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #3f4041ff !important;
  color: #7a7d80ff !important;
}
</style>
