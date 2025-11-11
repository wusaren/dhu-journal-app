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
}

class JournalService {
    /**
     * 获取期刊列表
     */
    async getJournals(): Promise<Journal[]> {
        return await apiClient.get('/api/journals')
    }

    /**
     * 获取指定角色的用户列表（封装 admin 接口）
     */
    async getUsersByRole(roleName: string): Promise<SimpleUser[]> {
        const resp: any = await apiClient.get(`/api/admin/users/with-role/${encodeURIComponent(roleName)}`)
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
        const resp = await apiClient.post(`/api/journals/${journalId}/assign`, { assignee_id: assigneeId })
        // 期望返回 { message: '分配成功' }
        return resp.data
    }

    /**
     * 创建期刊
     */
    async createJournal(data: CreateJournalRequest): Promise<ApiResponse<Journal>> {
        return await apiClient.post('/api/journals/create', data)
    }

    /**
     * 删除期刊
     */
    async deleteJournal(journalId: number): Promise<ApiResponse<void>> {
        return await apiClient.delete(`/api/journals/${journalId}`)
    }

    /**
     * 获取论文列表
     */
    async getPapers(journalId?: number): Promise<Paper[]> {
        const params = journalId ? { journalId } : {}
        return await apiClient.get('/api/papers', { params })
    }

    /**
     * 创建论文
     */
    async createPaper(data: any): Promise<ApiResponse<Paper>> {
        return await apiClient.post('/api/papers/create', data)
    }

    /**
     * 更新论文
     */
    async updatePaper(paperId: number, data: any): Promise<ApiResponse<void>> {
        return await apiClient.put(`/api/papers/${paperId}`, data)
    }

    /**
     * 删除论文
     */
    async deletePaper(paperId: number): Promise<ApiResponse<void>> {
        return await apiClient.delete(`/api/papers/${paperId}`)
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

        return await apiClient.post('/api/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        })
    }

    /**
     * 生成目录
     */
    async generateTOC(journalId: number): Promise<ExportResponse> {
        return await apiClient.post('/api/export/toc', { journalId })
    }

    /**
     * 生成推文
     */
    async generateWeibo(journalId: number): Promise<ExportResponse> {
        return await apiClient.post('/api/export/tuiwen', { journalId })
    }

    /**
     * 生成统计表
     */
    async generateStats(journalId: number): Promise<ExportResponse> {
        return await apiClient.post('/api/export/excel', { journalId })
    }

    /**
     * 下载文件
     */
    async downloadFile(filename: string): Promise<void> {
        const link = document.createElement('a')
        link.href = `http://localhost:5000/api/download/${filename}`
        link.download = filename
        link.click()
    }
}

export const journalService = new JournalService()
