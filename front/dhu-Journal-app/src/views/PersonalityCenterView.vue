<template>
  <div class="personality-center">

    <!-- 格式配置下拉框 -->
    <el-card class="config-card">
      <template #header>
        <div class="card-header">
          <h3>格式配置</h3>
        </div>
      </template>
      
      <div class="config-body">
        <el-form label-position="top">
          <el-form-item label="选择配置类型">
            <el-select 
              v-model="selectedConfigType" 
              placeholder="请选择配置类型"
              @change="handleConfigTypeChange"
              style="width: 100%"
            >
              <el-option label="统计表格式配置" value="stats" />
              <el-option label="推文格式配置" value="weibo" />
            </el-select>
          </el-form-item>
        </el-form>
      </div>
    </el-card>

    <!-- 格式操作栏 - 根据选择显示 -->
    <div v-if="showConfigPanel">
      <el-row :gutter="20">
        <!-- 统计表格式配置 -->
        <el-col :span="12" v-if="selectedConfigType === 'stats'">
          <el-card class="upload-card">
            <template #header>
              <div class="card-header">
                <h3>统计表格式配置</h3>
                <span class="total-count">上传并确认格式</span>
              </div>
            </template>

            <div class="upload-body">
              <p class="hint">支持格式：.xlsx .xls .csv。请确保第一行为表头，包含作者、标题、页码等字段。</p>

              <div class="file-row">
                <input ref="statsFileInput" type="file" accept=".xlsx,.xls,.csv" @change="onStatsFileChange" hidden />
                <!-- 合并按钮：上传格式文件（红色主题） -->
                <el-button class="upload-btn" type="primary" size="mid" @click="triggerStatsFile" :loading="uploadingStats">上传格式文件</el-button>
                <span class="file-name" v-if="statsFileName">{{ statsFileName }}</span>
                <span class="file-empty" v-else>尚未选择文件</span>
              </div>

              <div class="actions">
                <!-- 保留确认格式按钮 -->
                <el-button :disabled="!statsFile" size="small" @click="checkStatsFormat">确认格式</el-button>
              </div>

              <div class="result" v-if="statsResult">
                <p :class="{'ok': statsResult.ok, 'warn': !statsResult.ok}">{{ statsResult.message }}</p>
                <ul v-if="statsResult.errors && statsResult.errors.length">
                  <li v-for="(e, idx) in statsResult.errors" :key="idx">{{ e }}</li>
                </ul>
              </div>
            </div>
          </el-card>
        </el-col>

        <!-- 推文格式配置 -->
        <el-col :span="12" v-if="selectedConfigType === 'weibo'">
          <el-card class="upload-card">
            <template #header>
              <div class="card-header">
                <h3>推文格式配置</h3>
                <span class="total-count">上传并确认格式</span>
              </div>
            </template>

            <div class="upload-body">
              <p class="hint">支持格式：.txt .docx .doc。请确保包含推文正文与可选的摘要信息。</p>

              <div class="file-row">
                <input ref="weiboFileInput" type="file" accept=".txt,.md" @change="onWeiboFileChange" hidden />
                <!-- 合并按钮：上传格式文件（红色主题） -->
                <el-button class="upload-btn" type="primary" size="mid" @click="triggerWeiboFile" :loading="uploadingWeibo">上传格式文件</el-button>
                <span class="file-name" v-if="weiboFileName">{{ weiboFileName }}</span>
                <span class="file-empty" v-else>尚未选择文件</span>
              </div>

              <div class="actions">
                <!-- 保留确认格式按钮 -->
                <el-button :disabled="!weiboFile" size="small" @click="checkWeiboFormat">确认格式</el-button>
              </div>

              <div class="result" v-if="weiboResult">
                <p :class="{'ok': weiboResult.ok, 'warn': !weiboResult.ok}">{{ weiboResult.message }}</p>
                <ul v-if="weiboResult.errors && weiboResult.errors.length">
                  <li v-for="(e, idx) in weiboResult.errors" :key="idx">{{ e }}</li>
                </ul>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import apiClient from '@/api/axios'

