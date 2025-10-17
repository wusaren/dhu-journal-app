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
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

interface Paper {
  id: number
  title: string
  author: string
  journalIssue: string
  startPage: number
  endPage: number
  status: string
  submitDate: string
  file_path?: string
  stored_filename?: string
  parsing_status?: string // 解析状态：parsing, completed, failed
  parsing_progress?: number // 解析进度 0-100
}

interface FilterForm {
  issue: string
  status: string
  keyword: string
}

interface Journal {
  id: number
  title: string
  issue: string
  status: string
}

const filterForm = ref<FilterForm>({
  issue: '',
  status: '',
  keyword: ''
})

const selectedPapers = ref<Paper[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const journalList = ref<Journal[]>([])

// 论文列表数据 - 从后端API获取
const allPaperList = ref<Paper[]>([])
const parsingPapers = ref<Set<number>>(new Set()) // 正在解析的论文ID集合

// 过滤后的论文列表
const filteredPaperList = computed(() => {
  return allPaperList.value.filter(paper => {
    // 刊期筛选：直接匹配期刊刊期
    const matchesIssue = !filterForm.value.issue || 
      paper.journalIssue === filterForm.value.issue
    
    // 状态筛选：将英文状态值映射为中文状态
    const statusMap: Record<string, string> = {
      'pending': '待审核',
      'approved': '已通过', 
      'need_revision': '需修改',
      'rejected': '已拒绝'
    }
    const matchesStatus = !filterForm.value.status || 
      paper.status === statusMap[filterForm.value.status]
    
    // 关键词筛选：不区分大小写
    const matchesKeyword = !filterForm.value.keyword || 
      paper.title.toLowerCase().includes(filterForm.value.keyword.toLowerCase()) || 
      paper.author.toLowerCase().includes(filterForm.value.keyword.toLowerCase())
    
    return matchesIssue && matchesStatus && matchesKeyword
  })
})

// 分页后的论文列表
const pagedPaperList = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredPaperList.value.slice(start, end)
})

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
  currentPage.value = 1 // 搜索时重置到第一页
  ElMessage.info('搜索完成')
}

const resetFilter = () => {
  filterForm.value = {
    issue: '',
    status: '',
    keyword: ''
  }
  currentPage.value = 1
}

