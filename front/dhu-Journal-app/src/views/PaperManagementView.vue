<template>
  <div class="paper-management">
    

    <!-- 筛选区域 -->
    <el-card class="filter-card">
      <el-form :model="filterForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="期刊刊期">
              <el-select v-model="filterForm.issue" placeholder="请选择刊期" clearable>
                <el-option label="2024年第1期" value="2024-1" />
                <el-option label="2024年第2期" value="2024-2" />
                <el-option label="2024年第3期" value="2024-3" />
                <el-option label="2023年第4期" value="2023-4" />
                <el-option label="2023年第3期" value="2023-3" />
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
        <el-button size="small" type="warning" @click="handleBatchMove">
          批量移动
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
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ scope.row.status }}
            </el-tag>
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
}

interface FilterForm {
  issue: string
  status: string
  keyword: string
}

const filterForm = ref<FilterForm>({
  issue: '',
  status: '',
  keyword: ''
})

const selectedPapers = ref<Paper[]>([])
const currentPage = ref(1)
const pageSize = ref(10)

// 论文列表数据 - 从后端API获取
const allPaperList = ref<Paper[]>([])

// 过滤后的论文列表
const filteredPaperList = computed(() => {
  return allPaperList.value.filter(paper => {
    // 刊期筛选：使用value值进行匹配
    const matchesIssue = !filterForm.value.issue || 
      paper.journalIssue.includes(filterForm.value.issue.replace('-', '年第') + '期')
    
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
  ElMessage.info(`查看论文: ${paper.title}`)
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
    // 这里添加删除逻辑
    ElMessage.success('论文删除成功')
  } catch {
    ElMessage.info('取消删除')
  }
}

const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedPapers.value.length} 篇论文吗？`, '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    // 这里添加批量删除逻辑
    ElMessage.success('批量删除成功')
    selectedPapers.value = []
  } catch {
    ElMessage.info('取消批量删除')
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
        ElMessage.success('论文添加成功！系统已自动解析论文信息')
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

// 加载论文列表
const loadPapers = async () => {
  try {
    const response = await fetch('http://localhost:5000/api/papers')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
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
        submitDate: paper.created_at ? paper.created_at.split('T')[0] : new Date().toISOString().split('T')[0]
      }))
      ElMessage.success(`成功加载 ${papers.length} 篇论文`)
    } else {
      allPaperList.value = []
      ElMessage.info('暂无论文数据')
    }
  } catch (error) {
    console.error('加载论文列表失败:', error)
    ElMessage.error('加载论文列表失败，请确保后端服务已启动')
    allPaperList.value = []
  }
}

// 页面加载时获取论文列表
onMounted(() => {
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

.delete-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #3f4041ff !important;
  color: #7a7d80ff !important;
}
</style>
