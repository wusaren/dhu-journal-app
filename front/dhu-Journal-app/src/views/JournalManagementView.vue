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
        <el-table-column label="操作" width="500">
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
            <el-button 
              class="template-btn"
              size="small"
              @click="handleTemplateConfig(scope.row)"
            >
              模板配置
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

    <!-- 模板配置对话框 -->
    <TemplateConfigDialog
      v-model="showTemplateConfig"
      :journal-id="currentJournalForTemplate?.id"
      @saved="handleTemplateSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useJournalStore } from '@/stores/journalStore'
import type { Journal } from '@/api/journalService'
import { journalService } from '@/api/journalService'
import TemplateConfigDialog from '@/components/TemplateConfigDialog.vue'

const router = useRouter()
const journalStore = useJournalStore()

// 使用store中的状态和计算属性
const filterForm = computed(() => journalStore.filterForm)
const selectedJournals = computed(() => journalStore.selectedJournals)
const loading = computed(() => journalStore.loading)
const currentPage = computed({
  get: () => journalStore.currentPage,
  set: (value) => journalStore.setCurrentPage(value)
})
const pageSize = computed({
  get: () => journalStore.pageSize,
  set: (value) => journalStore.setPageSize(value)
})
const pagedJournalList = computed(() => journalStore.pagedJournalList)
const totalJournals = computed(() => journalStore.totalJournals)
const journalList = computed(() => journalStore.journalList)
const filteredJournalList = computed(() => journalStore.filteredJournalList)

// 处理筛选
const handleFilter = () => {
  ElMessage.info('筛选完成')
}

// 重置筛选
const resetFilter = () => {
  journalStore.resetFilter()
  ElMessage.info('筛选已重置')
}

// 处理选择变化
const handleSelectionChange = (selection: Journal[]) => {
  journalStore.setSelectedJournals(selection)
}

// 处理每页数量变化
const handleSizeChange = (size: number) => {
  journalStore.setPageSize(size)
}

// 处理当前页变化
const handleCurrentChange = (page: number) => {
  journalStore.setCurrentPage(page)
}

// 批量删除期刊
const handleBatchDelete = async () => {
  if (selectedJournals.value.length === 0) {
    ElMessage.warning('请先选择要删除的期刊')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedJournals.value.length} 个期刊吗？\n\n⚠️ 注意：如果期刊下还有论文，将无法删除该期刊。`, 
      '批量删除期刊', 
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await journalStore.batchDeleteJournals()
  } catch (error: any) {
    if (error === 'cancel' || error.message === 'cancel') {
      ElMessage.info('取消批量删除')
    } else {
      console.error('批量删除期刊失败:', error)
      ElMessage.error(error.message)
    }
  }
}

onMounted(() => {
  // 直接加载期刊列表，不需要认证
  journalStore.loadJournals()
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
    const papers = await journalStore.getPapers(journal.id)
    
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
    ElMessage.error(error.message)
  }
}

const handleViewTOC = async (journal: Journal) => {
  try {
    await journalStore.generateTOC(journal.id, journal.issue)
  } catch (error: any) {
    console.error('生成目录失败:', error)
    ElMessage.error(error.message)
  }
}

const handlePublish = (journal: Journal) => {
  const newStatus = journal.status === '已发布' ? '编辑中' : '已发布'
  ElMessage.success(`期刊 ${journal.issue} ${newStatus === '已发布' ? '已发布' : '已取消发布'}`)
}

const handleGenerateWeibo = async (journal: Journal) => {
  try {
    await journalStore.generateWeibo(journal.id, journal.issue)
  } catch (error: any) {
    console.error('生成推文失败:', error)
    ElMessage.error(error.message)
  }
}

// 模板配置相关状态
const showTemplateConfig = ref(false)
const currentJournalForTemplate = ref<Journal | null>(null)

const handleViewStats = async (journal: Journal) => {
  // 直接生成统计表，不打开配置对话框
  // 后端会自动判断：有模板配置就用模板，没有就用默认配置
  try {
    await journalStore.generateStats(journal.id, journal.issue)
  } catch (error: any) {
    console.error('生成统计表失败:', error)
    ElMessage.error(error.message)
  }
}

const handleTemplateConfig = (journal: Journal) => {
  currentJournalForTemplate.value = journal
  showTemplateConfig.value = true
}

const handleTemplateSaved = () => {
  ElMessage.success('模板配置已保存')
}

const handleDelete = async (journal: Journal) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除期刊"${journal.title} - ${journal.issue}"吗？\n\n⚠️ 注意：如果该期刊下还有论文，将无法删除期刊。`, 
      '删除期刊', 
      {
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await journalStore.deleteJournal(journal.id)
  } catch (error: any) {
    if (error === 'cancel' || error.message === 'cancel') {
      ElMessage.info('取消删除')
    } else {
      console.error('删除期刊失败:', error)
      ElMessage.error(error.message)
    }
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

/* 模板配置按钮自定义样式 */
.template-btn {
  background-color: #f5f5f5 !important;
  border-color: #d9d9d9 !important;
  color: #333 !important;
}

.template-btn:hover {
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
