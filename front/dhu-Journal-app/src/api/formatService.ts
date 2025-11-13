import apiClient from './axios'

export interface FormatValidationResult {
  ok: boolean
  message: string
  errors?: string[]
}

export interface UploadResponse {
  message: string
  success: boolean
}

export interface UserTemplateConfig {
  template_file_path?: string
  column_mapping: Array<{
    system_field: string
    template_header: string
    order: number
  }>
  created_at?: string
  updated_at?: string
}

export interface UserTuiwenTemplateConfig {
  fields: Array<{
    field: string
    label: string
    required: boolean
  }>
  created_at?: string
  updated_at?: string
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
    
    const response = await apiClient.post('/upload/stats-format', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    return response.data
  },

  /**
   * 上传推文格式文件
   * @param file 推文格式文件
   * @returns 上传结果
   */
  async uploadWeiboFormat(file: File): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await apiClient.post('/upload/tuiwen-format', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
    
    return response.data
  },

  /**
   * 保存用户统计表模板配置
   * @param templateConfig 模板配置
   * @returns 保存结果
   */
  async saveUserTemplate(templateConfig: UserTemplateConfig): Promise<UploadResponse> {
    const response = await apiClient.post('/user/template', templateConfig)
    return response.data
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
      system_field: string
      template_header: string
      order: number
    }>
    created_at?: string
    updated_at?: string
  }> {
    const response = await apiClient.get('/user/template')
    return response.data
  },

  /**
   * 保存用户推文模板配置
   * @param tuiwenConfig 推文模板配置
   * @returns 保存结果
   */
  async saveUserTuiwenTemplate(tuiwenConfig: UserTuiwenTemplateConfig): Promise<UploadResponse> {
    const response = await apiClient.post('/user/tuiwen-template', tuiwenConfig)
    return response.data
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
    created_at?: string
    updated_at?: string
  }> {
    const response = await apiClient.get('/user/tuiwen-template')
    return response.data
  },

}

export default formatService
