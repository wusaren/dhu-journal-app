<template>
  <div class="preliminary-review">
    

    <el-card class="filter-card">
      <el-form :model="filterForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-form-item label="论文状态">
              <el-select v-model="filterForm.status" placeholder="请选择状态" clearable>
                <el-option label="待审核" value="pending" />
                <el-option label="已审核" value="reviewed" />
                <el-option label="需修改" value="need_revision" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="提交日期">
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
              <el-input v-model="filterForm.keyword" placeholder="输入关键词" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item>
              <el-button class="search-btn" type="primary" @click="handleSearch">搜索</el-button>
              <el-button @click="resetFilter">重置</el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </el-card>

    <el-card class="review-list-card">
      <template #header>
        <div class="card-header">
          <h3>待审核论文列表</h3>
          <span class="total-count">共 {{ reviewList.length }} 篇论文</span>
        </div>
      </template>

      <el-table :data="reviewList" style="width: 100%">
        <el-table-column prop="title" label="论文标题" width="300" />
        <el-table-column prop="author" label="作者" width="120" />
        <el-table-column prop="submitDate" label="提交日期" width="120" />
        <el-table-column prop="reviewer" label="审核人" width="120" />
        <el-table-column label="审核状态" width="100">
          <template #default="scope">
            <el-tag :type="getReviewStatusType(scope.row.reviewStatus)">
              {{ scope.row.reviewStatus }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="scope">
            <el-button class="audit-btn"size="small" type="primary" @click="handleReview(scope.row)">
              审核
            </el-button>
            <el-button class="view-btn"size="small" @click="handleView(scope.row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

interface ReviewPaper {
  id: number
  title: string
  author: string
  submitDate: string
  reviewer: string
  reviewStatus: string
}

interface FilterForm {
  status: string
  dateRange: string[]
  keyword: string
}

const filterForm = ref<FilterForm>({
  status: '',
  dateRange: [],
  keyword: ''
})

const reviewList = ref<ReviewPaper[]>([
  {
    id: 1,
    title: '基于深度学习的图像识别技术研究',
    author: '张三',
    submitDate: '2024-01-15',
    reviewer: '李老师',
    reviewStatus: '待审核'
  },
  {
    id: 2,
    title: '人工智能在医疗诊断中的应用',
    author: '李四',
    submitDate: '2024-01-12',
    reviewer: '王老师',
    reviewStatus: '审核中'
  },
  {
    id: 3,
    title: '区块链技术在供应链管理中的研究',
    author: '王五',
    submitDate: '2024-01-10',
    reviewer: '张老师',
    reviewStatus: '已审核'
  },
  {
    id: 4,
    title: '大数据分析在商业决策中的应用',
    author: '赵六',
    submitDate: '2024-01-08',
    reviewer: '陈老师',
    reviewStatus: '需修改'
  }
])

const getReviewStatusType = (status: string) => {
  const statusMap: Record<string, string> = {
    '待审核': 'warning',
    '审核中': 'primary',
    '已审核': 'success',
    '需修改': 'danger'
  }
  return statusMap[status] || 'info'
}

const handleSearch = () => {
  ElMessage.info('搜索功能待实现')
}

const resetFilter = () => {
  filterForm.value = {
    status: '',
    dateRange: [],
    keyword: ''
  }
}

const handleReview = (paper: ReviewPaper) => {
  ElMessage.info(`开始审核论文：${paper.title}`)
}

const handleView = (paper: ReviewPaper) => {
  ElMessage.info(`查看论文详情：${paper.title}`)
}
</script>

<style scoped>
.preliminary-review {
  padding: 20px;
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
/* 审核按钮自定义样式 */
.audit-btn {
  background-color: #ffffffff !important;
  border-color: #d9d9d9ff !important;
  color: #333 !important;
}

.audit-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #3f4041ff !important;
  color: #7a7d80ff !important;
}
/* 查看按钮自定义样式 */
.view-btn {
  background-color: #ffffffff !important;
  border-color: #d9d9d9ff !important;
  color: #333 !important;
}

.view-btn:hover {
  background-color: #e6f7ff !important;
  border-color: #3f4041ff !important;
  color: #7a7d80ff !important;
}
</style>
