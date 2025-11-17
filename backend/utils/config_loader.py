import json
import os
from typing import List, Dict, Any
from pathlib import Path
class UserConfig:
    def __init__(self, config_path: str = None):
      # If no path is provided, build the path relative to this file to avoid backslash escape issues        
        if config_path is None:
            base_dir = Path(__file__).resolve().parents[1]  # backend directory
            config_path = base_dir / "config" / "users.json"
        self.config_path = str(config_path)
        self.users = []
        self.roles = []
        self.load_config()

    
    def load_config(self):
        """加载用户配置文件"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as file:
            config_data = json.load(file)
            
        self.users = config_data.get('users', [])
        self.roles = config_data.get('roles', [])
    
    def get_users(self) -> List[Dict[str, Any]]:
        """获取所有用户配置"""
        return self.users
    
    def get_roles(self) -> List[Dict[str, Any]]:
        """获取所有角色配置"""
        return self.roles
    
    def get_user_by_username(self, username: str) -> Dict[str, Any]:
        """根据用户名获取用户配置"""
        for user in self.users:
            if user.get('username') == username:
                return user
        return {}