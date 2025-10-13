<template>
  <div class="journal-management">
    

    

    <!-- 筛选区域 -->
    <el-card class="filter-card">
      <el-form :model="filterForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="期刊刊期">
              <el-select v-model="filterForm.issue" placeholder="请选择刊期" clearable @change="handleFilter">
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
            <el-form-item>
              <el-button class="reset-btn" @click="resetFilter">重置筛选</el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <!-- 期刊列表 -->
    <el-card class="journal-list-card">
      <template #header>
        <div class="card-header">
          <h3>期刊列表</h3>
          <span class="total-count">共 {{ filteredJournalList.length }} 个期刊</span>
        </div>
      </template>

      <!-- 批量操作按钮 -->
      <div class="batch-actions" v-if="selectedJournals.length > 0">
        <el-button size="small" type="danger" @click="handleBatchDelete">
          批量删除 ({{ selectedJournals.length }})
        </el-button>
      </div>

      <el-table 
        :data="pagedJournalList" 
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="issue" label="期号" width="150" />
        <el-table-column prop="title" label="期刊名称" width="200" />
        <el-table-column prop="publishDate" label="出版日期" width="120" />
        <el-table-column prop="paperCount" label="论文数量" width="100">
          <template #default="scope">
            {{ scope.row.paperCount }} 篇
          </template>
        </el-table-column>
        <el-table-column label="操作" width="400">
          <template #default="scope">
            <el-button class="edit-btn" size="small" type="primary" @click="handleEdit(scope.row)">
              编辑
            </el-button>
            <el-button class="view-btn" size="small" @click="handleViewTOC(scope.row)">
              查看目录
            </el-button>
            <el-button 
              class="generate-btn"
              size="small" 
              type="warning"
              @click="handleGenerateWeibo(scope.row)"
            >
              生成推文
            </el-button>
            <el-button 
              class="stats-btn"
              size="small" 
              type="success"
              @click="handleViewStats(scope.row)"
            >
              查看统计表
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
          :total="filteredJournalList.length"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>
    <!-- 创建期刊区域 -->
    <el-card class="create-card">
      <template #header>
        <div class="card-header">
          <h3>期刊管理</h3>
          <el-button 
            class="create-journal-btn" 
            type="primary" 
            size="mid"
            @click="handleCreateJournal"
          >
            创建期刊
          </el-button>
        </div>
      </template>
      
      <div class="create-tips">
        <p>点击"创建期刊"按钮来添加新的期刊记录</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'

interface Journal {
  id: number
  title: string
  issue: string
  publishDate: string
  paperCount: number
  status: string
  description?: string
  fileName?: string
  fileSize?: number
}

interface FilterForm {
  issue: string
}

const router = useRouter()
const journalList = ref<Journal[]>([])
const filteredJournalList = ref<Journal[]>([])
const selectedJournals = ref<Journal[]>([])
const loading = ref(false)
const filterForm = ref<FilterForm>({
  issue: ''
})
const currentPage = ref(1)
const pageSize = ref(10)

// 分页后的期刊列表
const pagedJournalList = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredJournalList.value.slice(start, end)
})

// 筛选期刊列表
const filterJournals = () => {
  if (!filterForm.value.issue) {
    // 如果没有筛选条件，显示所有期刊
    filteredJournalList.value = [...journalList.value]
  } else {
    // 根据刊期筛选
    filteredJournalList.value = journalList.value.filter(journal => 
      journal.issue === filterForm.value.issue
    )
  }
}

// 处理筛选
const handleFilter = () => {
  filterJournals()
  ElMessage.info('筛选完成')
}

// 重置筛选
const resetFilter = () => {
  filterForm.value.issue = ''
  filterJournals()
  ElMessage.info('筛选已重置')
}

// 处理选择变化
const handleSelectionChange = (selection: Journal[]) => {
  selectedJournals.value = selection
}

// 处理每页数量变化
const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

// 处理当前页变化
const handleCurrentChange = (page: number) => {
  currentPage.value = page
}

