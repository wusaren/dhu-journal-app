import apiClient from './axios'

export interface Journal {
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

export interface SimpleUser {
    id: number
    username: string
    email?: string
    active?: boolean
}

export interface CreateJournalRequest {
    issue: string
    title: string
    publish_date: string
    status: string
    description?: string
}

export interface Paper {
    id: number
    journal_id: number
    title: string
    authors: string
    first_author: string
    corresponding: string
    doi: string
    page_start: number
    page_end: number
    pdf_pages: number
    manuscript_id: string
    issue: string
    is_dhu: boolean
    abstract: string
    keywords: string
    file_path: string
    created_at: string
}

export interface ExportResponse {
    message: string
    downloadUrl: string
    filePath: string
}

export interface ApiResponse<T> {
    success: boolean
    message: string
    data?: T
    duplicate?: boolean
}

export interface ColumnDefinition {
    key: string
    label: string
    category: string
}

export interface ColumnConfig {
    key: string
    order: number
}

class JournalService {
    /**
     * 获取期刊列表
     */
    async getJournals(): Promise<Journal[]> {
        return await apiClient.get('/journals')
    }

    /**
     * 获取指定角色的用户列表（封装 admin 接口）
     */
    async getUsersByRole(roleName: string): Promise<SimpleUser[]> {
        const resp: any = await apiClient.get(`/admin/users/with-role/${encodeURIComponent(roleName)}`)
        console.log('API返回数据:', resp) // 调试日志
        
        // 由于axios拦截器直接返回response.data，resp已经是解析后的数据
        // 检查不同的数据结构可能性
        if (resp) {
            // 情况1: 直接返回用户数组
            if (Array.isArray(resp)) {
                return resp as SimpleUser[]
            }
            // 情况2: 返回 { users: [...] }
            if (resp.users && Array.isArray(resp.users)) {
                return resp.users as SimpleUser[]
            }
            // 情况3: 返回 { data: [...] }
            if (resp.data && Array.isArray(resp.data)) {
                return resp.data as SimpleUser[]
            }
        }
        console.warn('无法解析用户列表数据:', resp)
        return []
    }

    /**
     * 为期刊分配用户（更新 journal.created_by）
     */
    async assignJournal(journalId: number, assigneeId: number): Promise<{ message: string }> {
        const resp = await apiClient.post(`/journals/${journalId}/assign`, { assignee_id: assigneeId })
        // 期望返回 { message: '分配成功' }
        return resp.data
    }

    /**
     * 创建期刊
     */
    async createJournal(data: CreateJournalRequest): Promise<ApiResponse<Journal>> {
        return await apiClient.post('/journals/create', data)
    }

    /**
     * 删除期刊
     */
    async deleteJournal(journalId: number): Promise<ApiResponse<void>> {
        return await apiClient.delete(`/journals/${journalId}`)
    }

    /**
     * 获取论文列表
     */
    async getPapers(journalId?: number): Promise<Paper[]> {
        const params = journalId ? { journalId } : {}
        return await apiClient.get('/papers', { params })
    }

    /**
     * 创建论文
     */
    async createPaper(data: any): Promise<ApiResponse<Paper>> {
        return await apiClient.post('/papers/create', data)
    }

    /**
     * 更新论文
     */
    async updatePaper(paperId: number, data: any): Promise<ApiResponse<void>> {
        return await apiClient.put(`/papers/${paperId}`, data)
    }

    /**
     * 删除论文
     */
    async deletePaper(paperId: number): Promise<ApiResponse<void>> {
        return await apiClient.delete(`/papers/${paperId}`)
    }

