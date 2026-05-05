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
  }>
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
    return response as any
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
    // 由于后端没有专门的用户级别删除接口，我们使用一个虚拟的journal_id
    // 或者可以创建一个新的后端接口来处理用户级别的删除
    const response = await apiClient.delete('/journal/0/template')
    return response.data
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
    const response = await apiClient.get('/user/template')
    const data = response.data
    
    if (data.success && data.has_template) {
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

}

export default formatService