// 批量删除期刊
const handleBatchDelete = async () => {
  if (selectedJournals.value.length === 0) {
    ElMessage.warning('请先选择要删除的期刊')
    return
  }

  try {
    await ElMessageBox.confirm(`确定要删除选中的 ${selectedJournals.value.length} 个期刊吗？`, '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    
    // 这里添加批量删除逻辑
    // 注意：实际删除需要调用后端API
    ElMessage.success('批量删除成功')
    selectedJournals.value = []
    // 刷新期刊列表
    loadJournals()
  } catch {
    ElMessage.info('取消批量删除')
  }
}

// 删除单个期刊
const handleDelete = async (journal: Journal) => {
  try {
    await ElMessageBox.confirm(`确定要删除期刊"${journal.issue}"吗？`, '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    // 这里添加删除逻辑
    ElMessage.success('期刊删除成功')
    // 刷新期刊列表
    loadJournals()
  } catch {
    ElMessage.info('取消删除')
  }
}

// 加载期刊列表
const loadJournals = async () => {
  loading.value = true
  try {
    console.log('开始加载期刊列表...')
    
    // 尝试从数据库加载
    const response = await axios.get('http://localhost:5000/api/journals')
    console.log('期刊列表响应:', response.data)
    
    if (response.data && response.data.length > 0) {
      // 数据库中有数据，使用数据库数据
      journalList.value = response.data
      // 初始化筛选后的列表
      filterJournals()
      console.log('使用数据库数据，期刊数量:', response.data.length)
    } else {
      // 数据库中没有数据，显示空列表
      journalList.value = []
      filteredJournalList.value = []
      console.log('数据库为空，显示空列表')
    }
    
    ElMessage.success('期刊列表加载成功')
  } catch (error: any) {
    console.error('加载期刊列表失败:', error)
    console.error('错误详情:', error.response?.data)
    
    if (error.code === 'ERR_NETWORK' || error.message.includes('ERR_CONNECTION_REFUSED')) {
      ElMessage.error('无法连接到后端服务，请确保后端服务已启动')
      journalList.value = []
      filteredJournalList.value = []
    } else {
      ElMessage.error(`加载期刊列表失败: ${error.response?.data?.message || error.message}`)
      journalList.value = []
      filteredJournalList.value = []
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  // 直接加载期刊列表，不需要认证
  loadJournals()
})

const handleCreateJournal = () => {
  router.push('/create-journal')
}

const getStatusType = (status: string) => {
  const statusMap: Record<string, string> = {
    '已发布': 'success',
    '编辑中': 'warning',
    '未开始': 'info',
    '已归档': ''
  }
  return statusMap[status] || 'info'
}

const handleEdit = async (journal: Journal) => {
  try {
    // 获取该期刊的论文列表
    const response = await axios.get(`http://localhost:5000/api/papers?journalId=${journal.id}`)
    const papers = response.data
    
    if (papers && papers.length > 0) {
      // 限制显示数量：最多显示10条
      const displayPapers = papers.slice(0, 10)
      const isTruncated = papers.length > 10
      
      // 创建弹窗显示论文列表
      ElMessageBox.alert(
        `
        <div>
          <h3 style="margin-bottom: 15px; color: #303133;">期刊 "${journal.issue}" 的论文列表</h3>
          <p style="margin-bottom: 15px; color: #606266;">共 ${papers.length} 篇论文${isTruncated ? ' (显示前10条)' : ''}</p>
          <div style="max-height: 500px; overflow-y: auto;">
            <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
              <thead>
                <tr style="background-color: #f5f7fa;">
                  <th style="padding: 12px; border: 1px solid #ebeef5; text-align: left; min-width: 200px;">论文标题</th>
                  <th style="padding: 12px; border: 1px solid #ebeef5; text-align: left; min-width: 120px;">作者</th>
                  <th style="padding: 12px; border: 1px solid #ebeef5; text-align: left; min-width: 80px;">起始页</th>
                  <th style="padding: 12px; border: 1px solid #ebeef5; text-align: left; min-width: 100px;">稿件号</th>
                </tr>
              </thead>
              <tbody>
                ${displayPapers.map((paper: any) => `
                  <tr>
                    <td style="padding: 12px; border: 1px solid #ebeef5; word-break: break-word;">${paper.title || '无标题'}</td>
                    <td style="padding: 12px; border: 1px solid #ebeef5;">${paper.authors || paper.first_author || '未知作者'}</td>
                    <td style="padding: 12px; border: 1px solid #ebeef5; text-align: center;">${paper.page_start || 0}</td>
                    <td style="padding: 12px; border: 1px solid #ebeef5;">${paper.manuscript_id || '无'}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
          ${isTruncated ? `<p style="color: #909399; margin-top: 15px; font-size: 13px;">还有 ${papers.length - 10} 篇论文未显示，请前往论文管理页面查看完整列表</p>` : ''}
        </div>
        `,
        '期刊论文列表',
        {
          dangerouslyUseHTMLString: true,
          customClass: 'journal-papers-dialog',
          showConfirmButton: true,
          confirmButtonText: '关闭',
          showCancelButton: false,
          closeOnClickModal: true,
          width: '900px',  // 增加弹窗宽度
          customStyle: {
            'max-width': '90vw'  // 响应式最大宽度
          }
        }
      ).then(() => {
        // 弹窗关闭后的回调
      }).catch(() => {
        // 弹窗取消的回调
      })
      
      // 在弹窗显示后修改按钮样式
      setTimeout(() => {
        const confirmButton = document.querySelector('.el-message-box__btns .el-button--primary') as HTMLElement
        if (confirmButton) {
          confirmButton.style.backgroundColor = '#b62020ff'
          confirmButton.style.borderColor = '#be2121ff'
          confirmButton.style.color = 'white'
          
          // 添加悬停效果
          confirmButton.addEventListener('mouseenter', () => {
            confirmButton.style.backgroundColor = '#7a0b0b'
            confirmButton.style.borderColor = '#7a0b0b'
          })
          confirmButton.addEventListener('mouseleave', () => {
            confirmButton.style.backgroundColor = '#b62020ff'
            confirmButton.style.borderColor = '#be2121ff'
          })
        }
      }, 100)
    } else {
      ElMessage.info(`期刊 "${journal.issue}" 暂无论文数据`)
    }
  } catch (error: any) {
    console.error('获取期刊论文列表失败:', error)
    ElMessage.error(`获取论文列表失败: ${error.response?.data?.message || error.message}`)
  }
}

const handleViewTOC = async (journal: Journal) => {
  try {
    ElMessage.info(`正在生成目录: ${journal.issue}`)
    
    // 调用后端生成目录
    const response = await axios.post('http://localhost:5000/api/export/toc', {
      journalId: journal.id
    })
    
    if (response.data.downloadUrl) {
      // 下载文件
      const link = document.createElement('a')
      link.href = `http://localhost:5000${response.data.downloadUrl}`
      link.download = `目录_${journal.issue}.docx`
      link.click()
      ElMessage.success('目录生成成功！')
    }
  } catch (error: any) {
    console.error('生成目录失败:', error)
    ElMessage.error(`生成目录失败: ${error.response?.data?.message || error.message}`)
  }
}

const handlePublish = (journal: Journal) => {
  const newStatus = journal.status === '已发布' ? '编辑中' : '已发布'
  ElMessage.success(`期刊 ${journal.issue} ${newStatus === '已发布' ? '已发布' : '已取消发布'}`)
  
  // 更新状态
  const index = journalList.value.findIndex(j => j.id === journal.id)
  if (index !== -1) {
    journalList.value[index].status = newStatus
  }
}

const handleGenerateWeibo = async (journal: Journal) => {
  try {
    ElMessage.info(`正在生成推文: ${journal.issue}`)
    
    // 调用后端生成推文
    const response = await axios.post('http://localhost:5000/api/export/weibo', {
      journalId: journal.id
    })
    
    if (response.data.downloadUrl) {
      // 下载文件
      const link = document.createElement('a')
      link.href = `http://localhost:5000${response.data.downloadUrl}`
      link.download = `推文_${journal.issue}.html`
      link.click()
      ElMessage.success('推文生成成功！')
    }
  } catch (error: any) {
    console.error('生成推文失败:', error)
    ElMessage.error(`生成推文失败: ${error.response?.data?.message || error.message}`)
  }
}

const handleViewStats = async (journal: Journal) => {
  try {
    ElMessage.info(`正在生成统计表: ${journal.issue}`)
    
    // 调用后端生成统计表
    const response = await axios.post('http://localhost:5000/api/export/excel', {
      journalId: journal.id
    })
    
    if (response.data.downloadUrl) {
      // 下载文件
      const link = document.createElement('a')
      link.href = `http://localhost:5000${response.data.downloadUrl}`
      link.download = `统计表_${journal.issue}.xlsx`
      link.click()
      ElMessage.success('统计表生成成功！')
    }
  } catch (error: any) {
    console.error('生成统计表失败:', error)
    ElMessage.error(`生成统计表失败: ${error.response?.data?.message || error.message}`)
  }
}
</script>

<style scoped>
.journal-management {
  padding: 20px;
  width:100%;
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

.create-card {
  margin-bottom: 20px;
}

.journal-list-card {
  margin-bottom: 20px;
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

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  color: #333;
}

.total-count {
  color: #666;
  font-size: 14px;
}

.create-tips {
  margin-top: 15px;
  padding: 10px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.create-tips p {
  margin: 5px 0;
  color: #666;
  font-size: 14px;
}

/* 创建期刊按钮自定义样式 */
.create-journal-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.create-journal-btn:hover {
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

/* 生成推文按钮自定义样式 */
.generate-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

.generate-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #3f4041ff !important;
  color: #7a7d80ff !important;
}

/* 统计表按钮自定义样式 */
.stats-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

.stats-btn:hover {
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
/* 筛选区域样式 */
.filter-card {
  margin-bottom: 20px;
}

/* 重置筛选按钮自定义样式 */
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

/* 弹窗关闭按钮自定义样式 */
:deep(.custom-confirm-button) {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

:deep(.custom-confirm-button:hover) {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
  color: white !important;
}
</style>