    /**
     * 文件上传
     */
    async uploadFile(file: File, journalId?: string): Promise<any> {
        const formData = new FormData()
        formData.append('file', file)
        if (journalId) {
            formData.append('journalId', journalId)
        }

        return await apiClient.post('/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
    }

    /**
     * 生成目录
     */
    async generateTOC(journalId: number): Promise<ExportResponse> {
        return await apiClient.post('/export/toc', { journalId })
    }

    /**
     * 生成推文
     */
    async generateWeibo(journalId: number): Promise<ExportResponse> {
        return await apiClient.post('/export/tuiwen', { journalId })
    }
    /**
     * 获取可用列定义
     */
    
    async getAvailableColumns(): Promise<{ success: boolean; columns: ColumnDefinition[] }> {
        return await apiClient.get('/export/columns')
    }

    /**
     * 生成统计表（支持自定义列配置）
     */
    async generateStats(journalId: number, columns?: ColumnConfig[]): Promise<ExportResponse> {
        const data: any = { journalId }
        if (columns) {
            data.columns = columns
        }
        return await apiClient.post('/export/excel', data)
    }

    /**
     * 保存列配置到 JSON 文件
     */
    async saveColumnConfig(journalId: number, columns: ColumnConfig[]): Promise<ApiResponse<void>> {
        return await apiClient.post('/export/columns/config', {
            journalId,
            columns
        })
    }

    /**
     * 从 JSON 文件加载列配置
     */
    async getColumnConfig(journalId: number): Promise<{ success: boolean; has_config: boolean; columns: ColumnConfig[] | null }> {
        return await apiClient.get(`/export/columns/config/${journalId}`)
    }

    /**
     * 上传Excel模板文件
     */
    async uploadTemplate(journalId: number, formData: FormData): Promise<any> {
        return await apiClient.post(`/journal/${journalId}/template`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
    }

    /**
     * 获取模板表头识别结果
     */
    async getTemplateHeaders(journalId: number): Promise<{ success: boolean; has_template: boolean; headers: any[]; template_file_path?: string }> {
        return await apiClient.get(`/journal/${journalId}/template/headers`)
    }

    /**
     * 保存模板映射配置
     */
    async saveTemplateMapping(journalId: number, templateFilePath: string, columnMapping: any[]): Promise<ApiResponse<void>> {
        return await apiClient.put(`/journal/${journalId}/template/mapping`, {
            template_file_path: templateFilePath,
            column_mapping: columnMapping
        })
    }

    /**
     * 获取模板配置
     */
    async getTemplate(journalId: number): Promise<any> {
        return await apiClient.get(`/journal/${journalId}/template`)
    }

    /**
     * 删除模板
     */
    async deleteTemplate(journalId: number): Promise<ApiResponse<void>> {
        return await apiClient.delete(`/journal/${journalId}/template`)
    }

    /**
     * 获取系统字段列表
     */
    async getSystemFields(): Promise<{ success: boolean; fields: Array<{ key: string; label: string; keywords: string[] }> }> {
        return await apiClient.get('/template/system-fields')
    }

    /**
     * 上传推文模板文件
     */
    async uploadTuiwenTemplate(journalId: number, formData: FormData): Promise<any> {
        return await apiClient.post(`/journal/${journalId}/tuiwen-template`, formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
    }

    /**
     * 保存推文模板字段配置
     */
    async saveTuiwenTemplateConfig(journalId: number, fields: Array<{ key: string; label: string; order: number }>): Promise<ApiResponse<void>> {
        return await apiClient.put(`/journal/${journalId}/tuiwen-template`, {
            fields
        })
    }

    /**
     * 获取推文模板配置
     */
    async getTuiwenTemplate(journalId: number): Promise<{ success: boolean; has_template: boolean; template_file_path?: string }> {
        return await apiClient.get(`/journal/${journalId}/tuiwen-template`)
    }

    /**
     * 删除推文模板
     */
    async deleteTuiwenTemplate(journalId: number): Promise<ApiResponse<void>> {
        return await apiClient.delete(`/journal/${journalId}/tuiwen-template`)
    }

    /**
     * 下载文件
     */
    async downloadFile(filename: string): Promise<void> {
        const link = document.createElement('a')
        link.href = `/download/${filename}`
        link.download = filename
        link.click()
    }
}

export const journalService = new JournalService()
