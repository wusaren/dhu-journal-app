<template>
  <el-dialog
    v-model="dialogVisible"
    title="模板配置"
    width="1000px"
    @close="handleClose"
  >
    <div class="template-config-container">
      <!-- 步骤0：选择模板类型 -->
      <div v-if="step === 0" class="type-selection-section">
        <div class="section-header">
          <h3>选择模板类型</h3>
        </div>
        <div class="type-options">
          <el-card 
            class="type-card" 
            :class="{ 'selected': templateType === 'stats' }"
            @click="templateType = 'stats'"
          >
            <div class="type-icon">📊</div>
            <h4>统计表模板</h4>
            <p>配置Excel统计表的格式和列</p>
          </el-card>
          <el-card 
            class="type-card" 
            :class="{ 'selected': templateType === 'tuiwen' }"
            @click="templateType = 'tuiwen'"
          >
            <div class="type-icon">📝</div>
            <h4>推文模板</h4>
            <p>配置推文Word文档的格式和内容</p>
          </el-card>
        </div>
      </div>

      <!-- 步骤1：上传模板文件（仅统计表） -->
      <div v-if="step === 1 && templateType === 'stats'" class="upload-section">
        <el-upload
          class="upload-dragger"
          drag
          :auto-upload="false"
          :on-change="handleFileChange"
          :file-list="fileList"
          accept=".xlsx,.xls"
        >
          <el-icon class="el-icon--upload"><upload-filled /></el-icon>
          <div class="el-upload__text">
            将Excel模板文件拖到此处，或<em>点击上传</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              只支持 .xlsx 或 .xls 格式的Excel文件
            </div>
          </template>
        </el-upload>
        
        <div v-if="uploading" class="upload-status">
          <el-icon class="is-loading"><loading /></el-icon>
          <span>正在上传并识别表头...</span>
        </div>
      </div>

      <!-- 步骤1：选择字段（仅推文） -->
      <div v-if="step === 1 && templateType === 'tuiwen'" class="field-selection-section">
        <div class="section-header">
          <h3>选择推文字段</h3>
          <span class="hint-text">选择要在推文中显示的字段，可以调整顺序</span>
        </div>

        <div class="fields-list">
          <div
            v-for="(field, index) in tuiwenFields"
            :key="index"
            class="field-item"
            :draggable="true"
            @dragstart="handleTuiwenDragStart(index, $event)"
            @dragover.prevent="handleTuiwenDragOver($event)"
            @drop="handleTuiwenDrop(index, $event)"
          >
            <div class="field-info">
              <span class="field-number">{{ index + 1 }}</span>
              <span class="field-label">{{ field.label }}</span>
              <span class="drag-indicator">☰</span>
            </div>
            
            <div class="field-actions">
              <el-button
                size="small"
                type="danger"
                text
                @click="removeTuiwenField(index)"
              >
                删除
              </el-button>
            </div>
          </div>
        </div>

        <div class="add-field-section">
          <el-button type="primary" @click="showAddTuiwenFieldDialog = true">
            添加字段
          </el-button>
        </div>
      </div>


      <!-- 步骤2：推文字段确认（仅推文） -->
      <div v-if="step === 2 && templateType === 'tuiwen'" class="tuiwen-confirm-section">
        <div class="section-header">
          <h3>确认推文字段配置</h3>
          <span class="hint-text">请确认以下字段配置，点击"保存配置"完成设置</span>
        </div>

        <div class="fields-preview">
          <div
            v-for="(field, index) in tuiwenFields"
            :key="index"
            class="field-preview-item"
          >
            <span class="field-order">{{ index + 1 }}</span>
            <span class="field-name">{{ field.label }}</span>
          </div>
        </div>
      </div>

      <!-- 步骤2：配置表头映射（仅统计表） -->
      <div v-if="step === 2 && templateType === 'stats'" class="mapping-section">
        <div class="section-header">
          <h3>表头映射配置</h3>
          <span class="hint-text">请为每个表头选择对应的系统字段，或标记为自定义字段</span>
        </div>

        <div class="headers-list">
          <div
            v-for="(header, index) in headers"
            :key="index"
            class="header-item"
            :draggable="true"
            @dragstart="handleDragStart(index, $event)"
            @dragover.prevent="handleDragOver($event)"
            @drop="handleDrop(index, $event)"
          >
            <div class="header-info">
              <span class="header-number">{{ index + 1 }}</span>
              <span class="header-text">{{ header.template_header }}</span>
              <span class="drag-indicator">☰</span>
            </div>
            
            <div class="header-actions">
              <el-select
                v-model="header.system_key"
                placeholder="选择系统字段"
                clearable
                style="width: 200px;"
                @change="handleHeaderChange(header)"
              >
                <el-option
                  v-for="field in getAvailableFieldsForHeader(header)"
                  :key="field.key"
                  :label="field.label"
                  :value="field.key"
                />
              </el-select>
              
              <el-tag v-if="header.system_key" type="success" style="margin-left: 10px;">
                {{ getFieldLabel(header.system_key) }}
              </el-tag>
              <el-tag v-else type="info" style="margin-left: 10px;">
                自定义字段
              </el-tag>
              
              <el-button
                size="small"
                type="danger"
                text
                @click="removeHeader(index)"
                style="margin-left: 10px;"
              >
                删除
              </el-button>
            </div>
          </div>
        </div>

        <div class="add-field-section">
          <el-button type="primary" @click="showAddFieldDialog = true">
            添加字段
          </el-button>
        </div>
      </div>

      <!-- 添加字段对话框（统计表） -->
      <el-dialog
        v-model="showAddFieldDialog"
        title="添加字段"
        width="500px"
        append-to-body
      >
        <el-select
          v-model="newFieldKey"
          placeholder="选择系统字段"
          style="width: 100%;"
        >
          <el-option
            v-for="field in filteredAvailableFields"
            :key="field.key"
            :label="field.label"
            :value="field.key"
          />
        </el-select>
        <template #footer>
          <el-button @click="showAddFieldDialog = false">取消</el-button>
          <el-button type="primary" @click="handleAddField">确定</el-button>
        </template>
      </el-dialog>

      <!-- 添加推文字段对话框 -->
      <el-dialog
        v-model="showAddTuiwenFieldDialog"
        title="添加推文字段"
        width="500px"
        append-to-body
      >
        <el-select
          v-model="newTuiwenFieldKey"
          placeholder="选择字段"
          style="width: 100%;"
        >
          <el-option
            v-for="field in filteredAvailableTuiwenFields"
            :key="field.key"
            :label="field.label"
            :value="field.key"
          />
        </el-select>
        <template #footer>
          <el-button @click="showAddTuiwenFieldDialog = false">取消</el-button>
          <el-button type="primary" @click="handleAddTuiwenField">确定</el-button>
        </template>
      </el-dialog>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button v-if="step === 1" @click="step = 0">上一步</el-button>
        <el-button v-if="step === 2" @click="step = 1">上一步</el-button>
        <el-button @click="handleClose">取消</el-button>
        <el-button
          v-if="step === 0"
          type="primary"
          :disabled="!templateType"
          @click="handleTypeSelected"
        >
          下一步
        </el-button>
        <el-button
          v-if="step === 1 && templateType === 'stats'"
          type="primary"
          :disabled="!selectedFile"
          @click="handleUpload"
        >
          上传并识别
        </el-button>
        <el-button
          v-if="step === 1 && templateType === 'tuiwen'"
          type="primary"
          :disabled="tuiwenFields.length === 0"
          @click="step = 2"
        >
          下一步
        </el-button>
        <el-button
          v-if="step === 2"
          type="primary"
          :disabled="(templateType === 'stats' && headers.length === 0) || (templateType === 'tuiwen' && tuiwenFields.length === 0)"
          @click="handleSave"
        >
          保存配置
        </el-button>
        <el-button
          v-if="hasTemplate"
          type="danger"
          @click="handleDeleteTemplate"
        >
          删除模板
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Loading } from '@element-plus/icons-vue'
import { journalService } from '@/api/journalService'

