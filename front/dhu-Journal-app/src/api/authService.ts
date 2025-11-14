import apiClient from './axios'

export interface LoginRequest {
    username: string
    password: string
}

export interface RegisterRequest {
    username: string
    email: string
    password: string
}

export interface LoginResponse {
    message: string
    user: {
        id: number
        username: string
        email?: string
        role?: string
    }
}

export interface RegisterResponse {
    message: string
}

export interface User {
    id: number
    username: string
    email?: string
    role?: string
}

export interface UserDetail {
    id: number
    username: string
    email: string | null
    role: string | null
}

export const authService = {
    

    // 用户登录
    async login(credentials: LoginRequest): Promise<LoginResponse> {
        return await apiClient.post('/login', credentials)
    },

    // 用户登出
    async logout(): Promise<void> {
        return await apiClient.post('/logout')
    },

    // 获取当前用户信息
    async getCurrentUser(): Promise<User> {
        try {
            const resp = await apiClient.get('/me')
            if (resp && resp.data && resp.data.user) {
                // 同步本地存储以保持兼容
                localStorage.setItem('user', JSON.stringify(resp.data.user))
                return resp.data.user
            }
        } catch (err: any) {
            // 后端未实现或返回401，则回退到 localStorage（兼容旧逻辑）
            const userStr = localStorage.getItem('user')
            if (userStr) {
                try {
                    return JSON.parse(userStr)
                } catch {
                    throw new Error('获取用户信息失败')
                }
            }
            throw new Error(err?.response?.data?.message || '用户未登录')
        }
        // 如果没有返回用户，则抛出错误，保证不会返回 undefined
        throw new Error('无法获取当前用户信息')
    },

    // 检查登录状态
    isLoggedIn(): boolean {
        return !!localStorage.getItem('user')
    },

    // 保存用户信息
    saveUserInfo(user: User): void {
        localStorage.setItem('user', JSON.stringify(user))
    },

    // 清除用户信息
    clearUserInfo(): void {
        localStorage.removeItem('user')
    },

    // 获取当前用户
    getCurrentUserFromStorage(): User | null {
        const userStr = localStorage.getItem('user')
        if (userStr) {
            try {
                return JSON.parse(userStr)
            } catch {
                return null
            }
        }
        return null
    },
    

    // 获取当前用户的详细信息（用户名和邮箱）
    async getCurrentUserDetail(): Promise<UserDetail> {
        try {
        console.log('🟡 开始调用 /api/me 接口')
        
        // 由于拦截器直接返回 data，所以这里接收的就是 { user: {...} }
        const data = await apiClient.get('/me')
        console.log('🟢 直接获取的数据:', data)
        
        if (data && data.user) {
            console.log('🟢 成功获取用户数据:', data.user)
            return data.user
        } else {
            console.log('🔴 数据格式不正确:', data)
            throw new Error('获取用户详细信息失败: 数据格式不正确')
        }
        } catch (error: any) {
            console.log('🔴 API 调用错误:', error)
            throw new Error(error?.message || '获取用户信息失败')
        }
}
}