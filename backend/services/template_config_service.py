"""
用户模板配置服务 - 使用 JSON 文件存储每个用户的模板配置
"""
import os
import json
import logging
import shutil
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# 配置存储目录（相对于 backend 目录）
CONFIG_DIR = Path(__file__).parent.parent / 'user_configs'
CONFIG_DIR.mkdir(exist_ok=True)

class TemplateConfigService:
    """用户模板配置服务类"""
    
    def get_user_config_dir(self, user_id: int) -> Path:
        """获取用户配置目录"""
        user_dir = CONFIG_DIR / f"user_{user_id}"
        user_dir.mkdir(exist_ok=True)
        return user_dir
    
    def get_config_file_path(self, user_id: int) -> Path:
        """获取用户配置文件的路径"""
        user_dir = self.get_user_config_dir(user_id)
        return user_dir / "stats_template.json"
    
    def get_template_file_path(self, user_id: int, filename: str) -> Path:
        """获取用户模板文件的路径"""
        user_dir = self.get_user_config_dir(user_id)
        return user_dir / filename
    
    def save_user_template(self, user_id: int, template_file_path: str, column_mapping: List[Dict]) -> Dict:
        """
        保存用户模板配置到 JSON 文件，并复制模板文件到用户配置目录
        
        Args:
            user_id: 用户ID
            template_file_path: 上传的模板文件路径（临时路径）
            column_mapping: 列映射配置，格式: [
                {'template_header': '稿件号', 'system_key': 'manuscript_id', 'order': 1, 'is_custom': False},
                ...
            ]
        
        Returns:
            {'success': True/False, 'message': '...', 'template_file_path': '...'}
        """
        try:
            config_file = self.get_config_file_path(user_id)
            
            # 复制模板文件到用户配置目录
            source_path = Path(template_file_path)
            if not source_path.exists():
                return {
                    'success': False,
                    'message': f'模板文件不存在: {template_file_path}'
                }
            
            # 生成目标文件名
            target_filename = f"stats_template_{datetime.now().strftime('%Y%m%d_%H%M%S')}{source_path.suffix}"
            target_path = self.get_template_file_path(user_id, target_filename)
            
            # 复制文件
            shutil.copy2(source_path, target_path)
            logger.info(f"已复制用户模板文件: {source_path} -> {target_path}")
            
            # 准备保存的数据
            config_data = {
                'user_id': user_id,
                'template_file_path': str(target_path),
                'column_mapping': column_mapping,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # 保存到 JSON 文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存用户 {user_id} 的模板配置到 {config_file}")
            return {
                'success': True,
                'message': '模板配置保存成功',
                'template_file_path': str(target_path)
            }
        
        except Exception as e:
            logger.error(f"保存用户模板配置失败: {str(e)}")
            return {
                'success': False,
                'message': f'保存配置失败: {str(e)}'
            }
    
    def load_user_config(self, user_id: int) -> Optional[Dict]:
        """
        从 JSON 文件加载用户的模板配置
        
        Args:
            user_id: 用户ID
        
        Returns:
            配置字典，如果文件不存在则返回 None
        """
        try:
            config_file = self.get_config_file_path(user_id)
            
            if not config_file.exists():
                logger.info(f"用户 {user_id} 的配置文件不存在: {config_file}")
                return None
            
            # 读取 JSON 文件
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 检查模板文件是否存在
            template_file_path = config_data.get('template_file_path')
            if template_file_path and not Path(template_file_path).exists():
                logger.warning(f"用户模板文件不存在: {template_file_path}")
                return None
            
            logger.info(f"已加载用户 {user_id} 的模板配置")
            return config_data
        
        except Exception as e:
            logger.error(f"加载用户模板配置失败: {str(e)}")
            return None
    
    def delete_user_config(self, user_id: int) -> Dict:
        """
        删除用户的模板配置文件和模板文件
        
        Args:
            user_id: 用户ID
        
        Returns:
            {'success': True/False, 'message': '...'}
        """
        try:
            config_file = self.get_config_file_path(user_id)
            
            if not config_file.exists():
                return {
                    'success': False,
                    'message': '配置文件不存在'
                }
            
            # 读取配置，删除模板文件
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                template_file_path = config_data.get('template_file_path')
                if template_file_path and Path(template_file_path).exists():
                    Path(template_file_path).unlink()
                    logger.info(f"已删除用户模板文件: {template_file_path}")
            except Exception as e:
                logger.warning(f"删除用户模板文件时出错: {str(e)}")
            
            # 删除配置文件
            config_file.unlink()
            logger.info(f"已删除用户 {user_id} 的配置文件: {config_file}")
            return {
                'success': True,
                'message': '模板配置删除成功'
            }
        
        except Exception as e:
            logger.error(f"删除用户模板配置失败: {str(e)}")
            return {
                'success': False,
                'message': f'删除配置失败: {str(e)}'
            }
    
    def has_user_config(self, user_id: int) -> bool:
        """
        检查用户是否有保存的模板配置
        
        Args:
            user_id: 用户ID
        
        Returns:
            True 如果有配置，False 如果没有
        """
        config_file = self.get_config_file_path(user_id)
        if not config_file.exists():
            return False
        
        # 检查配置是否有效（模板文件是否存在）
        config = self.load_user_config(user_id)
        return config is not None
