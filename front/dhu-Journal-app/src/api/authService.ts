import apiClient from './axios'

export interface LoginRequest {
    username: string
    password: string
}

export interface LoginResponse {
    access_token: string
    user: {
        id: number
        username: string
        email?: string
        role?: string
    }
}

export interface User {
    id: number
    username: string
    email?: string
    role?: string
}

export const authService = {
    // 用户登录
    async login(credentials: LoginRequest): Promise<LoginResponse> {
        return await apiClient.post('/auth/login', credentials)
    },

    // 用户登出
    async logout(): Promise<void> {
        return await apiClient.post('/auth/logout')
    },

    // 获取当前用户信息
    async getCurrentUser(): Promise<User> {
        return await apiClient.get('/auth/me')
    },

    // 检查登录状态
    isLoggedIn(): boolean {
        return !!localStorage.getItem('token')
    },

    // 获取token
    getToken(): string | null {
        return localStorage.getItem('token')
    },

    // 保存用户信息
    saveUserInfo(token: string, user: User): void {
        localStorage.setItem('token', token)
        localStorage.setItem('user', JSON.stringify(user))
    },

    // 清除用户信息
    clearUserInfo(): void {
        localStorage.removeItem('token')
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