const props = defineProps<{
  modelValue: boolean
  journalId?: number
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'saved': []
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const step = ref(0) // 0: 选择类型, 1: 上传/选择字段, 2: 配置映射/确认
const templateType = ref<'stats' | 'tuiwen' | ''>('') // 模板类型
const fileList = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const templateFilePath = ref<string>('')
const headers = ref<Array<{
  template_header: string
  system_key: string | null
  label: string | null
  order: number
  is_custom: boolean
}>>([])
const systemFields = ref<Array<{ key: string; label: string; keywords: string[] }>>([])
const showAddFieldDialog = ref(false)
const newFieldKey = ref<string>('')
const hasTemplate = ref(false)
const dragIndex = ref<number | null>(null)

// 推文字段相关
const tuiwenFields = ref<Array<{ key: string; label: string; order: number }>>([])
const tuiwenFieldDefinitions = ref([
  { key: 'chinese_title', label: '中文标题' },
  { key: 'chinese_authors', label: '中文作者' },
  { key: 'title', label: '标题' },
  { key: 'authors', label: '作者' },
  { key: 'doi', label: 'DOI' },
  { key: 'citation', label: '引用信息' },
  { key: 'page_start', label: '起始页码' },
  { key: 'page_end', label: '结束页码' },
])
const showAddTuiwenFieldDialog = ref(false)
const newTuiwenFieldKey = ref<string>('')
const tuiwenDragIndex = ref<number | null>(null)

// 过滤已使用的系统字段（统计表）
const filteredAvailableFields = computed(() => {
  const usedKeys = new Set(headers.value.map(h => h.system_key).filter(Boolean))
  return systemFields.value.filter(field => !usedKeys.has(field.key))
})

// 过滤已使用的推文字段
const filteredAvailableTuiwenFields = computed(() => {
  const usedKeys = new Set(tuiwenFields.value.map(f => f.key))
  return tuiwenFieldDefinitions.value.filter(field => !usedKeys.has(field.key))
})

// 获取某个表头可选的系统字段（排除已使用的，但包含当前已选的）
const getAvailableFieldsForHeader = (header: any) => {
  const usedKeys = new Set(
    headers.value
      .filter(h => h !== header && h.system_key)
      .map(h => h.system_key)
  )
  return systemFields.value.filter(field => !usedKeys.has(field.key))
}

const getFieldLabel = (key: string) => {
  const field = systemFields.value.find(f => f.key === key)
  return field ? field.label : key
}

// 加载系统字段
const loadSystemFields = async () => {
  try {
    const res = await journalService.getSystemFields()
    if (res.success) {
      systemFields.value = res.fields
    }
  } catch (error) {
    console.error('加载系统字段失败:', error)
  }
}

// 选择模板类型后
const handleTypeSelected = () => {
  if (templateType.value) {
    step.value = 1
    // 加载已保存的配置（如果存在）
    loadSavedConfig()
  }
}

// 文件选择
const handleFileChange = (file: any) => {
  selectedFile.value = file.raw
}

// 上传并识别（仅统计表）
const handleUpload = async () => {
  if (!selectedFile.value || !props.journalId || templateType.value !== 'stats') {
    ElMessage.warning('请选择文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    // 统计表模板：上传Excel并识别表头
    const res = await journalService.uploadTemplate(props.journalId, formData)
    if (res.success) {
      headers.value = res.headers
      templateFilePath.value = res.template_file_path
      step.value = 2
      ElMessage.success('模板上传成功，已识别表头')
    } else {
      ElMessage.error(res.message || '上传失败')
    }
  } catch (error: any) {
    console.error('上传模板失败:', error)
    ElMessage.error(error.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

// 表头映射变化
const handleHeaderChange = (header: any) => {
  if (header.system_key) {
    const field = systemFields.value.find(f => f.key === header.system_key)
    header.label = field?.label || null
    header.is_custom = false
  } else {
    header.label = null
    header.is_custom = true
  }
}

// 删除表头
const removeHeader = (index: number) => {
  headers.value.splice(index, 1)
  // 重新排序
  updateOrders()
}

// 更新 order
const updateOrders = () => {
  headers.value.forEach((h, i) => {
    h.order = i + 1
  })
}

// 拖拽相关
const handleDragStart = (index: number, event: DragEvent) => {
  dragIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
  }
}

const handleDragOver = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const handleDrop = (dropIndex: number, event: DragEvent) => {
  event.preventDefault()
  if (dragIndex.value === null || dragIndex.value === dropIndex) {
    return
  }
  
  const draggedItem = headers.value[dragIndex.value]
  headers.value.splice(dragIndex.value, 1)
  headers.value.splice(dropIndex, 0, draggedItem)
  updateOrders()
  dragIndex.value = null
}

// 添加字段（统计表）
const handleAddField = () => {
  if (!newFieldKey.value) {
    ElMessage.warning('请选择字段')
    return
  }

  const field = systemFields.value.find(f => f.key === newFieldKey.value)
  if (field) {
    headers.value.push({
      template_header: field.label,
      system_key: field.key,
      label: field.label,
      order: headers.value.length + 1,
      is_custom: false
    })
    updateOrders()
    newFieldKey.value = ''
    showAddFieldDialog.value = false
  }
}

// 添加推文字段
const handleAddTuiwenField = () => {
  if (!newTuiwenFieldKey.value) {
    ElMessage.warning('请选择字段')
    return
  }

  const field = tuiwenFieldDefinitions.value.find(f => f.key === newTuiwenFieldKey.value)
  if (field) {
    tuiwenFields.value.push({
      key: field.key,
      label: field.label,
      order: tuiwenFields.value.length + 1
    })
    updateTuiwenOrders()
    newTuiwenFieldKey.value = ''
    showAddTuiwenFieldDialog.value = false
  }
}

// 删除推文字段
const removeTuiwenField = (index: number) => {
  tuiwenFields.value.splice(index, 1)
  updateTuiwenOrders()
}

// 更新推文字段order
const updateTuiwenOrders = () => {
  tuiwenFields.value.forEach((f, i) => {
    f.order = i + 1
  })
}

// 推文字段拖拽相关
const handleTuiwenDragStart = (index: number, event: DragEvent) => {
  tuiwenDragIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
  }
}

const handleTuiwenDragOver = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const handleTuiwenDrop = (dropIndex: number, event: DragEvent) => {
  event.preventDefault()
  if (tuiwenDragIndex.value === null || tuiwenDragIndex.value === dropIndex) {
    return
  }
  
  const draggedItem = tuiwenFields.value[tuiwenDragIndex.value]
  tuiwenFields.value.splice(tuiwenDragIndex.value, 1)
  tuiwenFields.value.splice(dropIndex, 0, draggedItem)
  updateTuiwenOrders()
  tuiwenDragIndex.value = null
}

// 保存配置
const handleSave = async () => {
  if (!props.journalId || !templateType.value) {
    return
  }

  try {
    if (templateType.value === 'stats') {
      // 统计表模板：保存列映射配置
      if (!templateFilePath.value) {
        ElMessage.error('模板文件路径不存在，请重新上传')
        return
      }
      
      const res = await journalService.saveTemplateMapping(
        props.journalId,
        templateFilePath.value,
        headers.value
      )
      
      if (res.success) {
        ElMessage.success('模板配置保存成功')
        hasTemplate.value = true
        emit('saved')
        handleClose()
      } else {
        ElMessage.error(res.message || '保存失败')
      }
    } else {
      // 推文模板：保存字段配置
      const res = await journalService.saveTuiwenTemplateConfig(
        props.journalId,
        tuiwenFields.value
      )
      
      if (res.success) {
        ElMessage.success('推文模板配置保存成功')
        hasTemplate.value = true
        emit('saved')
        handleClose()
      } else {
        ElMessage.error(res.message || '保存失败')
      }
    }
  } catch (error: any) {
    console.error('保存配置失败:', error)
    ElMessage.error(error.message || '保存失败')
  }
}

// 删除模板
const handleDeleteTemplate = async () => {
  if (!props.journalId || !templateType.value) {
    return
  }

  try {
    await ElMessageBox.confirm('确定要删除模板配置吗？', '删除模板', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    })

    const res = templateType.value === 'stats' 
      ? await journalService.deleteTemplate(props.journalId)
      : await journalService.deleteTuiwenTemplate(props.journalId)
    
    if (res.success) {
      ElMessage.success('模板删除成功')
      hasTemplate.value = false
      handleClose()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      console.error('删除模板失败:', error)
      ElMessage.error(error.message || '删除失败')
    }
  }
}

// 加载已保存的配置（当用户选择了模板类型后）
const loadSavedConfig = async () => {
  if (!props.journalId || !templateType.value) {
    return
  }

  try {
    if (templateType.value === 'stats') {
      // 加载统计表模板配置
      const res = await journalService.getTemplateHeaders(props.journalId)
      if (res.success && res.has_template) {
        headers.value = res.headers
        updateOrders()
        templateFilePath.value = res.template_file_path || ''
        hasTemplate.value = true
        step.value = 2
      }
    } else {
      // 加载推文模板配置
      const res = await journalService.getTuiwenTemplate(props.journalId)
      if (res.success && res.has_template && res.fields) {
        tuiwenFields.value = res.fields
        updateTuiwenOrders()
        hasTemplate.value = true
        step.value = 2
      } else if (res.success && res.has_template) {
        // 兼容旧格式（如果有模板文件路径）
        hasTemplate.value = true
        step.value = 1
      }
    }
  } catch (error) {
    console.warn('加载模板配置失败:', error)
  }
}

// 关闭
const handleClose = () => {
  step.value = 0
  templateType.value = ''
  fileList.value = []
  selectedFile.value = null
  headers.value = []
  tuiwenFields.value = []
  templateFilePath.value = ''
  dialogVisible.value = false
}

// 监听对话框打开
watch(() => props.modelValue, (newVal) => {
  if (newVal) {
    loadSystemFields()
    // 不自动加载配置，让用户先选择模板类型
  }
})
</script>

<style scoped>
.template-config-container {
  min-height: 400px;
}

/* 类型选择区域 */
.type-selection-section {
  padding: 20px;
  text-align: center;
}

.type-options {
  display: flex;
  gap: 30px;
  justify-content: center;
  margin-top: 30px;
}

.type-card {
  width: 250px;
  cursor: pointer;
  transition: all 0.3s;
  text-align: center;
  padding: 20px;
}

.type-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.type-card.selected {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.type-icon {
  font-size: 48px;
  margin-bottom: 15px;
}

.type-card h4 {
  margin: 10px 0;
  color: #303133;
  font-size: 18px;
}

.type-card p {
  color: #909399;
  font-size: 14px;
  margin: 0;
}

/* 推文预览区域 */
.tuiwen-preview-section {
  padding: 20px;
}

.placeholder-info {
  margin-top: 20px;
}

.placeholder-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-top: 10px;
}

.placeholder-list code {
  background-color: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  color: #e6a23c;
}

/* 推文确认区域 */
.tuiwen-confirm-section {
  padding: 20px;
}

.fields-preview {
  margin-top: 20px;
}

.field-preview-item {
  display: flex;
  align-items: center;
  padding: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  margin-bottom: 10px;
  background-color: #fafafa;
}

.field-preview-item .field-order {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background-color: #67c23a;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: bold;
  margin-right: 12px;
}

.field-preview-item .field-name {
  font-weight: 500;
  color: #303133;
}

.upload-section {
  text-align: center;
  padding: 20px;
}

.upload-dragger {
  width: 100%;
}

.upload-status {
  margin-top: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.mapping-section {
  padding: 20px;
}

.section-header {
  margin-bottom: 20px;
}

.section-header h3 {
  margin: 0 0 5px 0;
  font-size: 16px;
  font-weight: 500;
}

.hint-text {
  font-size: 12px;
  color: #909399;
}

.headers-list {
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 20px;
}

.header-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 15px;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  margin-bottom: 10px;
  background-color: #fafafa;
  cursor: move;
  transition: all 0.2s;
}

.header-item:hover {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.header-item[draggable="true"]:active {
  opacity: 0.7;
  transform: scale(1.02);
}

.header-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.header-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background-color: #409eff;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: bold;
}

.header-text {
  font-weight: 500;
  color: #303133;
  flex: 1;
}

.drag-indicator {
  opacity: 0.5;
  font-size: 16px;
  cursor: move;
  margin-left: 10px;
  color: #909399;
}

.drag-indicator:hover {
  opacity: 1;
  color: #409eff;
}

.add-field-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e4e7ed;
  text-align: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.dialog-footer {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
</style>

