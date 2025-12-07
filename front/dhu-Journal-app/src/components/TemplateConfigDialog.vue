<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
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

      <!-- 推文模板配置（合并步骤1和2） -->
      <div v-if="step === 1 && templateType === 'tuiwen'" class="tuiwen-config-section">
        <el-row :gutter="20">
          <!-- 左侧：配置区 -->
          <el-col :span="13">
            <el-card>
              <template #header>
                <div class="tuiwen-card-header">
                  <div class="tuiwen-card-header__row">
                    <span class="tuiwen-card-title">推文配置</span>
                    <div class="tuiwen-upload-actions">
                      <el-upload
                        :auto-upload="false"
                        :on-change="handleTuiwenTemplateUpload"
                        :show-file-list="false"
                        accept=".docx,.doc"
                      >
                        <el-button size="small" type="primary">
                          <el-icon style="margin-right: 5px;"><UploadFilled /></el-icon>
                          上传 Word 模板
                        </el-button>
                      </el-upload>
                      <el-upload
                        :auto-upload="false"
                        :on-change="handleTuiwenPaperUpload"
                        :show-file-list="false"
                        accept=".pdf"
                      >
                        <el-button size="small" type="primary">
                          <el-icon style="margin-right: 5px;"><UploadFilled /></el-icon>
                          上传论文 (PDF)
                        </el-button>
                      </el-upload>
                      <el-button size="small" @click="showAddTuiwenFieldDialog = true">
                        + 添加字段
                      </el-button>
                      <el-button 
                        v-if="tuiwenTemplateFile && tuiwenPaperFile" 
                        size="small" 
                        type="success" 
                        @click="uploadTuiwenTemplateAndPaper"
                        :loading="tuiwenTemplateUploading"
                      >
                        开始识别
                      </el-button>
                    </div>
                  </div>
                  <div 
                    v-if="tuiwenTemplateFile || tuiwenPaperFile" 
                    class="tuiwen-upload-status"
                  >
                    <span v-if="tuiwenTemplateFile">✓ 模板已选择: {{ tuiwenTemplateFile.name }}</span>
                    <span v-if="tuiwenPaperFile">✓ 论文已选择: {{ tuiwenPaperFile.name }}</span>
                  </div>
                </div>
              </template>
              
              <!-- 使用折叠面板 -->
              <el-collapse v-model="activeTuiwenFields">
                <el-collapse-item 
                  v-for="(field, index) in tuiwenFields"
                  :key="index"
                  :name="index"
                >
                  <template #title>
                    <div 
                      style="display: flex; align-items: center; width: 100%;"
                      :draggable="true"
                      @dragstart="handleTuiwenDragStart(index, $event)"
                      @dragover.prevent="handleTuiwenDragOver($event)"
                      @drop="handleTuiwenDrop(index, $event)"
                    >
                      <span style="margin-right: 10px; color: #909399; cursor: move;">☰</span>
                      <span style="margin-right: 10px; color: #409eff; font-weight: bold;">{{ index + 1 }}</span>
                      <span style="flex: 1;">{{ field.label }}</span>
                      <el-button 
                        size="small" 
                        text 
                        type="danger" 
                        @click.stop="removeTuiwenField(index)"
                        style="margin-right: 10px;"
                      >
                        删除
                      </el-button>
                    </div>
                  </template>
                  
                  <div v-if="field.type === 'image'" class="field-config-image">
                    <div class="image-inline">
                      <div class="image-inline-info">
                        <span class="image-inline-label">{{ field.label }}</span>
                        <span class="image-inline-location">
                          位置：{{ field.location || '未知' }}
                        </span>
                        <el-tag
                          v-if="field.image_config?.detected_type"
                          size="small"
                          type="info"
                        >
                          自动识别为 {{ field.image_config?.detected_type === 'first_image' ? '作者说' : '配图' }}
                        </el-tag>
                      </div>
                      <div class="image-inline-action">
                        <template v-if="field.image_config?.selected_type">
                          <el-tag
                            :type="field.image_config.selected_type === 'first_image' ? 'info' : 'success'"
                            size="small"
                          >
                            {{ field.image_config.selected_type === 'first_image' ? '作者说链接/OSID' : '论文配图' }}
                          </el-tag>
                          <el-button
                            text
                            type="primary"
                            size="small"
                            @click="resetImageFieldSelection(field)"
                          >
                            重新选择
                          </el-button>
                        </template>
                        <template v-else>
                          <el-select
                        :model-value="field.image_config?.selected_type"
                            placeholder="请选择图片类型"
                            size="small"
                            style="width: 200px;"
                        @update:modelValue="value => updateImageSelectedType(field, value as 'first_image' | 'second_image')"
                          >
                            <el-option label="作者说链接/OSID" value="first_image" />
                            <el-option label="论文配图" value="second_image" />
                          </el-select>
                          <div class="image-field-warning">未识别类型，请选择</div>
                        </template>
                      </div>
                    </div>
                  </div>
                  <div v-else class="field-config-simple">
                    <p class="field-config-simple__label">{{ field.label }}</p>
                    <p class="field-config-simple__key">系统字段：{{ field.key }}</p>
                    <p class="field-config-simple__desc">
                      已继承模板中的字体与排版，生成预览时将按照原样渲染。
                    </p>
                  </div>
                </el-collapse-item>
              </el-collapse>
              
              <div v-if="tuiwenFields.length === 0" style="text-align: center; padding: 40px; color: #909399;">
                <p>还没有添加字段</p>
                <p style="font-size: 12px; margin-top: 10px;">
                  可以上传 Word 模板自动识别，或手动添加字段
                </p>
              </div>

            </el-card>
          </el-col>
          
          <!-- 右侧：预览区 -->
          <el-col :span="11">
            <el-card>
              <template #header>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span>实时预览</span>
                  <el-button 
                    size="small" 
                    @click="handleGeneratePreview"
                    :loading="tuiwenPreviewLoading"
                  >
                    <el-icon style="margin-right: 5px;"><View /></el-icon>
                    刷新预览
                  </el-button>
                </div>
              </template>

              <el-alert
                v-if="hasUnknownImageSelection"
                type="warning"
                :closable="false"
                show-icon
                style="margin-bottom: 12px;"
                description="存在未识别的图片类型，预览会使用默认样式。请在左侧为每张图片选择“作者说”或“配图”。"
              />
              
              <div class="preview-area">
                <div v-if="tuiwenPreviewText.length > 0 || tuiwenPreviewUrl" class="preview-content">
                  <!-- 文本+图片预览 -->
                  <div v-if="previewDisplayItems.length > 0" class="text-preview-container">
                    <div
                      v-for="(item, index) in previewDisplayItems"
                      :key="index"
                      class="preview-line"
                    >
                      <template v-if="item.type === 'text' && item.data">
                        <span
                          v-if="item.data.prefix"
                          class="preview-prefix"
                          :style="getPreviewStyle(item.data.prefix_style)"
                        >
                          {{ item.data.prefix }}
                        </span>
                        <span
                          class="preview-content-text"
                          :class="{ 'citation-style': item.data.is_citation }"
                          :style="getPreviewStyle(item.data.content_style)"
                        >
                          {{ item.data.content }}
                        </span>
                      </template>
                      <template v-else-if="item.type === 'image'">
                        <span
                          class="preview-content-text"
                          :style="getPreviewStyle(item.field?.format || defaultPreviewStyle)"
                        >
                          【{{
                            getImageLabelByType(
                              item.field?.image_config?.selected_type ||
                                item.field?.image_config?.detected_type
                            )
                          }}】
                        </span>
                        <span v-if="!item.field?.image_config?.selected_type" class="preview-image-warning">
                          （请在左侧选择图片类型）
                        </span>
                      </template>
                    </div>
                  </div>
                  
                  <!-- 下载按钮 -->
                  <div style="text-align: center; padding: 15px; border-top: 1px solid #e4e7ed; margin-top: 15px;">
                    <el-button 
                      type="primary" 
                      @click="downloadPreview"
                      v-if="tuiwenPreviewUrl"
                    >
                      <el-icon style="margin-right: 5px;"><Download /></el-icon>
                      下载完整文档
                    </el-button>
                  </div>
                </div>
                <el-empty v-else description="点击刷新生成预览" />
              </div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <!-- 步骤2：推文字段确认（已废弃，保留兼容） -->
      <div v-if="step === 2 && templateType === 'tuiwen'" class="tuiwen-confirm-section" style="display: none;">
        <div class="section-header">
          <h3>配置推文字段格式</h3>
          <span class="hint-text">为每个字段设置前缀和格式，可以生成预览查看效果</span>
        </div>

        <!-- 字段配置列表 -->
        <div class="fields-config-list">
          <div
            v-for="(field, index) in tuiwenFields"
            :key="index"
            class="field-config-item"
          >
            <div class="field-header">
              <span class="field-number">{{ index + 1 }}</span>
              <span class="field-label">{{ field.label }}</span>
            </div>
            
            <div class="field-config-content">
              <!-- 前缀设置 -->
              <div class="config-row">
                <label class="config-label">前缀：</label>
                <el-input
                  v-model="field.prefix"
                  placeholder="例如：1. "
                  style="width: 200px;"
                  clearable
                />
                <span class="config-hint">在字段内容前添加的前缀文字</span>
              </div>
              
              <!-- 前缀格式 -->
              <div class="config-row">
                <label class="config-label">前缀格式：</label>
                <el-select 
                  v-model="field.prefix_format.font_name" 
                  placeholder="字体" 
                  style="width: 140px;"
                  clearable
                >
                  <el-option label="Arial" value="Arial" />
                  <el-option label="Times New Roman" value="Times New Roman" />
                  <el-option label="宋体" value="宋体" />
                  <el-option label="黑体" value="黑体" />
                  <el-option label="微软雅黑" value="微软雅黑" />
                </el-select>
                <el-input-number
                  v-model="field.prefix_format.font_size"
                  :min="8"
                  :max="72"
                  placeholder="大小"
                  style="width: 100px; margin-left: 10px;"
                />
                <el-color-picker
                  v-model="field.prefix_format.font_color"
                  style="margin-left: 10px;"
                />
              </div>
              
              <!-- 字段内容格式 -->
              <div class="config-row">
                <label class="config-label">内容格式：</label>
                <el-select 
                  v-model="field.format.font_name" 
                  placeholder="字体" 
                  style="width: 140px;"
                  clearable
                >
                  <el-option label="Arial" value="Arial" />
                  <el-option label="Times New Roman" value="Times New Roman" />
                  <el-option label="宋体" value="宋体" />
                  <el-option label="黑体" value="黑体" />
                  <el-option label="微软雅黑" value="微软雅黑" />
                </el-select>
                <el-input-number
                  v-model="field.format.font_size"
                  :min="8"
                  :max="72"
                  placeholder="大小"
                  style="width: 100px; margin-left: 10px;"
                />
                <el-color-picker
                  v-model="field.format.font_color"
                  style="margin-left: 10px;"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 预览区域 -->
        <div class="preview-section" style="margin-top: 30px;">
          <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 15px;">
            <el-button 
              type="primary" 
              @click="handleGeneratePreview"
              :loading="tuiwenPreviewLoading"
            >
              <el-icon style="margin-right: 5px;"><View /></el-icon>
              生成预览
            </el-button>
            <span class="hint-text">使用默认论文数据生成预览文档</span>
          </div>
          
          <div v-if="tuiwenPreviewUrl" class="preview-container">
            <div class="preview-header">
              <span>预览效果</span>
              <el-button 
                size="small" 
                text 
                @click="tuiwenPreviewUrl = ''"
              >
                关闭预览
              </el-button>
            </div>
            <div class="preview-content">
              <div style="text-align: center; padding: 20px;">
                <el-button 
                  type="primary" 
                  @click="downloadPreview"
                >
                  <el-icon style="margin-right: 5px;"><Download /></el-icon>
                  下载预览文档
                </el-button>
                <p style="margin-top: 15px; color: #909399; font-size: 14px;">
                  预览文档已生成，点击下载查看完整效果
                </p>
              </div>
            </div>
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
              <!-- 自定义字段可以编辑名称（包括识别出来的自定义字段） -->
              <el-input
                v-if="!header.system_key || header.is_custom"
                v-model="header.template_header"
                size="small"
                class="header-input"
                placeholder="请输入字段名称"
                @blur="handleCustomFieldNameChange(header)"
              />
              <span v-else class="header-text">{{ header.template_header }}</span>
              <span class="drag-indicator">☰</span>
            </div>
            
            <div class="header-actions">
              <el-select
                v-model="header.system_key"
                :placeholder="header.is_custom ? (header.template_header || '自定义字段') : '选择系统字段'"
                clearable
                style="width: 200px;"
                @change="handleHeaderChange(header)"
                @clear="handleHeaderClear(header)"
              >
                <el-option
                  v-for="field in getAvailableFieldsForHeader(header)"
                  :key="field.key"
                  :label="field.label"
                  :value="field.key"
                />
              </el-select>
              
              <el-tag v-if="header.system_key && !header.is_custom" type="success" style="margin-left: 10px;">
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
        <div style="margin-bottom: 15px;">
          <el-radio-group v-model="newFieldType">
            <el-radio label="system">系统字段</el-radio>
            <el-radio label="custom">自定义字段</el-radio>
          </el-radio-group>
        </div>
        
        <!-- 系统字段选择 -->
        <el-select
          v-if="newFieldType === 'system'"
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
        
        <!-- 自定义字段输入 -->
        <el-input
          v-if="newFieldType === 'custom'"
          v-model="newCustomFieldName"
          placeholder="请输入自定义字段名称（将显示在Excel表头）"
          style="width: 100%;"
          clearable
        />
        <div v-if="newFieldType === 'custom'" style="margin-top: 10px; color: #909399; font-size: 12px;">
          提示：自定义字段将不会映射到系统字段
        </div>
        
        <template #footer>
          <el-button @click="handleCloseAddFieldDialog">取消</el-button>
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
          class="next-btn"
          type="primary"
          :disabled="!templateType"
          @click="handleTypeSelected"
        >
          下一步
        </el-button>
        <el-button
          class="upload-btn"
          v-if="step === 1 && templateType === 'stats'"
          type="primary"
          :disabled="!selectedFile"
          @click="handleUpload"
        >
          上传并识别
        </el-button>
        <el-button
          class="save-btn"
          v-if="step === 1 && templateType === 'tuiwen'"
          type="primary"
          :disabled="tuiwenFields.length === 0"
          @click="handleSave"
        >
          保存配置
        </el-button>
        <el-button
          class="save-btn"
          v-if="step === 2"
          type="primary"
          :disabled="(templateType === 'stats' && headers.length === 0) || (templateType === 'tuiwen' && tuiwenFields.length === 0)"
          @click="handleSave"
        >
          保存配置
        </el-button>
        <el-button
          v-if="step === 2 && hasTemplate"
          class="delete-btn"
          type="primary"
          @click="handleDeleteTemplate"
        >
          删除模板
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Loading, View, Download } from '@element-plus/icons-vue'
import { formatService, type UserTemplateConfig, type UserTuiwenTemplateConfig } from '@/api/formatService'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'saved': []
}>()

