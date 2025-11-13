<template>
  <el-config-provider :locale="zhCn">
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
    <el-dialog v-model="showReviewDialog" title="论文审核" width="900px">
      <div class="review-content">
        <p class="paper-title-display"><strong>论文标题：</strong>{{ currentPaper?.title }}</p>
        
         <!-- 格式检测区域 -->
         <el-card class="format-check-card" shadow="never">
           <template #header>
             <div class="card-header-format">
               <span>论文格式检测</span>
               <el-button 
                 v-if="!isFormatChecking && !formatCheckResult"
                 class="check-format-btn" 
                 size="small"
                 @click="showModuleSelector"
                 :disabled="!currentPaper?.file"
               >
                 选择检测模块
               </el-button>
             </div>
           </template>
          
          <!-- 检测状态提示 -->
          <div v-if="!currentPaper?.file" class="format-hint">
            <el-alert title="请先上传论文文件才能进行格式检测" type="info" :closable="false" />
          </div>
          
          <!-- 检测进度 -->
          <div v-if="isFormatChecking" class="format-checking">
            <el-progress :percentage="formatCheckProgress" />
            <p style="text-align: center; margin-top: 10px; color: #666;">
              正在检测论文格式，请稍候...
            </p>
          </div>
          
          <!-- 检测结果 -->
          <div v-if="formatCheckResult && !isFormatChecking" class="format-result">
            <div class="result-summary">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="总检测项">
                  {{ formatCheckResult.data?.summary.total_checks || 0 }}
                </el-descriptions-item>
                <el-descriptions-item label="通过项">
                  <span style="color: #67c23a;">{{ formatCheckResult.data?.summary.passed_checks || 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="失败项">
                  <span style="color: #f56c6c;">{{ formatCheckResult.data?.summary.failed_checks || 0 }}</span>
                </el-descriptions-item>
                <el-descriptions-item label="通过率">
                  <el-tag :type="getPassRateType(formatCheckResult.data?.summary.pass_rate || 0)">
                    {{ formatCheckResult.data?.summary.pass_rate || 0 }}%
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
            </div>
            
            <!-- 详细结果折叠面板 -->
            <el-collapse v-model="activeModules" class="result-details" accordion>
              <el-collapse-item
                v-for="(moduleResult, moduleName) in formatCheckResult.data?.results"
                :key="moduleName"
                :name="moduleName"
              >
                <template #title>
                  <div class="module-title">
                    <span class="module-name">{{ moduleName }}</span>
                    <el-tag
                      :type="getModuleStatusType(moduleResult)"
                      size="small"
                      style="margin-left: 10px;"
                    >
                      {{ getModuleStatus(moduleResult) }}
                    </el-tag>
                  </div>
                </template>
                
                <div class="module-checks">
                  <div
                    v-for="(check, checkName) in moduleResult.checks"
                    :key="checkName"
                    class="check-item-inline"
                  >
                    <div class="check-header-inline">
                      <span :class="['check-icon', check.ok ? 'success' : 'error']">
                        {{ check.ok ? '✓' : '✗' }}
                      </span>
                      <span class="check-name-text">{{ checkName }}</span>
                    </div>
                    <div v-if="check.messages && check.messages.length > 0" class="check-messages-inline">
                      <div v-for="(message, index) in check.messages" :key="index" class="message-text">
                        • {{ message }}
                      </div>
                    </div>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
            
            <div class="format-actions">
              <el-button size="small" @click="resetFormatCheck">重新检测</el-button>
              <el-button class="view-report-btn" size="small" @click="viewDetailReport">查看详细报告</el-button>
            </div>
          </div>
        </el-card>
        
        <!-- 审核表单 -->
        <el-form :model="reviewForm" label-width="80px" style="margin-top: 20px;">
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
              :rows="4"
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
    
    <!-- 详细报告对话框 -->
    <el-dialog v-model="showReportDialog" title="格式检测详细报告" width="800px">
      <div class="report-content">
        <pre>{{ reportText }}</pre>
      </div>
      <template #footer>
        <el-button @click="showReportDialog = false">关闭</el-button>
        <el-button class="download-report-btn" type="primary" @click="downloadReport">下载报告</el-button>
      </template>
    </el-dialog>
    
    <!-- 检测模块选择对话框 -->
    <el-dialog v-model="showModuleSelectorDialog" title="选择检测模块" width="600px">
      <div class="module-selector-content">
        <el-alert 
          title="请选择需要检测的内容模块" 
          type="info" 
          :closable="false"
          style="margin-bottom: 20px;"
        />
        
        <!-- 全选选项 -->
        <div class="module-option">
          <el-checkbox 
            v-model="selectAllModules" 
            @change="handleSelectAll"
            :indeterminate="isIndeterminate"
          >
            <span class="module-label">全部检测</span>
          </el-checkbox>
        </div>
        
        <el-divider />
        
        <!-- 各检测模块 -->
        <el-checkbox-group v-model="selectedModules" @change="handleModuleChange">
          <div class="module-option" v-for="module in availableModules" :key="module.value">
            <el-checkbox :value="module.value">
              <span class="module-label">{{ module.label }}</span>
              <span class="module-description">{{ module.description }}</span>
            </el-checkbox>
          </div>
        </el-checkbox-group>
        
        <!-- 图片内容检测选项 -->
        <div v-if="selectedModules.includes('Figure')" class="figure-api-option">
          <!-- <el-divider /> -->
          <el-alert 
            title="图片检测选项" 
            type="warning" 
            :closable="false"
            style="margin-bottom: 10px;padding: 0"
          />
          <el-checkbox v-model="enableFigureApi" style="padding-bottom: 10px;">
            <span class="module-label">启用图片内容检测</span>
            <span class="module-description">*需要调用API，检测时间较长</span>
          </el-checkbox>
        </div>
      </div>
      
      <template #footer>
        <el-button @click="showModuleSelectorDialog = false">取消</el-button>
        <el-button 
          class="confirm-btn" 
          type="primary" 
          @click="confirmModuleSelection"
          :disabled="selectedModules.length === 0"
        >
          开始检测
        </el-button>
      </template>
    </el-dialog>
  </div>
  </el-config-provider>   
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { paperFormatService } from '@/api/paperFormatService'
import type { ApiResponse, CheckAllResult } from '@/api/paperFormatService'
import zhCn from 'element-plus/es/locale/lang/zh-cn'


interface Paper {
  id: number
  title: string
  file?: File
  submitDate?: string
  reviewDate?: string
  reviewStatus?: string
  comment?: string
  formatCheckResult?: ApiResponse<CheckAllResult>
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
const showReportDialog = ref(false)
const showModuleSelectorDialog = ref(false)

// 表单数据
const newPaper = ref({
  title: '',
  submitDate: new Date().toISOString().split('T')[0],
  file: null as File | null
})

const reviewForm = ref({
  status: '',
  comment: ''
})

const currentPaper = ref<Paper | null>(null)

// 格式检测相关状态
const isFormatChecking = ref(false)
const formatCheckProgress = ref(0)
const formatCheckResult = ref<ApiResponse<CheckAllResult> | null>(null)
const activeModules = ref<string>('')
const reportText = ref('')

// 模块选择相关状态
const selectedModules = ref<string[]>([])
const selectAllModules = ref(false)
const enableFigureApi = ref(false)

// 可用的检测模块列表
const availableModules = [
  { value: 'Title', label: '标题格式检测', description: '检测标题、作者、单位格式' },
  { value: 'Abstract', label: '摘要格式检测', description: '检测摘要结构和格式' },
  { value: 'Keywords', label: '关键词格式检测', description: '检测关键词格式' },
  { value: 'Content', label: '正文格式检测', description: '检测正文格式' },
  { value: 'Formula', label: '公式格式检测', description: '检测公式编号和格式' },
  { value: 'Figure', label: '图片格式检测', description: '检测图片格式和编号' },
  { value: 'Table', label: '表格格式检测', description: '检测表格格式和编号' }
]

// 计算是否为半选状态
const isIndeterminate = computed(() => {
  const selected = selectedModules.value.length
  const total = availableModules.length
  return selected > 0 && selected < total
})

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
  newPaper.value.title = file.name.split('.')[0]
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
  newPaper.value = { title: '', submitDate: new Date().toISOString().split('T')[0], file: null }
  showAddDialog.value = false
}

// 审核论文
const handleReview = (paper: Paper) => {
  console.log(paper)
  currentPaper.value = paper
  reviewForm.value = { status: '', comment: '' }
  // 重置格式检测状态
  formatCheckResult.value = null
  isFormatChecking.value = false
  formatCheckProgress.value = 0
  activeModules.value = ''
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
    comment: reviewForm.value.comment,
    formatCheckResult: formatCheckResult.value || undefined
  }
  reviewedList.value.push(reviewedPaper)
  
  ElMessage.success('审核完成')
  showReviewDialog.value = false
}

// 模块选择相关方法
const showModuleSelector = () => {
  if (!currentPaper.value?.file) {
    ElMessage.error('请先选择论文文件')
    return
  }
  
  // 重置选择状态
  selectedModules.value = []
  selectAllModules.value = false
  enableFigureApi.value = false
  
  // 显示选择对话框
  showModuleSelectorDialog.value = true
}

const handleSelectAll = (value: boolean) => {
  if (value) {
    selectedModules.value = availableModules.map(m => m.value)
  } else {
    selectedModules.value = []
  }
}

const handleModuleChange = (value: string[]) => {
  selectAllModules.value = value.length === availableModules.length
  
  // 如果取消了图片检测，也取消图片内容检测
  if (!value.includes('Figure')) {
    enableFigureApi.value = false
  }
}

const confirmModuleSelection = () => {
  if (selectedModules.value.length === 0) {
    ElMessage.warning('请至少选择一个检测模块')
    return
  }
  
  // 关闭选择对话框
  showModuleSelectorDialog.value = false
  
  // 开始检测
  startFormatCheck()
}

// 格式检测相关方法
const startFormatCheck = async () => {
  if (!currentPaper.value?.file) {
    ElMessage.error('请先选择论文文件')
    return
  }
  
  try {
    isFormatChecking.value = true
    formatCheckProgress.value = 0
    
    // 模拟进度更新
    const progressInterval = setInterval(() => {
      if (formatCheckProgress.value < 90) {
        formatCheckProgress.value += 10
      }
    }, 500)
    
    // 执行格式检测
    const result = await paperFormatService.checkAll(
      currentPaper.value.file, 
      enableFigureApi.value,
      selectedModules.value
    )
    
    clearInterval(progressInterval)
    formatCheckProgress.value = 100
    
    // 保存检测结果
    formatCheckResult.value = result
    
    if (result.success) {
      ElMessage.success('格式检测完成，报告已自动保存')
      
      // 如果返回了报告信息，可以提示用户
      if (result.data?.report_saved) {
        console.log('报告已保存:', result.data.report_filename)
        reportText.value = result.data.report_text
      }
    } else {
      ElMessage.error(result.message || '格式检测失败')
    }
    
  } catch (error) {
    ElMessage.error('格式检测失败：' + (error as Error).message)
  } finally {
    setTimeout(() => {
      isFormatChecking.value = false
    }, 300)
  }
}

// 重新检测
const resetFormatCheck = () => {
  formatCheckResult.value = null
  formatCheckProgress.value = 0
  activeModules.value = ''
  isFormatChecking.value = false
  
  // 显示模块选择对话框
  showModuleSelector()
}

// 查看详细报告
const viewDetailReport = async () => {
  if (!formatCheckResult.value) {
    ElMessage.error('无检测结果')
    return
  }
  if(!reportText.value){
    ElMessage.error('无检测报告')
    return
  }

  showReportDialog.value = true
  
  // try {
  //   const reportResult = await paperFormatService.generateReport(formatCheckResult.value)
  //
  //   if (reportResult.success && reportResult.data) {
  //     reportText.value = reportResult.data.report_text
  //     showReportDialog.value = true
  //   } else {
  //     ElMessage.error('生成报告失败')
  //   }
  // } catch (error) {
  //   ElMessage.error('生成报告失败：' + (error as Error).message)
  // }
}

// 下载报告
const downloadReport = () => {
  if (!reportText.value) {
    ElMessage.error('无报告内容')
    return
  }
  
  // 创建Blob对象
  const blob = new Blob([reportText.value], { type: 'text/plain;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  
  // 创建下载链接
  const link = document.createElement('a')
  link.href = url
  link.download = `论文格式检测报告_${currentPaper.value?.title || '未命名'}_${new Date().getTime()}.txt`
  document.body.appendChild(link)
  link.click()
  
  // 清理
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
  
  ElMessage.success('报告下载成功')
}

const getPassRateType = (passRate: number) => {
  if (passRate >= 90) return 'success'
  if (passRate >= 70) return 'warning'
  return 'danger'
}

const getModuleStatus = (moduleResult: any) => {
  const checks = moduleResult.checks || {}
  const checkValues = Object.values(checks)
  
  if (checkValues.length === 0) return '未检测'
  
  const allPassed = checkValues.every((check: any) => check.ok === true)
  if (allPassed) return '全部通过'
  
  const allFailed = checkValues.every((check: any) => check.ok === false)
  if (allFailed) return '全部失败'
  
  return '部分通过'
}

const getModuleStatusType = (moduleResult: any) => {
  const status = getModuleStatus(moduleResult)
  
  if (status === '全部通过') return 'success'
  if (status === '全部失败') return 'danger'
  if (status === '部分通过') return 'warning'
  return 'info'
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

// 重置
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

/* 格式检测相关样式 */
.format-check-card {
  margin-bottom: 20px;
  border: 1px solid #ebeef5;
}

.card-header-format {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.check-format-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.check-format-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

.format-hint {
  padding: 10px 0;
}

.format-checking {
  padding: 20px 0;
}

.format-result {
  padding: 10px 0;
}

.result-summary {
  margin-bottom: 20px;
}

.result-details {
  margin-top: 15px;
}

.module-title {
  display: flex;
  align-items: center;
  flex: 1;
}

.module-name {
  font-weight: 500;
  color: #333;
}

.module-checks {
  padding: 10px 0;
}

.check-item-inline {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f0f0f0;
}

.check-item-inline:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.check-header-inline {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
}

.check-icon {
  font-weight: bold;
  font-size: 16px;
  margin-right: 8px;
  width: 20px;
  text-align: center;
}

.check-icon.success {
  color: #67c23a;
}

.check-icon.error {
  color: #f56c6c;
}

.check-name-text {
  font-weight: 500;
  color: #606266;
}

.check-messages-inline {
  padding-left: 28px;
  color: #909399;
  font-size: 13px;
}

.message-text {
  margin-bottom: 4px;
  line-height: 1.5;
}

.format-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.view-report-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.view-report-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

.paper-title-display {
  font-size: 14px;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}

.report-content {
  max-height: 60vh;
  overflow-y: auto;
}

.report-content pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #333;
}

.download-report-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.download-report-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

/* 模块选择器样式 */
.module-selector-content {
  padding: 10px 0;
}

.module-option {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.module-option:last-child {
  border-bottom: none;
}

.module-label {
  font-weight: 500;
  color: #303133;
  font-size: 14px;
}

.module-description {
  margin-left: 0;
  color: #909399;
  font-size: 13px;
}

.figure-api-option {
  margin-top: 10px;
  padding: 15px;
  background-color: #fdf6ec;
  border-radius: 4px;
}

:deep(.el-checkbox) {
  display: flex;
  align-items: flex-start;
  width: 100%;
}

:deep(.el-checkbox__label) {
  display: flex;
  flex-direction: column;
  gap: 4px;
  white-space: normal;
  line-height: 1.5;
}
</style>
