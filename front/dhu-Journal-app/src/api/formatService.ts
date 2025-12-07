import apiClient from './axios'

export interface FormatValidationResult {
  ok: boolean
  message: string
  errors?: string[]
}

export interface UploadResponse {
  message: string
  success: boolean
  headers?: Array<{
    template_header: string
    system_key: string | null
    label: string | null
    order: number
    is_custom: boolean
  }>
  template_file_path?: string
}

export interface UserTemplateConfig {
  template_file_path?: string
  column_mapping: Array<{
    system_key: string
    template_header: string
    order: number
    is_custom: boolean
  }>
  created_at?: string
  updated_at?: string
}

export interface UserTuiwenTemplateConfig {
  fields: Array<{
    field: string
    label: string
    required: boolean
    order?: number
    prefix?: string
    format?: { font_name: string; font_size: number; font_color: string }
    prefix_format?: { font_name: string; font_size: number; font_color: string }
  }>
  image_fields?: Array<{
    template_field: string
    selected_type: 'first_image' | 'second_image'
    location?: string
  }>
  template_file_path?: string  // 模板文件路径
  paper_file_path?: string  // 论文文件路径
  paper_cache_path?: string  // 论文缓存路径
  created_at?: string
  updated_at?: string
}

export interface SystemField {
  key: string
  label: string
  category: string
}

/**
 * 格式配置服务
 */
export const formatService = {
  /**
   * 上传统计表格式文件
   * @param file 统计表格式文件
   * @returns 上传结果
   */
  async uploadStatsFormat(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    
    return  await apiClient.post('/upload/stats-format', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    // const response =
    // return response.data
  },


  /**
   * 保存用户统计表模板配置
   * @param templateConfig 模板配置
   * @returns 保存结果
   */
  async saveUserTemplate(templateConfig: UserTemplateConfig): Promise<UploadResponse> {
    return  await apiClient.put('/user/template', templateConfig)
    
    // const response =
    // response.data
  },

  /**
   * 获取用户统计表模板配置
   * @returns 用户模板配置
   */
  async getUserTemplate(): Promise<{ 
    success: boolean
    has_template: boolean
    template_file_path?: string
    column_mapping?: Array<{
      system_key: string
      template_header: string
      order: number
    }>
    created_at?: string
    updated_at?: string
  }> {
    const response = await apiClient.get('/user/template')
    return response as any
  },

  /**
   * 保存用户推文模板配置
   * @param tuiwenConfig 推文模板配置
   * @returns 保存结果
   */
  async saveUserTuiwenTemplate(tuiwenConfig: UserTuiwenTemplateConfig): Promise<UploadResponse> {
    // axios 拦截器已经返回了 response.data，所以这里直接返回 response
    return await apiClient.post('/user/tuiwen-template', tuiwenConfig) as any
  },

  /**
   * 获取用户推文模板配置
   * @returns 用户推文模板配置
   */
  async getUserTuiwenTemplate(): Promise<{
    success: boolean
    has_template: boolean
    fields?: Array<{
      field: string
      label: string
      required: boolean
    }>
    image_fields?: Array<{
      template_field: string
      selected_type: 'first_image' | 'second_image'
      location?: string
    }>
    template_file_path?: string
    paper_file_path?: string
    paper_cache_path?: string
    created_at?: string
    updated_at?: string
  }> {
    const response = await apiClient.get('/user/tuiwen-template')
    return response as any
  },

  /**
   * 删除用户推文模板配置
   * @returns 删除结果
   */
  async deleteUserTuiwenTemplate(): Promise<UploadResponse> {
    // axios 拦截器已经返回了 response.data，所以这里直接返回 response
    return await apiClient.delete('/user/tuiwen-template') as any
  },

  /**
   * 获取系统字段列表
   * @returns 系统字段列表
   */
  async getSystemFields(): Promise<{
    success: boolean
    fields: SystemField[]
  }> {
    const response = await apiClient.get('/template/system-fields')
    return response as any
  },

  /**
   * 删除用户模板配置
   * @returns 删除结果
   */
  async deleteUserTemplate(): Promise<UploadResponse> {
    return await apiClient.delete('/user/template')
  },

  /**
   * 获取用户模板表头识别结果
   * @returns 用户模板表头信息
   */
  async getUserTemplateHeaders(): Promise<{
    success: boolean
    has_template: boolean
    headers: Array<{
      system_key: string
      template_header: string
      order: number
    }>
    template_file_path?: string
  }> {
    // 由于后端没有专门的用户级别获取表头接口，我们使用用户模板配置接口
    // axios 拦截器已经返回了 response.data，所以这里直接使用 response
    const data = await apiClient.get('/user/template') as any
    
    if (data && data.success && data.has_template) {
      return {
        success: true,
        has_template: true,
        headers: data.column_mapping || [],
        template_file_path: data.template_file_path
      }
    } else {
      return {
        success: true,
        has_template: false,
        headers: [],
        template_file_path: undefined
      }
    }
  },

  /**
   * 获取默认推文字段配置
   * @returns 默认推文字段列表
   */
  async getDefaultTuiwenFields(): Promise<{
    success: boolean
    fields: Array<{
      field: string
      label: string
      required: boolean
      order: number
    }>
  }> {
    const response = await apiClient.get('/default/tuiwen-fields')
    return response as any
  },

  /**
   * 上传并识别推文 Word 模板和论文文件
   * @param templateFile Word 模板文件
   * @param paperFile 论文文件（PDF）
   * @returns 识别结果
   */
  async uploadTuiwenTemplate(templateFile: File, paperFile: File): Promise<{
    success: boolean
    fields?: Array<{
      field: string
      label: string
      type: 'placeholder' | 'text_label'
      location: string
      format: { font_name: string; font_size: number; font_color: string }
    }>
    image_fields?: Array<{
      location: string
      detected_type: 'first_image' | 'second_image' | null
    }>
    template_file_path?: string
    paper_file_path?: string
    paper_cache_path?: string
    message?: string
  }> {
    const formData = new FormData()
    formData.append('template_file', templateFile)
    formData.append('paper_file', paperFile)
    const response = await apiClient.post('/upload/tuiwen-template', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return response as any
  },

  /**
   * 生成推文预览
   * @param fieldsConfig 字段配置列表
   * @returns 预览结果
   */
  async generateTuiwenPreview(fieldsConfig: Array<{
    field: string
    label: string
    order: number
    prefix?: string
    format?: { font_name: string; font_size: number; font_color: string }
    prefix_format?: { font_name: string; font_size: number; font_color: string }
  }>): Promise<{
    success: boolean
    preview_file_path?: string
    preview_download_url?: string
    preview_text?: Array<{
      prefix: string
      prefix_style: { font_name: string; font_size: number; font_color: string }
      content: string
      content_style: { font_name: string; font_size: number; font_color: string; font_style?: string }
      is_citation?: boolean
    }>
    message?: string
  }> {
    const response = await apiClient.post('/tuiwen/preview', { fields: fieldsConfig })
    return response as any
  },

}

export default formatService
