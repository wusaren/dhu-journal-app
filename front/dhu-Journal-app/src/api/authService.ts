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

export const authService = {
    // 用户注册
    async register(credentials: RegisterRequest): Promise<RegisterResponse> {
        return await apiClient.post('/api/register', credentials)
    },

    // 用户登录
    async login(credentials: LoginRequest): Promise<LoginResponse> {
        return await apiClient.post('/api/login', credentials)
    },

    // 用户登出
    async logout(): Promise<void> {
        return await apiClient.post('/api/logout')
    },

    // 获取当前用户信息
    async getCurrentUser(): Promise<User> {
        try {
            const resp = await apiClient.get('/api/me')
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
    }
}
