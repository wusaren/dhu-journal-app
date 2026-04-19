<template>
  <el-config-provider :locale="zhCn">
    <div class="operator-view">
      <!-- 页面标题 -->
      <div class="page-header">
        <h2>业务员工作台</h2>
        <p class="subtitle">批量检测论文目录，一键生成批注文档和检测报告</p>
      </div>

      <!-- 目录选择和配置区域 -->
      <el-card class="config-card">
        <el-row :gutter="20">
          <!-- 左侧：目录选择 -->
          <el-col :span="12">
            <div class="config-section">
              <h4><el-icon><FolderOpened /></el-icon> 论文目录</h4>
              <div class="directory-input-row">
                <el-input
                  v-model="directoryPath"
                  placeholder="请输入论文目录路径，如：D:\论文批次\2024届"
                  clearable
                  @keyup.enter="handleScanDirectory"
                  style="flex: 1;"
                >
                  <template #append>
                    <el-button @click="handleScanDirectory" :loading="scanning">扫描</el-button>
                  </template>
                </el-input>
              </div>
              <div class="folder-picker-row">
                <el-button type="primary" plain :loading="uploading" @click="handleUploadFolder">
                  <el-icon><FolderAdd /></el-icon>
                  上传论文文件夹
                </el-button>
                <span class="folder-hint">支持选择文件夹或拖拽文件到此处（文件格式：学号_学生_论文.docx）</span>
              </div>
              <input
                ref="folderInput"
                type="file"
                webkitdirectory
                multiple
                style="display: none;"
                @change="handleFolderFilesSelected"
              />

              <!-- 上传文件列表 -->
              <div v-if="uploadedFiles.length > 0" class="scan-result">
                <el-alert
                  :title="`已上传 ${uploadedFiles.length} 篇论文`"
                  type="success"
                  :closable="false"
                  show-icon
                />
                <div class="file-list">
                  <div
                    v-for="(file, index) in uploadedFiles.slice(0, 10)"
                    :key="index"
                    class="file-item"
                  >
                    <span class="file-name">{{ file.filename }}</span>
                    <span class="file-info">{{ file.student_id }} - {{ file.student_name }}</span>
                  </div>
                  <div v-if="uploadedFiles.length > 10" class="file-more">
                    还有 {{ uploadedFiles.length - 10 }} 篇论文...
                  </div>
                </div>
              </div>

              <!-- 扫描结果 -->
              <div v-else-if="scannedFiles.length > 0" class="scan-result">
                <el-alert
                  :title="`共扫描到 ${scannedFiles.length} 篇符合格式的论文`"
                  type="success"
                  :closable="false"
                  show-icon
                />
                <div class="file-list">
                  <div
                    v-for="(file, index) in scannedFiles.slice(0, 5)"
                    :key="index"
                    class="file-item"
                  >
                    <span class="file-name">{{ file.filename }}</span>
                    <span class="file-info">{{ file.student_id }} - {{ file.student_name }}</span>
                  </div>
                  <div v-if="scannedFiles.length > 5" class="file-more">
                    还有 {{ scannedFiles.length - 5 }} 篇论文...
                  </div>
                </div>
              </div>

              <div v-else-if="scanMessage && !scanning" class="scan-message">
                <el-alert :title="scanMessage" type="info" :closable="false" show-icon />
              </div>
            </div>
          </el-col>

          <!-- 右侧：检测配置 -->
          <el-col :span="12">
            <div class="config-section">
              <h4><el-icon><Setting /></el-icon> 检测配置</h4>

              <!-- 检测模块选择 -->
              <div class="module-selection">
                <el-checkbox
                  v-model="selectAllModules"
                  @change="handleSelectAllModules"
                  :indeterminate="isIndeterminate"
                >
                  全选
                </el-checkbox>
                <el-divider />
                <el-checkbox-group v-model="selectedModules">
                  <el-checkbox
                    v-for="module in availableModules"
                    :key="module.value"
                    :value="module.value"
                    :label="module.value"
                  >
                    {{ module.label }}
                  </el-checkbox>
                </el-checkbox-group>
              </div>

              <!-- 自动审核阈值设置 -->
              <div class="threshold-setting">
                <h5><el-icon><Warning /></el-icon> 自动审核设置</h5>
                <div class="threshold-row">
                  <span>通过率 ≥</span>
                  <el-input-number
                    v-model="passThreshold"
                    :min="0"
                    :max="100"
                    :step="5"
                    controls-position="right"
                    style="width: 100px;"
                  />
                  <span>% → 自动通过</span>
                </div>
                <div class="threshold-hint">
                  通过率低于该阈值的论文将标记为"需修改"
                </div>
              </div>
            </div>
          </el-col>
        </el-row>

        <!-- 操作按钮 -->
        <div class="action-buttons">
          <el-button
            type="primary"
            size="large"
            :disabled="!canStartCheck"
            :loading="isChecking"
            @click="handleStartBatchCheck"
          >
            <el-icon><VideoPlay /></el-icon>
            开始批量检测
          </el-button>
          <el-button
            size="large"
            :disabled="!currentBatchId"
            @click="handleExportExcel"
          >
            <el-icon><Download /></el-icon>
            导出Excel汇总表
          </el-button>
          <el-button size="large" @click="handleLoadHistory">
            <el-icon><Refresh /></el-icon>
            刷新历史任务
          </el-button>
        </div>
      </el-card>

      <!-- 批量任务进度 -->
      <el-card v-if="currentBatchId && isChecking" class="progress-card">
        <template #header>
          <div class="card-header">
            <span>批量检测进度</span>
            <el-tag type="primary">任务 #{{ currentBatchId }}</el-tag>
          </div>
        </template>
        <div class="progress-content">
          <el-progress
            :percentage="progressPercent"
            :status="progressStatus"
            :stroke-width="20"
          />
          <div class="progress-info">
            <span>已处理: {{ progressData.processed }} / {{ progressData.total_papers }} 篇</span>
            <span>通过: {{ progressData.passed }} 篇</span>
            <span>失败: {{ progressData.failed }} 篇</span>
          </div>
          <div v-if="progressData.current_paper" class="current-paper">
            当前处理: {{ progressData.current_paper }}
          </div>
        </div>
        <div class="progress-actions">
          <el-button type="danger" @click="handleCancelBatch">
            取消任务
          </el-button>
        </div>
      </el-card>

      <!-- 历史批次任务列表 -->
      <el-card class="history-card">
        <template #header>
          <div class="card-header">
            <span>历史批次任务</span>
          </div>
        </template>

        <el-table :data="batchJobs" style="width: 100%" stripe>
          <el-table-column prop="id" label="批次ID" width="80" align="center" />
          <el-table-column prop="directory_path" label="源目录" min-width="200" />
          <el-table-column prop="total_papers" label="总数" width="80" align="center" />
          <el-table-column prop="processed" label="已处理" width="80" align="center">
            <template #default="scope">
              <span :style="{ color: scope.row.processed === scope.row.total_papers ? '#67c23a' : '#409eff' }">
                {{ scope.row.processed }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100" align="center">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">
                {{ getStatusText(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="pass_threshold" label="阈值" width="80" align="center" />
          <el-table-column prop="created_at" label="创建时间" width="160">
            <template #default="scope">
              {{ formatDateTime(scope.row.created_at) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" align="center">
            <template #default="scope">
              <el-button size="small" @click="handleViewBatchDetail(scope.row)">
                查看详情
              </el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="scope.row.status !== 'completed'"
                @click="handleExportBatchExcel(scope.row.id)"
              >
                导出
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <!-- 批次详情对话框 -->
      <el-dialog
        v-model="showBatchDetail"
        title="批次详情"
        width="90%"
        :fullscreen="false"
      >
        <div v-if="currentBatch" class="batch-detail">
          <!-- 批次汇总信息 -->
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="批次ID">{{ currentBatch.id }}</el-descriptions-item>
            <el-descriptions-item label="源目录">{{ currentBatch.directory_path }}</el-descriptions-item>
            <el-descriptions-item label="输出目录">{{ currentBatch.output_path }}</el-descriptions-item>
            <el-descriptions-item label="总论文数">{{ currentBatch.total_papers }}</el-descriptions-item>
            <el-descriptions-item label="已处理">{{ currentBatch.processed }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="getStatusType(currentBatch.status)">
                {{ getStatusText(currentBatch.status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="开始时间">
              {{ formatDateTime(currentBatch.started_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="完成时间">
              {{ formatDateTime(currentBatch.completed_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="自动通过阈值">{{ currentBatch.pass_threshold }}%</el-descriptions-item>
          </el-descriptions>

          <!-- 论文列表 -->
          <h4 style="margin-top: 20px;">论文审核情况</h4>
          <el-table :data="currentBatch.papers" style="width: 100%" stripe max-height="400">
            <el-table-column prop="student_id" label="学号" width="100" align="center" />
            <el-table-column prop="student_name" label="姓名" width="100" align="center" />
            <el-table-column prop="original_filename" label="文件名" min-width="200" />
            <el-table-column label="检测状态" width="100" align="center">
              <template #default="scope">
                <el-tag :type="getCheckStatusType(scope.row.check_status)" size="small">
                  {{ getCheckStatusText(scope.row.check_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="审核状态" width="100" align="center">
              <template #default="scope">
                <el-tag :type="getReviewStatusType(scope.row.review_status)" size="small">
                  {{ getReviewStatusText(scope.row.review_status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="通过率" width="100" align="center">
              <template #default="scope">
                <span v-if="scope.row.pass_rate !== null" :style="{ color: getPassRateColor(scope.row.pass_rate) }">
                  {{ scope.row.pass_rate.toFixed(1) }}%
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" align="center">
              <template #default="scope">
                <el-button
                  size="small"
                  :disabled="!scope.row.original_path"
                  @click="handleOpenOriginal(scope.row)"
                >
                  原文档
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  :disabled="!scope.row.report_path"
                  @click="handleOpenReport(scope.row)"
                >
                  报告
                </el-button>
                <el-button
                  size="small"
                  type="success"
                  :disabled="!scope.row.annotated_path"
                  @click="handleOpenAnnotated(scope.row)"
                >
                  批注
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <template #footer>
          <el-button @click="showBatchDetail = false">关闭</el-button>
          <el-button
            type="primary"
            :disabled="!currentBatch"
            @click="handleExportCurrentBatch"
          >
            导出Excel
          </el-button>
        </template>
      </el-dialog>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FolderOpened, Setting, Warning, VideoPlay, Download, Refresh, FolderAdd } from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { operatorService, type FileInfo, type BatchJob, type BatchJobDetail } from '@/api/operatorService'

// 目录和扫描
const directoryPath = ref('')
const scannedFiles = ref<FileInfo[]>([])
const scanning = ref(false)
const uploading = ref(false)
const scanMessage = ref('')
const folderInput = ref<HTMLInputElement | null>(null)

// 上传的文件状态
const uploadedFiles = ref<FileInfo[]>([])
const uploadedTempDir = ref('')

// 检测配置
const availableModules = [
  { value: 'Title', label: '标题' },
  { value: 'Abstract', label: '摘要' },
  { value: 'English_Abstract', label: '英文摘要' },
  { value: 'Keywords', label: '关键词' },
  { value: 'Content', label: '正文' },
  { value: 'Formula', label: '公式' },
  { value: 'TOC', label: '目录/图录/表录' },
  { value: 'Figure', label: '图片' },
  { value: 'Table', label: '表格' },
  { value: 'References', label: '参考文献' },
]
const selectedModules = ref<string[]>(availableModules.map(m => m.value))
const selectAllModules = ref(true)
const passThreshold = ref(85)

// 批量检测状态
const currentBatchId = ref<number | null>(null)
const isChecking = ref(false)
const progressData = ref({
  total_papers: 0,
  processed: 0,
  passed: 0,
  failed: 0,
  current_paper: null as string | null
})
let progressInterval: number | null = null

// 历史任务
const batchJobs = ref<BatchJob[]>([])

// 批次详情
const showBatchDetail = ref(false)
const currentBatch = ref<BatchJobDetail | null>(null)

// 计算属性
const canStartCheck = computed(() => {
  // 支持两种方式：1. 扫描目录后的文件 2. 上传文件夹的文件
  const hasFiles = scannedFiles.value.length > 0 || uploadedFiles.value.length > 0
  return hasFiles && selectedModules.value.length > 0 && !isChecking.value
})

const isIndeterminate = computed(() => {
  return selectedModules.value.length > 0 && selectedModules.value.length < availableModules.length
})

const progressPercent = computed(() => {
  if (progressData.value.total_papers === 0) return 0
  return Math.round((progressData.value.processed / progressData.value.total_papers) * 100)
})

const progressStatus = computed(() => {
  if (progressData.value.processed === progressData.value.total_papers) {
    return 'success'
  }
  return undefined
})

// 方法
const handleSelectAllModules = (checked: boolean) => {
  if (checked) {
    selectedModules.value = availableModules.map(m => m.value)
  } else {
    selectedModules.value = []
  }
}

// 点击选择文件夹按钮 - 触发文件选择
const handleSelectFolder = () => {
  if (folderInput.value) {
    folderInput.value.click()
  }
}

// 处理选择的文件夹文件
const handleFolderFilesSelected = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const files = target.files

  if (files && files.length > 0) {
    uploading.value = true

    try {
      const response = await operatorService.uploadFolder(files)

      if (response.success && response.data) {
        uploadedFiles.value = response.data.files || []
        uploadedTempDir.value = response.data.temp_dir || ''

        if (uploadedFiles.value.length > 0) {
          ElMessage.success(`成功上传 ${uploadedFiles.value.length} 篇论文，请点击"开始批量检测"`)
        } else {
          ElMessage.info('未找到符合格式的论文文件（格式：学号_学生_论文.docx）')
        }
      } else {
        ElMessage.error(response.message || '上传失败')
      }
    } catch (error: any) {
      ElMessage.error(error.message || '上传失败')
    } finally {
      uploading.value = false
    }
  }

  // 清空input，允许重新选择同一文件夹
  target.value = ''
}

// 别名：上传文件夹
const handleUploadFolder = handleSelectFolder

const handleScanDirectory = async () => {
  if (!directoryPath.value.trim()) {
    ElMessage.warning('请输入目录路径')
    return
  }

  scanning.value = true
  scanMessage.value = ''
  scannedFiles.value = []

  try {
    const response = await operatorService.scanDirectory(directoryPath.value)
    if (response.success && response.data) {
      scannedFiles.value = response.data.files || []
      scanMessage.value = response.data.message || ''
      if (scannedFiles.value.length === 0) {
        ElMessage.info('未找到符合格式的论文文件（格式：学号_学生_论文.docx）')
      } else {
        ElMessage.success(scanMessage.value)
      }
    } else {
      scanMessage.value = response.message || '扫描失败'
      ElMessage.error(scanMessage.value)
    }
  } catch (error: any) {
    scanMessage.value = error.message || '扫描目录失败'
    ElMessage.error(scanMessage.value)
  } finally {
    scanning.value = false
  }
}

const handleStartBatchCheck = async () => {
  try {
    let response

    // 根据是否有上传的文件决定调用哪个接口
    if (uploadedFiles.value.length > 0) {
      // 从上传的文件启动检测
      response = await operatorService.startBatchCheckFromUpload(
        uploadedFiles.value,
        uploadedTempDir.value,
        passThreshold.value,
        selectedModules.value
      )
    } else if (scannedFiles.value.length > 0 && directoryPath.value) {
      // 从扫描的目录启动检测
      response = await operatorService.startBatchCheck(
        directoryPath.value,
        passThreshold.value,
        selectedModules.value
      )
    } else {
      ElMessage.warning('请先上传论文文件夹或扫描目录')
      return
    }

    if (response.success && response.data) {
      currentBatchId.value = response.data.batch_id
      isChecking.value = true
      progressData.value = {
        total_papers: response.data.total_papers,
        processed: 0,
        passed: 0,
        failed: 0,
        current_paper: null
      }

      ElMessage.success(response.data.message || '批量检测任务已启动')
      startProgressPolling()
    } else if (response.success && !response.data) {
      // 直接返回 success: true 的情况（如 start-from-upload）
      currentBatchId.value = response.batch_id
      isChecking.value = true
      progressData.value = {
        total_papers: response.total_papers,
        processed: 0,
        passed: 0,
        failed: 0,
        current_paper: null
      }

      ElMessage.success(response.message || '批量检测任务已启动')
      startProgressPolling()
    } else {
      ElMessage.error(response.message || '启动批量检测失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '启动批量检测失败')
  }
}

const startProgressPolling = () => {
  if (progressInterval) {
    clearInterval(progressInterval)
  }

  progressInterval = window.setInterval(async () => {
    if (!currentBatchId.value) {
      stopProgressPolling()
      return
    }

    try {
      const response = await operatorService.getBatchProgress(currentBatchId.value)
      if (response.success && response.progress) {
        progressData.value = {
          total_papers: response.progress.total_papers,
          processed: response.progress.processed,
          passed: response.progress.passed,
          failed: response.progress.failed,
          current_paper: response.progress.current_paper
        }

        if (response.progress.status === 'completed' || response.progress.status === 'failed' || response.progress.status === 'cancelled') {
          stopProgressPolling()
          isChecking.value = false
          ElMessage.info(`批量检测任务已${response.progress.status === 'completed' ? '完成' : response.progress.status === 'cancelled' ? '取消' : '失败'}`)
          // 检测完成后清除上传状态，允许重新上传
          uploadedFiles.value = []
          uploadedTempDir.value = ''
          handleLoadHistory()
        }
      }
    } catch (error) {
      console.error('获取进度失败:', error)
    }
  }, 2000)
}

const stopProgressPolling = () => {
  if (progressInterval) {
    clearInterval(progressInterval)
    progressInterval = null
  }
}

const handleCancelBatch = async () => {
  if (!currentBatchId.value) return

  try {
    await ElMessageBox.confirm('确定要取消当前批量检测任务吗？', '取消任务', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const response = await operatorService.cancelBatchJob(currentBatchId.value)
    if (response.success) {
      ElMessage.success('任务已取消')
      stopProgressPolling()
      isChecking.value = false
      handleLoadHistory()
    } else {
      ElMessage.error(response.message || '取消失败')
    }
  } catch {
    // 用户取消
  }
}

const handleLoadHistory = async () => {
  try {
    const response = await operatorService.getBatchJobs(20)
    if (response.success && response.data) {
      batchJobs.value = response.data.jobs || []
    }
  } catch (error: any) {
    ElMessage.error(error.message || '加载历史任务失败')
  }
}

const handleViewBatchDetail = async (job: BatchJob) => {
  try {
    const response = await operatorService.getBatchJobDetail(job.id)
    if (response.success && response.data) {
      currentBatch.value = response.data.job
      showBatchDetail.value = true
    } else {
      ElMessage.error(response.message || '获取批次详情失败')
    }
  } catch (error: any) {
    ElMessage.error(error.message || '获取批次详情失败')
  }
}

const handleExportExcel = () => {
  if (!currentBatchId.value) {
    ElMessage.warning('请先选择一个批次任务')
    return
  }

  const url = operatorService.getExcelDownloadUrl(currentBatchId.value)
  window.open(url, '_blank')
}

const handleExportBatchExcel = (batchId: number) => {
  const url = operatorService.getExcelDownloadUrl(batchId)
  window.open(url, '_blank')
}

const handleExportCurrentBatch = () => {
  if (currentBatch.value) {
    handleExportBatchExcel(currentBatch.value.id)
  }
}

const handleOpenOriginal = (paper: any) => {
  window.open(`/api/operator/batch/papers/${paper.id}/open-original`, '_blank')
}

const handleOpenReport = (paper: any) => {
  window.open(`/api/operator/batch/papers/${paper.id}/open-report`, '_blank')
}

const handleOpenAnnotated = (paper: any) => {
  window.open(`/api/operator/batch/papers/${paper.id}/open-annotated`, '_blank')
}

// 工具方法
const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'warning'
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    running: '检测中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return map[status] || status
}

const getCheckStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    completed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

const getCheckStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待检测',
    completed: '已完成',
    failed: '失败'
  }
  return map[status] || status
}

const getReviewStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    reviewed: 'success',
    needs_revision: 'warning'
  }
  return map[status] || 'info'
}

const getReviewStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待审核',
    reviewed: '已通过',
    needs_revision: '需修改'
  }
  return map[status] || status
}

const getPassRateColor = (rate: number) => {
  if (rate >= 85) return '#67c23a'
  if (rate >= 60) return '#e6a23c'
  return '#f56c6c'
}

const formatDateTime = (dateStr: string | null) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}

// 生命周期
onMounted(() => {
  handleLoadHistory()
})

onUnmounted(() => {
  stopProgressPolling()
})
</script>

<style scoped>
.operator-view {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 8px 0;
  color: #333;
}

.subtitle {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.config-card {
  margin-bottom: 20px;
}

.config-section {
  padding: 10px;
}

.config-section h4 {
  margin: 0 0 15px 0;
  color: #333;
  display: flex;
  align-items: center;
  gap: 8px;
}

.directory-input-row {
  margin-bottom: 10px;
}

.folder-picker-row {
  display: flex;
  align-items: center;
  gap: 15px;
}

.folder-hint {
  color: #909399;
  font-size: 12px;
}

.scan-result {
  margin-top: 15px;
}

.file-list {
  margin-top: 10px;
  max-height: 150px;
  overflow-y: auto;
}

.file-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 10px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 4px;
  font-size: 13px;
}

.file-name {
  color: #333;
  font-weight: 500;
}

.file-info {
  color: #909399;
}

.file-more {
  text-align: center;
  color: #909399;
  font-size: 13px;
  padding: 8px;
}

.scan-message {
  margin-top: 15px;
}

.module-selection {
  margin-bottom: 20px;
}

.module-selection .el-checkbox-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}

.threshold-setting {
  background: #fdf6ec;
  padding: 15px;
  border-radius: 4px;
}

.threshold-setting h5 {
  margin: 0 0 10px 0;
  color: #e6a23c;
  display: flex;
  align-items: center;
  gap: 8px;
}

.threshold-row {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #666;
}

.threshold-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.action-buttons {
  margin-top: 20px;
  display: flex;
  justify-content: center;
  gap: 15px;
}

.action-buttons .el-button--primary {
  background-color: #9c0e0e !important;
  border-color: #9c0e0e !important;
}

.action-buttons .el-button--primary:hover {
  background-color: #7a0b0b !important;
  border-color: #7a0b0b !important;
}

.progress-card {
  margin-bottom: 20px;
}

.progress-content {
  padding: 10px 0;
}

.progress-info {
  display: flex;
  justify-content: space-around;
  margin-top: 15px;
  color: #666;
  font-size: 14px;
}

.current-paper {
  text-align: center;
  margin-top: 10px;
  color: #409eff;
  font-size: 13px;
}

.progress-actions {
  margin-top: 15px;
  text-align: center;
}

.history-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-detail {
  padding: 10px;
}
</style>