const handleSelectionChange = (selection: Paper[]) => {
  selectedPapers.value = selection
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (page: number) => {
  currentPage.value = page
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
  const pdfUrl = `http://localhost:5000/api/preview/${filename}`
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
    
    // 调用后端API删除论文
    const response = await fetch(`http://localhost:5000/api/papers/${paper.id}`, {
      method: 'DELETE'
    })
    
    const result = await response.json()
    
    if (response.ok && result.success) {
      ElMessage.success('论文删除成功')
      // 刷新论文列表
      loadPapers()
    } else {
      ElMessage.error(result.message || '论文删除失败')
    }
  } catch (error: any) {
    if (error === 'cancel' || error.message === 'cancel') {
      ElMessage.info('取消删除')
    } else {
      console.error('删除论文失败:', error)
      ElMessage.error('论文删除失败，请检查网络连接')
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
    
    // 批量删除论文
    const deletePromises = selectedPapers.value.map(paper => 
      fetch(`http://localhost:5000/api/papers/${paper.id}`, {
        method: 'DELETE'
      })
    )
    
    const responses = await Promise.all(deletePromises)
    const results = await Promise.all(responses.map(r => r.json()))
    
    // 检查是否所有删除都成功
    const failedCount = results.filter(r => !r.success).length
    const successCount = results.length - failedCount
    
    if (failedCount === 0) {
      ElMessage.success(`批量删除成功，共删除 ${successCount} 篇论文`)
    } else {
      ElMessage.warning(`部分删除失败，成功删除 ${successCount} 篇，失败 ${failedCount} 篇`)
    }
    
    // 刷新论文列表
    loadPapers()
    selectedPapers.value = []
  } catch (error: any) {
    if (error === 'cancel' || error.message === 'cancel') {
      ElMessage.info('取消批量删除')
    } else {
      console.error('批量删除失败:', error)
      ElMessage.error('批量删除失败，请检查网络连接')
    }
  }
}

const handleBatchDownload = async () => {
  if (selectedPapers.value.length === 0) {
    ElMessage.warning('请先选择要下载的论文')
    return
  }

  try {
    ElMessage.info(`正在批量下载 ${selectedPapers.value.length} 篇论文...`)
    
    // 检查选中的论文是否有PDF文件
    const papersWithFiles = selectedPapers.value.filter(paper => 
      paper.file_path || paper.stored_filename
    )
    
    if (papersWithFiles.length === 0) {
      ElMessage.warning('选中的论文都没有PDF文件')
      return
    }
    
    // 逐个下载PDF文件
    for (const paper of papersWithFiles) {
      // 从文件路径中提取文件名
      let filename = ''
      if (paper.file_path) {
        const pathParts = paper.file_path.split(/[\\/]/)
        filename = pathParts[pathParts.length - 1]
      } else if (paper.stored_filename) {
        filename = paper.stored_filename
      }
      
      if (filename) {
        // 使用下载API下载PDF文件
        const downloadUrl = `http://localhost:5000/api/download/${filename}`
        
        // 创建下载链接并触发下载
        const link = document.createElement('a')
        link.href = downloadUrl
        link.download = filename
        link.style.display = 'none'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        
        // 添加小延迟避免浏览器限制
        await new Promise(resolve => setTimeout(resolve, 100))
      }
    }
    
    ElMessage.success(`批量下载完成，共下载 ${papersWithFiles.length} 篇论文`)
    
  } catch (error) {
    console.error('批量下载失败:', error)
    ElMessage.error('批量下载失败，请稍后重试')
  }
}

const handleBatchMove = () => {
  ElMessage.info('批量移动功能待实现')
}

const handleAddPaper = () => {
  // 创建文件输入元素
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.pdf'
  input.style.display = 'none'
  
  input.onchange = async (event: any) => {
    const file = event.target.files[0]
    if (!file) return
    
    if (file.type !== 'application/pdf') {
      ElMessage.error('请选择PDF文件')
      return
    }
    
    try {
      // 检查论文是否已存在
      const existingPapers = await checkPaperExists(file.name)
      if (existingPapers.length > 0) {
        ElMessage.warning(`论文 "${file.name}" 已存在于数据库中，不可重复上传`)
        return
      }
      
      ElMessage.info('正在上传并解析论文...')
      
      const formData = new FormData()
      formData.append('file', file)
      formData.append('journalId', '1') // 默认期刊ID
      
      const response = await fetch('http://localhost:5000/api/upload', {
        method: 'POST',
        body: formData
      })
      
      const result = await response.json()
      
      if (response.ok) {
        if (result.duplicate) {
          ElMessage.warning(result.message || '文件已存在，跳过重复上传')
        } else if (result.warning) {
          ElMessage.warning(result.message || '文件上传成功，但未能解析出论文信息')
        } else if (result.error) {
          ElMessage.error(result.message || '文件上传失败')
        } else {
          // 检查是否创建了新期刊
          if (result.journalCreated && result.journalInfo) {
            const journalTitle = result.journalInfo.title
            const journalIssue = result.journalInfo.issue
            ElMessage.success(`已为您在期刊管理页面创建期刊 ${journalTitle}（${journalIssue}）`)
          } else {
            ElMessage.success(result.message || '论文添加成功！系统已自动解析论文信息')
          }
          
          // 如果上传成功且有期刊ID，开始轮询解析状态
          if (result.journalId) {
            startParsingStatusPolling(result.journalId)
          }
        }
        // 刷新论文列表
        loadPapers()
      } else {
        ElMessage.error(result.message || '论文上传失败')
      }
    } catch (error) {
      console.error('上传失败:', error)
      ElMessage.error('论文上传失败，请检查网络连接')
    }
  }
  
  // 触发文件选择
  document.body.appendChild(input)
  input.click()
  document.body.removeChild(input)
}

// 开始解析状态轮询
const startParsingStatusPolling = (journalId: number) => {
  const pollingInterval = setInterval(async () => {
    try {
      // 获取该期刊的所有论文
      const response = await fetch(`http://localhost:5000/api/papers?journalId=${journalId}`)
      const papers = await response.json()
      
      if (papers && papers.length > 0) {
        // 检查是否有正在解析的论文
        const parsingPapersInJournal = papers.filter((paper: any) => 
          paper.parsing_status === 'parsing'
        )
        
        if (parsingPapersInJournal.length === 0) {
          // 所有论文解析完成，停止轮询
          clearInterval(pollingInterval)
          ElMessage.success('所有论文解析完成！')
          // 刷新论文列表显示最终状态
          loadPapers()
        } else {
          // 更新正在解析的论文状态
          updateParsingPapersStatus(papers)
        }
      } else {
        // 没有论文数据，停止轮询
        clearInterval(pollingInterval)
      }
    } catch (error) {
      console.error('轮询解析状态失败:', error)
      // 发生错误时停止轮询
      clearInterval(pollingInterval)
    }
  }, 3000) // 每3秒轮询一次
  
  // 设置最大轮询时间（5分钟）
  setTimeout(() => {
    clearInterval(pollingInterval)
    ElMessage.warning('论文解析超时，请检查解析状态')
  }, 5 * 60 * 1000)
}

// 更新正在解析的论文状态
const updateParsingPapersStatus = (papers: any[]) => {
  papers.forEach((paper: any) => {
    if (paper.parsing_status === 'parsing') {
      // 找到对应的论文并更新状态
      const existingPaper = allPaperList.value.find(p => p.id === paper.id)
      if (existingPaper) {
        existingPaper.parsing_status = paper.parsing_status
        existingPaper.parsing_progress = paper.parsing_progress || 0
      } else {
        // 如果是新论文，添加到列表并标记为解析中
        const newPaper: Paper = {
          id: paper.id,
          title: paper.title || '正在解析中...',
          author: paper.authors || paper.first_author || '未知作者',
          journalIssue: paper.issue || '未知刊期',
          startPage: paper.page_start || 0,
          endPage: paper.page_end || 0,
          status: '待审核',
          submitDate: paper.created_at ? paper.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
          file_path: paper.file_path,
          stored_filename: paper.stored_filename,
          parsing_status: paper.parsing_status,
          parsing_progress: paper.parsing_progress || 0
        }
        allPaperList.value.unshift(newPaper)
      }
    }
  })
}

// 检查论文是否已存在
const checkPaperExists = async (filename: string): Promise<Paper[]> => {
  try {
    // 获取所有论文
    const response = await fetch('http://localhost:5000/api/papers')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const papers = await response.json()
    
    // 检查是否有相同文件名的论文
    const existingPapers = papers.filter((paper: any) => {
      // 检查文件路径或存储文件名是否匹配
      const filePath = paper.file_path || ''
      const storedFilename = paper.stored_filename || ''
      return filePath.includes(filename) || storedFilename.includes(filename)
    })
    
    return existingPapers
  } catch (error) {
    console.error('检查论文存在性失败:', error)
    return []
  }
}

// 加载期刊列表
const loadJournals = async () => {
  try {
    const response = await fetch('http://localhost:5000/api/journals')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const journals = await response.json()
    
    if (journals && journals.length > 0) {
      journalList.value = journals.map((journal: any) => ({
        id: journal.id,
        title: journal.title,
        issue: journal.issue,
        status: journal.status
      }))
      console.log('成功加载期刊列表:', journalList.value)
    } else {
      journalList.value = []
      console.log('暂无期刊数据')
    }
  } catch (error) {
    console.error('加载期刊列表失败:', error)
    journalList.value = []
  }
}

// 加载论文列表
const loadPapers = async () => {
  try {
    const response = await fetch('http://localhost:5000/api/papers')
    const papers = await response.json()
    
    if (papers && papers.length > 0) {
      // 将API数据转换为前端格式
      allPaperList.value = papers.map((paper: any) => ({
        id: paper.id,
        title: paper.title || '无标题',
        author: paper.authors || paper.first_author || '未知作者',
        journalIssue: paper.issue || '未知刊期',
        startPage: paper.page_start || 0,
        endPage: paper.page_end || 0,
        status: '待审核', // 默认状态，实际应该从数据库获取
        submitDate: paper.created_at ? paper.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
        file_path: paper.file_path,
        stored_filename: paper.stored_filename,
        parsing_status: paper.parsing_status, // 解析状态
        parsing_progress: paper.parsing_progress || 0 // 解析进度
      }))
      ElMessage.success(`成功加载 ${papers.length} 篇论文`)
    } else {
      allPaperList.value = []
      ElMessage.info('暂无论文数据')
    }
  } catch (error) {
    console.error('加载论文列表失败:', error)
    ElMessage.error('加载论文列表失败')
  }
}

// 页面加载时获取数据
onMounted(() => {
  loadJournals()
  loadPapers()
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