const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const dialogTitle = computed(() => {
  if (templateType.value === 'tuiwen' && step.value >= 1) {
    return '推文配置'
  }
  return '模板配置'
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
const newFieldType = ref<'system' | 'custom'>('system')
const newCustomFieldName = ref<string>('')
const hasTemplate = ref(false)
const dragIndex = ref<number | null>(null)

// 推文字段相关
const tuiwenFields = ref<Array<{ 
  key: string; 
  label: string; 
  order: number;
  type?: string;
  location?: string;
  detected_type?: string | null;
  image_config?: {
    template_field: string;
    location?: string;
    context?: string;
    detected_type?: string | null;
    selected_type: 'first_image' | 'second_image' | null;
  };
  prefix?: string;
  format?: { font_name: string; font_size: number; font_color: string };
  prefix_format?: { font_name: string; font_size: number; font_color: string };
}>>([])
const availableTuiwenFields = ref<Array<{ key: string; label: string }>>([])
const showAddTuiwenFieldDialog = ref(false)
const newTuiwenFieldKey = ref<string>('')
const tuiwenDragIndex = ref<number | null>(null)
const tuiwenTemplateFilePath = ref<string>('')
const tuiwenPaperFilePath = ref<string>('')
const tuiwenPaperCachePath = ref<string>('')
const tuiwenTemplateFile = ref<File | null>(null)
const tuiwenPaperFile = ref<File | null>(null)
const tuiwenPreviewUrl = ref<string>('')
const tuiwenPreviewText = ref<Array<{
  prefix: string
  prefix_style: { font_name: string; font_size: number; font_color: string }
  content: string
  content_style: { font_name: string; font_size: number; font_color: string; font_style?: string }
  is_citation?: boolean
}>>([])
const tuiwenPreviewLoading = ref(false)
const activeTuiwenFields = ref<number[]>([]) // 折叠面板的激活项
const tuiwenTemplateUploading = ref(false)

// 过滤已使用的系统字段（统计表）
const filteredAvailableFields = computed(() => {
  const usedKeys = new Set(headers.value.map(h => h.system_key).filter(Boolean))
  return systemFields.value.filter(field => !usedKeys.has(field.key))
})

// 过滤已使用的推文字段
const filteredAvailableTuiwenFields = computed(() => {
  const usedKeys = new Set(tuiwenFields.value.map(f => f.key))
  return availableTuiwenFields.value.filter(field => !usedKeys.has(field.key))
})

const defaultPreviewStyle = {
  font_name: '',
  font_size: 12,
  font_color: '#303133'
}

const getImageLabelByType = (
  type: 'first_image' | 'second_image' | null | undefined
) => {
  if (type === 'first_image') return '作者说链接/OSID'
  if (type === 'second_image') return '论文配图'
  return '图片（未识别）'
}

const getFieldKeyForConfig = (field: any) => {
  if (field?.type === 'image') {
    const cfg = field.image_config
    if (cfg?.selected_type) return cfg.selected_type
    if (cfg?.detected_type) return cfg.detected_type
    if (field.detected_type) return field.detected_type
  }
  return field.key
}

const hasUnknownImageSelection = computed(() =>
  tuiwenFields.value.some(
    field => field.type === 'image' && !field.image_config?.selected_type
  )
)

const previewDisplayItems = computed(() => {
  const textQueue = [...tuiwenPreviewText.value]
  const items: Array<{ type: 'text' | 'image'; data?: any; field?: any }> = []

  const sortedFields = [...tuiwenFields.value].sort(
    (a, b) => (a.order ?? 999) - (b.order ?? 999)
  )

  sortedFields.forEach(field => {
    if (field.type === 'image') {
      items.push({ type: 'image', field })
    } else if (textQueue.length > 0) {
      items.push({ type: 'text', data: textQueue.shift() })
    }
  })

  textQueue.forEach(item => items.push({ type: 'text', data: item }))
  return items
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
    const res = await formatService.getSystemFields()
    if (res.success) {
      systemFields.value = res.fields
    }
  } catch (error) {
    console.error('加载系统字段失败:', error)
  }
}

// 加载可用推文字段列表
const loadAvailableTuiwenFields = async () => {
  try {
    const defaultRes = await formatService.getDefaultTuiwenFields()
    if (defaultRes && defaultRes.success && defaultRes.fields) {
      availableTuiwenFields.value = defaultRes.fields.map((field: any) => ({
        key: field.field,
        label: field.label
      }))
    }
  } catch (error) {
    console.error('加载可用推文字段失败:', error)
  }
}

// 选择模板类型后
const handleTypeSelected = async () => {
  if (templateType.value) {
    // 如果是推文模板，先加载可用字段列表
    if (templateType.value === 'tuiwen') {
      await loadAvailableTuiwenFields()
    }
    // 先检查是否有已保存的配置，如果有则跳转到配置页面，否则进入上传/选择字段步骤
    await loadSavedConfig()
  }
}

// 文件选择
const handleFileChange = (file: any) => {
  selectedFile.value = file.raw
}


// 上传并识别（仅统计表）
const handleUpload = async () => {
  if (!selectedFile.value || templateType.value !== 'stats') {
    ElMessage.warning('请选择文件')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    // 统计表模板：上传Excel并识别表头（用户级别）
    const res = await formatService.uploadStatsFormat(selectedFile.value)
    console.log('上传结果:', res) // 调试日志
    templateFilePath.value = res.template_file_path
    console.log("templateFilePath:", templateFilePath.value)
    // 检查返回结果的结构 res
    if (res.success) {
      // 使用后端返回的表头数据
      if (res.headers && res.headers.length > 0) {
        // 转换后端返回的表头格式
        headers.value = res.headers.map((header: any, index: number) => ({
          template_header: header.template_header,
          system_key: header.system_key,
          label: header.label,
          order: index + 1,
          is_custom: header.is_custom
        }))
        console.log('使用后端返回的表头:', headers.value)
      } else {
        // 如果后端没有返回表头，创建默认表头
        headers.value = [
          { template_header: '稿件号', system_key: 'manuscript_id', label: '稿件号', order: 1, is_custom: false },
          { template_header: '标题', system_key: 'title', label: '标题', order: 2, is_custom: false },
          { template_header: '作者', system_key: 'authors', label: '作者', order: 3, is_custom: false },
          { template_header: '一作', system_key: 'first_author', label: '一作', order: 4, is_custom: false },
          { template_header: '通讯', system_key: 'corresponding', label: '通讯', order: 5, is_custom: false },
          { template_header: '刊期', system_key: 'issue', label: '刊期', order: 6, is_custom: false },
          { template_header: '是否东华大学', system_key: 'is_dhu', label: '是否东华大学', order: 7, is_custom: false }
        ]
        console.log('使用默认表头:', headers.value)
      }
      step.value = 2
      ElMessage.success('模板上传成功，请配置表头映射')
    } else {
      // 如果返回结果没有success字段，或者success为false
      const errorMessage = res?.message || '上传失败，请检查文件格式'
      ElMessage.error(errorMessage)
    }
  } catch (error: any) {
    console.error('上传模板失败:', error)
    // 更详细的错误信息
    const errorMessage = error?.response?.data?.message || error?.message || '上传失败，请检查网络连接'
    ElMessage.error(errorMessage)
  } finally {
    uploading.value = false
  }
}

const populateImageFields = (imageFields: Array<any> = []) => {
  const extraMap = new Map<string, any>()
  if (Array.isArray(imageFields)) {
    imageFields.forEach((field: any) => {
      const key = field.location || field.template_field || field.field_name
      if (key) {
        extraMap.set(key, field)
      }
    })
  }

  tuiwenFields.value = tuiwenFields.value.map(field => {
    if (field.type !== 'image') {
      return field
    }

    const extra = extraMap.get(field.location || field.label || field.key) || {}
    const detected = field.detected_type ?? extra.detected_type ?? extra.image_type ?? null
    const selected =
      field.image_config?.selected_type ??
      extra.selected_type ??
      detected ??
      null

    const updatedField = {
      ...field,
      label: getImageLabelByType(selected || detected),
      image_config: {
        template_field: extra.template_field || field.label || '图片',
        location: field.location,
        context: extra.context,
        detected_type: detected,
        selected_type: selected
      }
    }

    return updatedField
  })
}

const buildImageFieldsPayload = () => {
  return tuiwenFields.value
    .filter(field => field.type === 'image')
    .map(field => ({
      template_field: field.image_config?.template_field || field.label || '图片',
      selected_type: field.image_config?.selected_type || 'first_image',
      location: field.location
    }))
}

const ensureImageConfig = (field: any) => {
  if (!field.image_config) {
    field.image_config = {
      template_field: field.label || '图片',
      location: field.location,
      context: '',
      detected_type: field.detected_type || null,
      selected_type: null
    }
  }
  return field.image_config
}

const updateImageSelectedType = (field: any, value: 'first_image' | 'second_image' | null) => {
  if (!field || field.type !== 'image') return
  const config = ensureImageConfig(field)
  config.selected_type = value
  field.label = getImageLabelByType(value || config.detected_type)
  handleImageTypeChange(field)
}

// 表头映射变化
const handleHeaderChange = (header: any) => {
  if (header.system_key) {
    const field = systemFields.value.find(f => f.key === header.system_key)
    header.label = field?.label || null
    header.is_custom = false
    // 如果之前是自定义字段，现在改为系统字段，将表头名称改为系统字段的标签
    if (field) {
      header.template_header = field.label
    }
  } else {
    header.label = null
    header.is_custom = true
    // 标记为自定义字段时，保持当前表头名称不变（用户可以编辑）
    // 确保is_custom为true，这样识别出来的自定义字段也能编辑名称
  }
}

// 清空下拉框时（标记为自定义字段）
const handleHeaderClear = (header: any) => {
  header.system_key = null
  header.label = null
  header.is_custom = true
  // 保持当前表头名称不变
}

// 自定义字段名称变化
const handleCustomFieldNameChange = (header: any) => {
  if (!header.template_header || !header.template_header.trim()) {
    ElMessage.warning('字段名称不能为空')
    // 如果名称为空，恢复为默认值
    header.template_header = '自定义字段'
  } else {
    header.template_header = header.template_header.trim()
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

// 关闭添加字段对话框
const handleCloseAddFieldDialog = () => {
  newFieldKey.value = ''
  newFieldType.value = 'system'
  newCustomFieldName.value = ''
  showAddFieldDialog.value = false
}

// 添加字段（统计表）
const handleAddField = () => {
  if (newFieldType.value === 'system') {
    // 添加系统字段
    if (!newFieldKey.value) {
      ElMessage.warning('请选择系统字段')
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
      handleCloseAddFieldDialog()
    }
  } else {
    // 添加自定义字段
    if (!newCustomFieldName.value || !newCustomFieldName.value.trim()) {
      ElMessage.warning('请输入自定义字段名称')
      return
    }

    const fieldName = newCustomFieldName.value.trim()
    headers.value.push({
      template_header: fieldName,
      system_key: null,
      label: null,
      order: headers.value.length + 1,
      is_custom: true
    })
    updateOrders()
    handleCloseAddFieldDialog()
  }
}

// 添加推文字段
const handleAddTuiwenField = () => {
  if (!newTuiwenFieldKey.value) {
    ElMessage.warning('请选择字段')
    return
  }

  const field = availableTuiwenFields.value.find(f => f.key === newTuiwenFieldKey.value)
  if (field) {
    tuiwenFields.value.push({
      key: field.key,
      label: field.label,
      order: tuiwenFields.value.length + 1,
      prefix: '',
      format: { font_name: '', font_size: 12, font_color: '#000000' },
      prefix_format: { font_name: '', font_size: 12, font_color: '#000000' }
    })
    updateTuiwenOrders()
    newTuiwenFieldKey.value = ''
    showAddTuiwenFieldDialog.value = false
    // 自动刷新预览
    nextTick(() => {
      debouncedGeneratePreview()
    })
  }
}

// 删除推文字段
const removeTuiwenField = (index: number) => {
  tuiwenFields.value.splice(index, 1)
  updateTuiwenOrders()
  // 自动刷新预览
  nextTick(() => {
    debouncedGeneratePreview()
  })
}

// 更新推文字段order
const updateTuiwenOrders = () => {
  tuiwenFields.value.forEach((f, i) => {
    f.order = i + 1
  })
}

// 处理上传 Word 模板
const handleTuiwenTemplateUpload = async (file: any) => {
  if (!file.raw) {
    return
  }
  
  // 保存模板文件
  tuiwenTemplateFile.value = file.raw
  ElMessage.success('模板文件已选择，请继续上传论文文件（PDF格式）')
}

// 处理上传论文文件
const handleTuiwenPaperUpload = async (file: any) => {
  if (!file.raw) {
    return
  }
  
  // 保存论文文件
  tuiwenPaperFile.value = file.raw
  ElMessage.success('论文文件已选择')
  
  // 如果模板文件也已选择，提示可以开始识别
  if (tuiwenTemplateFile.value) {
    ElMessage.info('模板和论文都已选择，请点击"开始识别"按钮')
  }
}

const handleImageTypeChange = () => {
  if (step.value === 1 && templateType.value === 'tuiwen') {
    debouncedGeneratePreview()
  }
}

const resetImageFieldSelection = (field: any) => {
  if (field?.type === 'image') {
    const config = ensureImageConfig(field)
    config.selected_type = null
    handleImageTypeChange()
  }
}

// 上传模板和论文文件
const uploadTuiwenTemplateAndPaper = async () => {
  if (!tuiwenTemplateFile.value || !tuiwenPaperFile.value) {
    ElMessage.error('请同时上传模板文件和论文文件')
    return
  }
  
  try {
    tuiwenTemplateUploading.value = true
    ElMessage.info('正在上传并识别模板...')
    
    const res = await formatService.uploadTuiwenTemplate(tuiwenTemplateFile.value, tuiwenPaperFile.value)
    
    if (res.success && res.fields) {
      // 将识别结果转换为前端格式（简化版，不包含格式编辑）
      tuiwenFields.value = res.fields.map((field: any, index: number) => ({
        key: field.field,
        label: field.label,
        order: index + 1,
        type: field.type,
        location: field.location,
        detected_type: field.detected_type || null,
        prefix: field.prefix || '',
        format: field.format || { font_name: '', font_size: 12, font_color: '#000000' },
        prefix_format: field.prefix_format || { font_name: '', font_size: 12, font_color: '#000000' }
      }))
      populateImageFields(res.image_fields || [])
      
      // 保存模板文件路径和论文文件路径
      if (res.template_file_path) {
        tuiwenTemplateFilePath.value = res.template_file_path
      }
      if (res.paper_file_path) {
        tuiwenPaperFilePath.value = res.paper_file_path
      }
      if (res.paper_cache_path) {
        tuiwenPaperCachePath.value = res.paper_cache_path
      }
      // 展开所有字段
      activeTuiwenFields.value = tuiwenFields.value.map((_, index) => index)
      
      // 自动保存配置（包含论文路径），以便预览时可以使用
      if (tuiwenTemplateFilePath.value && tuiwenPaperFilePath.value) {
        try {
          const userTuiwenConfig: UserTuiwenTemplateConfig = {
            template_file_path: tuiwenTemplateFilePath.value,
            paper_file_path: tuiwenPaperFilePath.value,
            paper_cache_path: tuiwenPaperCachePath.value,
            fields: tuiwenFields.value.map(field => {
              const fieldKey = getFieldKeyForConfig(field)
              return {
                field: fieldKey,
                label: field.label,
                required: false,
                order: field.order,
                type: field.type,
                location: field.location,
                detected_type: field.detected_type || field.image_config?.detected_type || null,
                prefix: field.prefix || '',
                format: field.format || { font_name: '', font_size: 12, font_color: '#000000' },
                prefix_format:
                  field.prefix_format || { font_name: '', font_size: 12, font_color: '#000000' }
              }
            }),
            image_fields: buildImageFieldsPayload()
          }
          await formatService.saveUserTuiwenTemplate(userTuiwenConfig)
          console.log('已自动保存模板配置（包含论文路径）')
        } catch (error) {
          console.warn('自动保存配置失败，但不影响使用:', error)
        }
      }
      
      ElMessage.success(`成功识别 ${res.fields.length} 个字段`)
      
      // 自动生成预览
      await handleGeneratePreview()
    } else {
      ElMessage.error(res.message || '模板识别失败，请尝试手动配置')
    }
  } catch (error: any) {
    console.error('上传模板失败:', error)
    ElMessage.error(error.message || '上传模板失败')
  } finally {
    tuiwenTemplateUploading.value = false
  }
}

// 生成推文预览（带防抖）
let previewTimer: ReturnType<typeof setTimeout> | null = null
const debouncedGeneratePreview = () => {
  if (previewTimer) {
    clearTimeout(previewTimer)
  }
  previewTimer = setTimeout(() => {
    handleGeneratePreview()
  }, 500) // 500ms 防抖
}

// 生成推文预览
const handleGeneratePreview = async () => {
  if (tuiwenFields.value.length === 0) {
    // 如果没有字段，清空预览
    tuiwenPreviewText.value = []
    tuiwenPreviewUrl.value = ''
    return
  }

  try {
    tuiwenPreviewLoading.value = true
    
    // 准备字段配置（使用识别出的格式）
    const fieldsConfig = tuiwenFields.value.map(field => {
      const fieldKey = getFieldKeyForConfig(field)
      return {
        field: fieldKey,
        label: field.label,
        order: field.order,
        prefix: field.prefix || '',
        format: field.format || { font_name: '', font_size: 12, font_color: '#000000' },
        prefix_format: field.prefix_format || {
          font_name: '',
          font_size: 12,
          font_color: '#000000'
        }
      }
    })

    const res = await formatService.generateTuiwenPreview(fieldsConfig)
    
    if (res.success) {
      if (res.preview_download_url) {
        tuiwenPreviewUrl.value = res.preview_download_url
      }
      if (res.preview_text) {
        tuiwenPreviewText.value = res.preview_text
      }
    } else {
      console.error('预览生成失败:', res.message)
    }
  } catch (error: any) {
    console.error('生成预览失败:', error)
  } finally {
    tuiwenPreviewLoading.value = false
  }
}

// 下载预览文档
const downloadPreview = () => {
  if (tuiwenPreviewUrl.value) {
    // 创建临时链接下载
    const link = document.createElement('a')
    link.href = tuiwenPreviewUrl.value
    link.download = '推文预览.docx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}

// 获取预览样式
const getPreviewStyle = (style: { font_name: string; font_size: number; font_color: string; font_style?: string }) => {
  return {
    fontFamily: style.font_name || 'inherit',
    fontSize: `${style.font_size || 12}px`,
    color: style.font_color || '#000000',
    fontStyle: style.font_style || 'normal'
  }
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
  // 自动刷新预览
  nextTick(() => {
    debouncedGeneratePreview()
  })
}

// 保存配置
const handleSave = async () => {
  if (!templateType.value) {
    return
  }

  try {
    if (templateType.value === 'stats') {
      // 统计表模板：保存列映射配置（用户级别）
      const userTemplateConfig: UserTemplateConfig = {
        template_file_path: templateFilePath.value || 'user_template.xlsx', // 添加模板文件路径
        column_mapping: headers.value.map(header => ({
          system_key: header.system_key || header.template_header,
          template_header: header.template_header,
          order: header.order,
          is_custom: header.is_custom
        }))
      }
      
      const res = await formatService.saveUserTemplate(userTemplateConfig)
      
      if (res.success) {
        ElMessage.success('统计表模板配置保存成功')
        hasTemplate.value = true
        emit('saved')
        handleClose()
      } else {
        ElMessage.error(res.message || '保存失败')
      }
    } else {
      // 推文模板：保存字段配置（用户级别）
      const userTuiwenConfig: UserTuiwenTemplateConfig = {
        template_file_path: tuiwenTemplateFilePath.value || undefined,
        paper_file_path: tuiwenPaperFilePath.value || undefined,
        paper_cache_path: tuiwenPaperCachePath.value || undefined,
        fields: tuiwenFields.value.map(field => {
          const fieldKey = getFieldKeyForConfig(field)
          return {
            field: fieldKey,
            label: field.label,
            required: false,
            order: field.order,
            type: field.type,
            location: field.location,
            detected_type: field.detected_type || field.image_config?.detected_type || null,
            prefix: field.prefix || '',
            format: field.format || { font_name: '', font_size: 12, font_color: '#000000' },
            prefix_format:
              field.prefix_format || { font_name: '', font_size: 12, font_color: '#000000' }
          }
        }),
        image_fields: buildImageFieldsPayload()
      }
      
      const res = await formatService.saveUserTuiwenTemplate(userTuiwenConfig)
      
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
  if (!templateType.value) {
    return
  }

  try {
    await ElMessageBox.confirm('确定要删除模板配置吗？', '删除模板', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning'
    })

    // 对于推文模板，使用删除接口
    if (templateType.value === 'tuiwen') {
      const res = await formatService.deleteUserTuiwenTemplate()
      if (res.success) {
        ElMessage.success('推文模板配置删除成功')
        hasTemplate.value = false
        tuiwenFields.value = []
        tuiwenTemplateFilePath.value = ''
        tuiwenPaperFilePath.value = ''
        tuiwenPaperCachePath.value = ''
        tuiwenTemplateFile.value = null
        tuiwenPaperFile.value = null
        handleClose()
      } else {
        ElMessage.error(res.message || '删除失败')
      }
    } else {
      // 统计表模板使用删除接口
      const res = await formatService.deleteUserTemplate()
      if (res.success) {
        ElMessage.success('统计表模板删除成功')
        hasTemplate.value = false
        handleClose()
      } else {
        ElMessage.error(res.message || '删除失败')
      }
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
  if (!templateType.value) {
    return
  }

  try {
    // 确保系统字段已加载（用于显示字段标签）
    if (templateType.value === 'stats' && systemFields.value.length === 0) {
      await loadSystemFields()
    }

    if (templateType.value === 'stats') {
      // 加载统计表模板配置（用户级别）
      const res = await formatService.getUserTemplate()
      console.log('加载统计表模板配置结果:', res)
      if (res && res.success && res.has_template) {
        // 转换数据格式
        headers.value = (res.column_mapping || []).map((mapping: any) => {
          // 如果有system_key，使用系统字段的label，否则使用template_header
          const systemField = systemFields.value.find(f => f.key === mapping.system_key)
          const label = systemField ? systemField.label : mapping.template_header
          return {
            template_header: mapping.template_header,
            system_key: mapping.system_key || null,
            label: label,
            order: mapping.order || 1,
            is_custom: mapping.is_custom || !mapping.system_key
          }
        })
        updateOrders()
        hasTemplate.value = true
        templateFilePath.value = res.template_file_path || ''
        // 有模板配置，直接跳转到配置页面
        step.value = 2
      } else {
        // 没有模板配置，进入上传文件步骤
        step.value = 1
      }
    } else {
      // 加载推文模板配置（用户级别）
      const res = await formatService.getUserTuiwenTemplate()
      console.log('加载推文模板配置结果:', res)
      if (res && res.success && res.has_template && res.fields) {
        // 有用户配置，加载用户配置
        tuiwenFields.value = (res.fields || []).map((field: any) => ({
          key: field.field,
          label: field.label,
          order: field.order || 1,
          type: field.type,
          location: field.location,
          detected_type: field.detected_type || null,
          prefix: field.prefix || '',
          format: field.format || { font_name: '', font_size: 12, font_color: '#000000' },
          prefix_format: field.prefix_format || { font_name: '', font_size: 12, font_color: '#000000' }
        }))
        updateTuiwenOrders()
        hasTemplate.value = true
        tuiwenTemplateFilePath.value = res.template_file_path || ''
        tuiwenPaperFilePath.value = res.paper_file_path || ''
        tuiwenPaperCachePath.value = res.paper_cache_path || ''
        populateImageFields(res.image_fields || [])
        // 有模板配置，直接跳转到配置页面（合并后的单页）
        step.value = 1
        // 展开所有字段以便编辑
        activeTuiwenFields.value = tuiwenFields.value.map((_, index) => index)
        // 自动生成预览
        nextTick(() => {
          handleGeneratePreview()
        })
      } else {
        // 没有用户配置，加载默认配置
        // 注意：availableTuiwenFields 已经在 handleTypeSelected 中加载了
        try {
          const defaultRes = await formatService.getDefaultTuiwenFields()
          if (defaultRes && defaultRes.success && defaultRes.fields) {
            // 如果可用字段列表还没有加载，则加载它
            if (availableTuiwenFields.value.length === 0) {
              availableTuiwenFields.value = defaultRes.fields.map((field: any) => ({
                key: field.field,
                label: field.label
              }))
            }
            // 初始化字段列表为默认配置
            tuiwenFields.value = defaultRes.fields.map((field: any) => ({
              key: field.field,
              label: field.label,
              order: field.order || 1,
              prefix: '',
              format: { font_name: '', font_size: 12, font_color: '#000000' },
              prefix_format: { font_name: '', font_size: 12, font_color: '#000000' }
            }))
            updateTuiwenOrders()
            // 进入字段配置步骤
            step.value = 1
            // 自动生成预览
            nextTick(() => {
              handleGeneratePreview()
            })
          } else {
            step.value = 1
          }
        } catch (error) {
          console.warn('加载默认配置失败:', error)
          step.value = 1
        }
      }
    }
  } catch (error) {
    console.warn('加载模板配置失败:', error)
    // 出错时也进入第一步
    step.value = 1
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
  tuiwenTemplateFilePath.value = ''
  availableTuiwenFields.value = []
  tuiwenPreviewUrl.value = ''
  tuiwenPreviewText.value = []
  tuiwenPreviewLoading.value = false
  activeTuiwenFields.value = []
  tuiwenTemplateUploading.value = false
  dialogVisible.value = false
}

// 监听对话框打开
watch(() => props.modelValue, (newVal: boolean) => {
  if (newVal) {
    loadSystemFields()
    // 不自动加载配置，让用户先选择模板类型
  }
})

// 监听推文字段变化，自动刷新预览
watch(() => tuiwenFields.value, () => {
  if (step.value === 1 && templateType.value === 'tuiwen' && tuiwenFields.value.length > 0) {
    debouncedGeneratePreview()
  }
}, { deep: true })
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

.tuiwen-card-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tuiwen-card-header__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.tuiwen-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.tuiwen-upload-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.tuiwen-upload-actions .el-upload {
  display: inline-flex;
}

.tuiwen-upload-status {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  font-size: 12px;
  color: #909399;
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

/* 字段配置列表 */
.fields-config-list {
  margin-top: 20px;
}

.field-config-item {
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 15px;
  margin-bottom: 15px;
  background-color: #fafafa;
}

.field-config-simple {
  padding: 12px 14px;
  background-color: #f7f9fc;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-config-simple__label {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.field-config-simple__key {
  margin: 0;
  font-size: 13px;
  color: #606266;
}

.field-config-simple__desc {
  margin: 0;
  font-size: 12px;
  color: #909399;
}

.field-header {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e4e7ed;
}

.field-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background-color: #409eff;
  color: white;
  border-radius: 50%;
  font-size: 14px;
  font-weight: bold;
  margin-right: 12px;
}

.field-label {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
}

.field-config-content {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.config-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.config-label {
  min-width: 80px;
  font-size: 14px;
  color: #606266;
  text-align: right;
}

.config-hint {
  font-size: 12px;
  color: #909399;
  margin-left: 10px;
}

/* 预览区域 */
.preview-section {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #e4e7ed;
}

.preview-container {
  margin-top: 15px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  overflow: hidden;
  background-color: #fff;
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 15px;
  background-color: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  font-weight: 500;
  color: #303133;
}

.preview-content {
  padding: 15px;
  background-color: #fff;
}

.preview-area {
  min-height: 460px;
  max-height: 700px;
  overflow-y: auto;
}

.text-preview-container {
  padding: 20px;
  background-color: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  min-height: 360px;
}

.preview-line {
  margin-bottom: 15px;
  line-height: 1.8;
  word-wrap: break-word;
}

.preview-prefix {
  display: inline;
  margin-right: 5px;
}

.preview-content-text {
  display: inline;
}

.preview-content-text.citation-style {
  font-style: italic;
}

.field-config-image {
  padding: 12px 14px;
  background-color: #f7f9fc;
  border: 1px dashed #dcdfe6;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.image-inline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.image-inline-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 14px;
  color: #303133;
}

.image-inline-label {
  font-weight: 600;
}

.image-inline-location {
  font-size: 12px;
  color: #909399;
}

.image-inline-action {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.image-field-warning {
  font-size: 12px;
  color: #e6a23c;
}

.preview-image-warning {
  color: #e6a23c;
  margin-left: 6px;
  font-size: 12px;
}

.image-field-info .detected-type {
  font-size: 12px;
  color: #67c23a;
}

.image-field-info .context-text {
  font-size: 12px;
  color: #909399;
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

/* 推文字段拖拽样式 */
.el-collapse-item__header[draggable="true"] {
  cursor: move;
}

.el-collapse-item__header[draggable="true"]:hover {
  background-color: #f5f7fa;
}

.el-collapse-item__header[draggable="true"]:active {
  opacity: 0.7;
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
  width: 150px;
  margin-right: 10px;
}

.header-input {
  width: 150px;
  margin-right: 10px;
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

.next-btn, .upload-btn {
  min-width: 100px;
  background: #7c0101;
  color: rgb(255, 255, 255);
}

.next-btn:hover, .upload-btn:hover {
  background: #5e0606;
  color: rgb(255, 255, 255);
}

.save-btn {
  min-width: 100px;
  background: #409eff;
  color: rgb(255, 255, 255);
}

.save-btn:hover {
  background: #66b1ff;
  color: rgb(255, 255, 255);
}

.delete-btn {
  min-width: 100px;
  background: #7c0101;
  color: rgb(255, 255, 255);
}

.delete-btn:hover {
  background: #5e0606;
  color: rgb(255, 255, 255);
}
</style>