// 配置类型状态
const selectedConfigType = ref<string>('')
const showConfigPanel = computed(() => selectedConfigType.value !== '')

// 文件与状态
const statsFile = ref<File | null>(null)
const weiboFile = ref<File | null>(null)
const statsFileName = ref('')
const weiboFileName = ref('')

const uploadingStats = ref(false)
const uploadingWeibo = ref(false)

const statsResult = ref<{ ok: boolean; message: string; errors?: string[] } | null>(null)
const weiboResult = ref<{ ok: boolean; message: string; errors?: string[] } | null>(null)

const statsFileInput = ref<HTMLInputElement | null>(null)
const weiboFileInput = ref<HTMLInputElement | null>(null)

const triggerStatsFile = () => statsFileInput.value?.click()
const triggerWeiboFile = () => weiboFileInput.value?.click()

// 配置类型变更处理
const handleConfigTypeChange = (value: string) => {
  selectedConfigType.value = value
  // 重置文件状态
  if (value === 'stats') {
    weiboFile.value = null
    weiboFileName.value = ''
    weiboResult.value = null
  } else if (value === 'weibo') {
    statsFile.value = null
    statsFileName.value = ''
    statsResult.value = null
  }
}

// 选择文件后立即上传
const onStatsFileChange = async (e: Event) => {
  const t = e.target as HTMLInputElement
  const f = t.files?.[0] || null
  statsFile.value = f
  statsFileName.value = f ? f.name : ''
  statsResult.value = null
  if (f) {
    await uploadStats()
  }
}

const onWeiboFileChange = async (e: Event) => {
  const t = e.target as HTMLInputElement
  const f = t.files?.[0] || null
  weiboFile.value = f
  weiboFileName.value = f ? f.name : ''
  weiboResult.value = null
  if (f) {
    await uploadWeibo()
  }
}

