<template>
  <div class="journal-management">
    

    

    <!-- 期刊列表 -->
    <el-card class="journal-list-card">
      <template #header>
        <div class="card-header">
          <h3>期刊列表</h3>
          <span class="total-count">共 {{ journalList.length }} 个期刊</span>
        </div>
      </template>

      <el-table :data="journalList" style="width: 100%">
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
          </template>
        </el-table-column>
      </el-table>
    </el-card>
    <!-- 上传区域 -->
    <el-card class="upload-card">
      <template #header>
        <div class="card-header">
          <h3>上传期刊文件</h3>
        </div>
      </template>

      <el-upload
        class="upload-demo"
        action="#"
        :auto-upload="false"
        :on-change="handleFileChange"
        :show-file-list="false"
      >
        <template #trigger>
          <el-button class="select-journal-btn" type="primary" size="mid">选择期刊文件</el-button>
        </template>
        <el-button 
          style="margin-left: 10px;" 
          :disabled="!selectedFile"
          :loading="uploadLoading"
          @click="handleParse"
          class="analysis-journal-btn"
          type="success" 
          size="mid"
        >
          添加到期刊
        </el-button>
      </el-upload>

      <div v-if="selectedFile" class="file-info">
        <p>已选择文件: {{ selectedFile.name }}</p>
        <p>文件大小: {{ formatFileSize(selectedFile.size) }}</p>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadFiles } from 'element-plus'
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

const selectedFile = ref<File | null>(null)
const journalList = ref<Journal[]>([])
const loading = ref(false)
const uploadLoading = ref(false)

// 获取认证token
const getAuthHeaders = () => {
  const token = localStorage.getItem('token')
  return {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
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
      console.log('使用数据库数据，期刊数量:', response.data.length)
    } else {
      // 数据库中没有数据，显示空列表
      journalList.value = []
      console.log('数据库为空，显示空列表')
    }
    
    ElMessage.success('期刊列表加载成功')
  } catch (error: any) {
    console.error('加载期刊列表失败:', error)
    console.error('错误详情:', error.response?.data)
    
    if (error.code === 'ERR_NETWORK' || error.message.includes('ERR_CONNECTION_REFUSED')) {
      ElMessage.error('无法连接到后端服务，请确保后端服务已启动')
      journalList.value = []
    } else {
      ElMessage.error(`加载期刊列表失败: ${error.response?.data?.message || error.message}`)
      journalList.value = []
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  // 直接加载期刊列表，不需要认证
  loadJournals()
})

const handleFileChange = (file: UploadFile, fileList: UploadFiles) => {
  selectedFile.value = file.raw as File
}

const handleParse = async () => {
  if (!selectedFile.value) {
    ElMessage.error('请先选择文件')
    return
  }

  uploadLoading.value = true
  
  try {
    console.log('开始上传文件:', selectedFile.value.name)
    
    // 创建FormData
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('journalId', '1') // 默认关联到期刊ID 1
    
    console.log('准备上传文件...')
    
    // 上传文件（不需要认证）
    const uploadResponse = await axios.post('http://localhost:5000/api/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })

    console.log('文件上传响应:', uploadResponse.data)

    console.log('上传响应:', uploadResponse.data)
    
    if (uploadResponse.data.fileId || uploadResponse.data.message === '文件上传成功') {
      ElMessage.success('文件上传成功！')
      
      // 重新从数据库加载期刊列表
      await loadJournals()
      
      ElMessage.success('文件已添加到期刊列表！')
    } else {
      ElMessage.error('文件上传失败：未收到有效响应')
    }
  } catch (error: any) {
    console.error('文件上传失败:', error)
    console.error('错误详情:', error.response?.data)
    
    if (error.code === 'ERR_NETWORK' || error.message.includes('ERR_CONNECTION_REFUSED')) {
      ElMessage.error('无法连接到后端服务，请确保后端服务已启动 (http://localhost:5000)')
    } else if (error.response?.status === 500) {
      ElMessage.error(`服务器内部错误: ${error.response?.data?.message || '请检查后端日志'}`)
    } else {
      ElMessage.error(`文件上传失败: ${error.response?.data?.message || error.message}`)
    }
  } finally {
    uploadLoading.value = false
  }
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
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

const handleEdit = (journal: Journal) => {
  ElMessage.info('编辑功能暂未实现，敬请期待！')
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

.upload-card {
  margin-bottom: 20px;
}

.journal-list-card {
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

.file-info {
  margin-top: 15px;
  padding: 10px;
  background-color: #f8f9fa;
  border-radius: 4px;
}

.file-info p {
  margin: 5px 0;
  color: #666;
  font-size: 14px;
}

.upload-demo {
  display: flex;
  align-items: center;
}
/* 选择期刊按钮自定义样式 */
.select-journal-btn {
  background-color: #b62020ff !important;
  border-color: #be2121ff !important;
  color: white !important;
}

.select-journal-btn:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}
.analysis-journal-btn {
  background-color: #fa8c16 !important;
  border-color: #fa8c16 !important;
  color: white !important;
}
.analysis-journal-btn:hover {
  background-color: #fa8c20 !important;
  border-color: #fa8c20!important;
  color: white !important;
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
</style>
