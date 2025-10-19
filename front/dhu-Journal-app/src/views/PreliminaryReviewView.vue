<template>
  <div class="preliminary-review">
    
    <!-- 待审核论文筛选区域 -->
    <el-card class="filter-card">
      <el-form :model="pendingSearchForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="提交日期">
              <el-date-picker
                v-model="pendingSearchForm.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="关键词">
              <el-input v-model="pendingSearchKeyword" placeholder="输入关键词搜索" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item>
              <el-button class="search-btn" type="primary" @click="handlePendingSearch">搜索</el-button>
              <el-button class="reset-btn" @click="resetPendingSearch">重置</el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 待审核论文列表 -->
    <el-card class="content-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <h3>待审核论文列表</h3>
            <span class="total-count">共 {{ filteredPendingList.length }} 篇论文</span>
          </div>
          <div class="header-right">
            <el-button class="add-paper-btn" type="primary" size="small" @click="showAddDialog = true">添加论文</el-button>
          </div>
        </div>
      </template>

      <el-table :data="paginatedPendingList" style="width: 100%">
        <el-table-column prop="title" label="论文标题" width="300" />
        <el-table-column prop="submitDate" label="提交日期" width="120" />
        <el-table-column label="操作" width="250">
          <template #default="scope">
            <el-button class="view-btn" size="small" @click="handleView(scope.row)">
              查看
            </el-button>
            <el-button class="audit-btn" size="small" @click="handleReview(scope.row)">
              审核
            </el-button>
            <el-button class="delete-btn" size="small" @click="handleDelete(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 待审核列表分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pendingPagination.currentPage"
          v-model:page-size="pendingPagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :small="true"
          :background="true"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredPendingList.length"
          @size-change="handlePendingPageSizeChange"
          @current-change="handlePendingPageChange"
        />
      </div>
    </el-card>

    <!-- 已审核论文筛选区域 -->
    <el-card class="filter-card">
      <el-form :model="filterForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="论文状态">
              <el-select v-model="filterForm.status" placeholder="请选择状态" clearable>
                <el-option label="已审核" value="reviewed" />
                <el-option label="需修改" value="need_revision" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="审核日期">
              <el-date-picker
                v-model="filterForm.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                value-format="YYYY-MM-DD"
              />
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

    <!-- 已审核论文列表 -->
    <el-card class="content-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <h3>已审核论文列表</h3>
            <span class="total-count">共 {{ filteredReviewedList.length }} 篇论文</span>
          </div>
        </div>
      </template>

      <el-table :data="paginatedReviewedList" style="width: 100%">
        <el-table-column prop="title" label="论文标题" width="250" />
        <el-table-column prop="reviewDate" label="审核日期" width="120" />
        <el-table-column label="审核状态" width="120">
          <template #default="scope">
            <el-tag :type="getReviewStatusType(scope.row.reviewStatus)">
              {{ scope.row.reviewStatus }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="scope">
            <el-button class="view-btn" size="small" @click="handleView(scope.row)">
              查看
            </el-button>
            <el-button class="edit-btn" size="small" @click="handleEdit(scope.row)">
              修改
            </el-button>
            <el-button class="delete-btn" size="small" @click="handleDelete(scope.row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- 已审核列表分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="reviewedPagination.currentPage"
          v-model:page-size="reviewedPagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :small="true"
          :background="true"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredReviewedList.length"
          @size-change="handleReviewedPageSizeChange"
          @current-change="handleReviewedPageChange"
        />
      </div>
    </el-card>

    <!-- 添加论文对话框 -->
    <el-dialog v-model="showAddDialog" title="添加论文" width="500px">
      <el-form :model="newPaper" label-width="80px">
        <el-form-item label="论文标题">
          <el-input v-model="newPaper.title" placeholder="请输入论文标题" />
        </el-form-item>
        <el-form-item label="提交日期">
          <el-date-picker
            v-model="newPaper.submitDate"
            type="date"
            placeholder="选择提交日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="上传文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".doc,.docx"
            :on-change="handleFileChange"
          >
            <el-button class="upload-btn" type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">只能上传Word文档，且不超过10MB</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button class="confirm-btn" type="primary" @click="handleAddPaper">确定</el-button>
      </template>
    </el-dialog>

    <!-- 审核对话框 -->
    <el-dialog v-model="showReviewDialog" title="论文审核" width="400px">
      <div class="review-content">
        <p><strong>论文标题：</strong>{{ currentPaper?.title }}</p>
        <el-form :model="reviewForm" label-width="80px">
          <el-form-item label="审核结果">
            <el-radio-group v-model="reviewForm.status">
              <el-radio value="已审核">已审核</el-radio>
              <el-radio value="需修改">需修改</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="审核意见">
            <el-input
              v-model="reviewForm.comment"
              type="textarea"
              :rows="3"
              placeholder="请输入审核意见（可选）"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showReviewDialog = false">取消</el-button>
        <el-button class="confirm-btn" type="primary" @click="confirmReview">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'

interface Paper {
  id: number
  title: string
  file?: File
  submitDate?: string
  reviewDate?: string
  reviewStatus?: string
  comment?: string
}

interface FilterForm {
  status: string
  dateRange: string[]
  keyword: string
}

// 数据定义
const pendingList = ref<Paper[]>([
  {
    id: 1,
    title: '基于深度学习的图像识别技术研究',
    submitDate: '2024-01-15'
  },
  {
    id: 2,
    title: '人工智能在医疗诊断中的应用',
    submitDate: '2024-01-12'
  }
])

const reviewedList = ref<Paper[]>([
  {
    id: 3,
    title: '区块链技术在供应链管理中的研究',
    submitDate: '2024-01-10',
    reviewDate: '2024-01-11',
    reviewStatus: '已审核'
  },
  {
    id: 4,
    title: '大数据分析在商业决策中的应用',
    submitDate: '2024-01-08',
    reviewDate: '2024-01-09',
    reviewStatus: '需修改'
  }
])

// 筛选表单
const filterForm = ref<FilterForm>({
  status: '',
  dateRange: [],
  keyword: ''
})

// 待审核列表搜索关键词
const pendingSearchKeyword = ref('')

// 待审核列表搜索表单
const pendingSearchForm = ref({
  keyword: '',
  dateRange: []
})

// 分页配置
const pendingPagination = ref({
  currentPage: 1,
  pageSize: 10
})

const reviewedPagination = ref({
  currentPage: 1,
  pageSize: 10
})

// 对话框状态
const showAddDialog = ref(false)
const showReviewDialog = ref(false)

// 表单数据
const newPaper = ref({
  title: '',
  submitDate: '',
  file: null as File | null
})

const reviewForm = ref({
  status: '',
  comment: ''
})

const currentPaper = ref<Paper | null>(null)

// 计算属性：筛选后的待审核列表
const filteredPendingList = computed(() => {
  let filtered = [...pendingList.value]
  
  // 按关键词筛选
  if (pendingSearchKeyword.value.trim()) {
    const keyword = pendingSearchKeyword.value.toLowerCase()
    filtered = filtered.filter(paper => 
      paper.title.toLowerCase().includes(keyword)
    )
  }
  
  // 按提交日期筛选
  if (pendingSearchForm.value.dateRange && pendingSearchForm.value.dateRange.length === 2) {
    const [startDate, endDate] = pendingSearchForm.value.dateRange
    filtered = filtered.filter(paper => {
      if (!paper.submitDate) return false
      return paper.submitDate >= startDate && paper.submitDate <= endDate
    })
  }
  
  return filtered
})

// 计算属性：筛选后的已审核列表
const filteredReviewedList = computed(() => {
  let filtered = [...reviewedList.value]
  
  // 按状态筛选
  if (filterForm.value.status) {
    const statusMap: Record<string, string> = {
      'reviewed': '已审核',
      'need_revision': '需修改'
    }
    const targetStatus = statusMap[filterForm.value.status]
    if (targetStatus) {
      filtered = filtered.filter(paper => paper.reviewStatus === targetStatus)
    }
  }
  
  // 按审核日期筛选
  if (filterForm.value.dateRange && filterForm.value.dateRange.length === 2) {
    const [startDate, endDate] = filterForm.value.dateRange
    filtered = filtered.filter(paper => {
      if (!paper.reviewDate) return false
      return paper.reviewDate >= startDate && paper.reviewDate <= endDate
    })
  }
  
  // 按关键词筛选
  if (filterForm.value.keyword.trim()) {
    const keyword = filterForm.value.keyword.toLowerCase()
    filtered = filtered.filter(paper => 
      paper.title.toLowerCase().includes(keyword)
    )
  }
  
  return filtered
})

// 计算属性：分页后的待审核列表
const paginatedPendingList = computed(() => {
  const start = (pendingPagination.value.currentPage - 1) * pendingPagination.value.pageSize
  const end = start + pendingPagination.value.pageSize
  return filteredPendingList.value.slice(start, end)
})

// 计算属性：分页后的已审核列表
const paginatedReviewedList = computed(() => {
  const start = (reviewedPagination.value.currentPage - 1) * reviewedPagination.value.pageSize
  const end = start + reviewedPagination.value.pageSize
  return filteredReviewedList.value.slice(start, end)
})

// 状态类型映射
const getReviewStatusType = (status: string) => {
  const statusMap: Record<string, string> = {
    '已审核': 'success',
    '需修改': 'danger'
  }
  return statusMap[status] || 'info'
}

// 文件选择处理
const handleFileChange = (file: any) => {
  newPaper.value.file = file.raw
}

// 添加论文
const handleAddPaper = () => {
  if (!newPaper.value.title.trim()) {
    ElMessage.error('请输入论文标题')
    return
  }
  
  if (!newPaper.value.submitDate) {
    ElMessage.error('请选择提交日期')
    return
  }
  
  if (!newPaper.value.file) {
    ElMessage.error('请选择文件')
    return
  }
  
  const paper: Paper = {
    id: Date.now(),
    title: newPaper.value.title,
    submitDate: newPaper.value.submitDate,
    file: newPaper.value.file
  }
  
  pendingList.value.push(paper)
  ElMessage.success('论文添加成功')
  
  // 重置表单
  newPaper.value = { title: '', submitDate: '', file: null }
  showAddDialog.value = false
}

// 审核论文
const handleReview = (paper: Paper) => {
  currentPaper.value = paper
  reviewForm.value = { status: '', comment: '' }
  showReviewDialog.value = true
}

// 确认审核
const confirmReview = () => {
  if (!reviewForm.value.status) {
    ElMessage.error('请选择审核结果')
    return
  }
  
  if (!currentPaper.value) return
  
  // 从待审核列表移除
  const index = pendingList.value.findIndex(p => p.id === currentPaper.value!.id)
  if (index > -1) {
    pendingList.value.splice(index, 1)
  }
  
  // 获取当前日期作为审核日期
  const reviewDate = new Date().toISOString().split('T')[0]
  
  // 添加到已审核列表
  const reviewedPaper: Paper = {
    ...currentPaper.value,
    reviewDate: reviewDate,
    reviewStatus: reviewForm.value.status,
    comment: reviewForm.value.comment
  }
  reviewedList.value.push(reviewedPaper)
  
  ElMessage.success('审核完成')
  showReviewDialog.value = false
}

// 删除论文
const handleDelete = (paper: Paper) => {
  // 从待审核列表删除
  const pendingIndex = pendingList.value.findIndex(p => p.id === paper.id)
  if (pendingIndex > -1) {
    pendingList.value.splice(pendingIndex, 1)
    ElMessage.success('论文已删除')
    return
  }
  
  // 从已审核列表删除
  const reviewedIndex = reviewedList.value.findIndex(p => p.id === paper.id)
  if (reviewedIndex > -1) {
    reviewedList.value.splice(reviewedIndex, 1)
    ElMessage.success('论文已删除')
    return
  }
}

// 查看论文
const handleView = (paper: Paper) => {
  ElMessage.info('查看功能待实现')
}

// 修改论文
const handleEdit = (paper: Paper) => {
  ElMessage.info('修改功能待实现')
}

// 待审核列表搜索
const handlePendingSearch = () => {
  // 重置到第一页
  pendingPagination.value.currentPage = 1
  ElMessage.info('搜索完成')
}

// 重置待审核列表搜索
const resetPendingSearch = () => {
  pendingSearchKeyword.value = ''
  pendingSearchForm.value.dateRange = []
  pendingPagination.value.currentPage = 1
  ElMessage.info('搜索已重置')
}

// 待审核列表分页处理
const handlePendingPageChange = (page: number) => {
  pendingPagination.value.currentPage = page
}

const handlePendingPageSizeChange = (size: number) => {
  pendingPagination.value.pageSize = size
  pendingPagination.value.currentPage = 1
}

// 已审核列表分页处理
const handleReviewedPageChange = (page: number) => {
  reviewedPagination.value.currentPage = page
}

const handleReviewedPageSizeChange = (size: number) => {
  reviewedPagination.value.pageSize = size
  reviewedPagination.value.currentPage = 1
}

// 筛选功能
const handleSearch = () => {
  // 重置到第一页
  reviewedPagination.value.currentPage = 1
  
  ElMessage.success(`筛选完成，找到 ${filteredReviewedList.value.length} 篇论文`)
}

const resetFilter = () => {
  filterForm.value = {
    status: '',
    dateRange: [],
    keyword: ''
  }
  
  // 重置分页
  reviewedPagination.value.currentPage = 1
  
  ElMessage.info('筛选已重置')
}

</script>

<style scoped>
.preliminary-review {
  padding: 20px;
}

.filter-card {
  margin-bottom: 20px;
}

.content-card {
  margin-bottom: 20px;
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

.review-list-card {
  margin-bottom: 20px;
}

.reviewed-list-card {
  margin-bottom: 20px;
}


.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
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

/* 上传按钮自定义样式 */
.upload-btn {
  background-color: #9c0e0e !important;
  border-color: #9c0e0e !important;
  color: white !important;
}

.upload-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

/* 确定按钮自定义样式 */
.confirm-btn {
  background-color: #9c0e0e !important;
  border-color: #9c0e0e !important;
  color: white !important;
}

.confirm-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-header h3 {
  margin: 0;
  color: #333;
}

.total-count {
  color: #666;
  font-size: 14px;
}

.add-paper-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.add-paper-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
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

/* 操作按钮统一样式 */
.view-btn, .audit-btn, .edit-btn, .delete-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

.view-btn:hover, .audit-btn:hover, .edit-btn:hover, .delete-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #91d5ff !important;
  color: #1890ff !important;
}
</style>