// 上传函数（示例 API 路径，可根据后端调整）
const uploadStats = async () => {
  if (!statsFile.value) return
  uploadingStats.value = true
  try {
    const fd = new FormData()
    fd.append('file', statsFile.value)
    const resp = await apiClient.post('/api/upload/stats-format', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success(resp.data?.message || '上传成功')
  } catch (err: any) {
    console.error(err)
    ElMessage.error(err?.response?.data?.message || '上传失败')
  } finally {
    uploadingStats.value = false
  }
}

const uploadWeibo = async () => {
  if (!weiboFile.value) return
  uploadingWeibo.value = true
  try {
    const fd = new FormData()
    fd.append('file', weiboFile.value)
    const resp = await apiClient.post('/api/upload/weibo-format', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    ElMessage.success(resp.data?.message || '上传成功')
  } catch (err: any) {
    console.error(err)
    ElMessage.error(err?.response?.data?.message || '上传失败')
  } finally {
    uploadingWeibo.value = false
  }
}

// 简单的格式确认：调用后端校验接口，或做客户端预校验
const checkStatsFormat = async () => {
  if (!statsFile.value) return
  const ext = statsFile.value.name.split('.').pop()?.toLowerCase()
  const allowed = ['xlsx', 'xls', 'csv']
  if (!ext || !allowed.includes(ext)) {
    statsResult.value = { ok: false, message: '不支持的文件格式', errors: ['请上传 xlsx / xls / csv 文件'] }
    return
  }

  // 调用后端格式校验（若后端未实现，可只做客户端提示）
  try {
    const fd = new FormData()
    fd.append('file', statsFile.value)
    const resp = await apiClient.post('/api/validate/stats-format', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    statsResult.value = resp.data || { ok: true, message: '格式检查通过' }
  } catch (err: any) {
    statsResult.value = { ok: false, message: err?.response?.data?.message || '格式校验失败', errors: err?.response?.data?.errors || [] }
  }
}

const checkWeiboFormat = async () => {
  if (!weiboFile.value) return
  const ext = weiboFile.value.name.split('.').pop()?.toLowerCase()
  const allowed = ['txt', 'md']
  if (!ext || !allowed.includes(ext)) {
    weiboResult.value = { ok: false, message: '不支持的文件格式', errors: ['请上传 txt 或 md 文件'] }
    return
  }

  try {
    const fd = new FormData()
    fd.append('file', weiboFile.value)
    const resp = await apiClient.post('/api/validate/weibo-format', fd, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    weiboResult.value = resp.data || { ok: true, message: '格式检查通过' }
  } catch (err: any) {
    weiboResult.value = { ok: false, message: err?.response?.data?.message || '格式校验失败', errors: err?.response?.data?.errors || [] }
  }
}
</script>

<style scoped>
.personality-center {
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
  font-size: 24px;
  font-weight: 600;
}

.page-header p {
  color: #666;
  margin: 0;
  font-size: 14px;
}

/* 配置卡片样式 */
.config-card {
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.config-body {
  padding: 16px 0;
}

.config-card .card-header {
  background-color: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
  padding: 16px 20px;
}

.config-card .card-header h3 {
  color: #333;
  font-size: 18px;
  font-weight: 600;
  margin: 0;
}

/* 上传卡片样式 */
.upload-card {
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.upload-card:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
}

.upload-card .card-header {
  background-color: #f8f9fa;
  border-bottom: 1px solid #e4e7ed;
  padding: 16px 20px;
}

.upload-card .card-header h3 {
  color: #333;
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.total-count {
  color: #666;
  font-size: 13px;
}

.upload-body {
  padding: 20px;
}

.hint {
  color: #909399;
  margin-bottom: 16px;
  font-size: 13px;
  line-height: 1.5;
}

.file-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px;
  background-color: #f8f9fa;
  border-radius: 6px;
  border: 1px dashed #dcdfe6;
}

.file-name {
  color: #303133;
  font-size: 14px;
  font-weight: 500;
}

.file-empty {
  color: #909399;
  font-size: 13px;
  font-style: italic;
}

.actions {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.result {
  margin-top: 16px;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.result p {
  margin: 0 0 8px 0;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
}

.result p.ok {
  background: #f0f9eb;
  color: #67c23a;
  border: 1px solid #e1f3d8;
}

.result p.warn {
  background: #fff6f6;
  color: #f56c6c;
  border: 1px solid #fde2e2;
}

.result ul {
  margin: 8px 0 0 16px;
  padding: 0;
  color: #606266;
  font-size: 13px;
  line-height: 1.5;
}

.result li {
  margin-bottom: 4px;
}

/* 按钮风格保持与 JournalManagement 相近 */
.upload-btn {
  background-color: #9c0e0e;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.3s ease;
}
.upload-btn:hover {
  background-color: #7a0b0b;
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.upload-btn:active {
  transform: translateY(0);
}

/* 确认格式按钮样式 */
.actions .el-button {
  border-radius: 6px;
  font-weight: 500;
}

/* 下拉框样式优化 */
:deep(.el-select) {
  width: 100%;
}

:deep(.el-select .el-input__inner) {
  border-radius: 6px;
  border: 1px solid #dcdfe6;
}

:deep(.el-select .el-input__inner:focus) {
  border-color: #9c0e0e;
  box-shadow: 0 0 0 2px rgba(156, 14, 14, 0.1);
}

/* 响应式处理 */
@media (max-width: 768px) {
  .personality-center {
    padding: 16px;
  }
  
  .file-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .actions {
    flex-direction: column;
    gap: 8px;
  }
  
  .upload-card .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .upload-card .card-header h3 {
    font-size: 15px;
  }
  
  .total-count {
    font-size: 12px;
  }
}

/* 动画效果 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
