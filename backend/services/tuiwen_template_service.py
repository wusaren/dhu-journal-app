"""
用户推文模板配置服务 - 使用 JSON 文件存储每个用户的推文模板配置
"""
import os
import json
import logging
import shutil
from typing import Dict, Optional, List
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# 配置存储目录（相对于 backend 目录）
CONFIG_DIR = Path(__file__).parent.parent / 'user_configs'
CONFIG_DIR.mkdir(exist_ok=True)

class TuiwenTemplateService:
    """用户推文模板配置服务类"""
    
    def get_user_config_dir(self, user_id: int) -> Path:
        """获取用户配置目录"""
        user_dir = CONFIG_DIR / f"user_{user_id}"
        user_dir.mkdir(exist_ok=True)
        return user_dir
    
    def get_config_file_path(self, user_id: int) -> Path:
        """获取用户配置文件的路径"""
        user_dir = self.get_user_config_dir(user_id)
        return user_dir / "weibo_template.json"
    
    def save_user_template_config(
        self,
        user_id: int,
        fields: List[Dict],
        template_file_path: Optional[str] = None,
        image_fields: Optional[List[Dict]] = None,
        paper_file_path: Optional[str] = None,
        paper_cache_path: Optional[str] = None
    ) -> Dict:
        """
        保存用户推文模板字段配置到 JSON 文件
        
        Args:
            user_id: 用户ID
            fields: 字段配置列表，格式: [{'key': 'title', 'label': '标题', 'order': 1}, ...]
        
        Returns:
            {'success': True/False, 'message': '...'}
        """
        try:
            config_file = self.get_config_file_path(user_id)
            
            existing_config: Optional[Dict] = None
            if config_file.exists():
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        existing_config = json.load(f)
                except Exception:
                    existing_config = None

            # 准备保存的数据
            config_data = {
                'user_id': user_id,
                'fields': fields,
                'image_fields': image_fields if image_fields is not None else existing_config.get('image_fields') if existing_config else [],
                'template_file_path': template_file_path or (existing_config.get('template_file_path') if existing_config else None),
                'paper_file_path': paper_file_path or (existing_config.get('paper_file_path') if existing_config else None),
                'paper_cache_path': paper_cache_path or (existing_config.get('paper_cache_path') if existing_config else None),
                'created_at': existing_config.get('created_at') if existing_config else datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # 保存到 JSON 文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存用户 {user_id} 的推文模板字段配置到 {config_file}")
            return {
                'success': True,
                'message': '推文模板配置保存成功'
            }
        
        except Exception as e:
            logger.error(f"保存用户推文模板配置失败: {str(e)}")
            return {
                'success': False,
                'message': f'保存配置失败: {str(e)}'
            }
    
    def load_user_config(self, user_id: int) -> Optional[Dict]:
        """
        从 JSON 文件加载用户的推文模板配置
        
        Args:
            user_id: 用户ID
        
        Returns:
            配置字典，如果文件不存在则返回 None
        """
        try:
            config_file = self.get_config_file_path(user_id)
            
            if not config_file.exists():
                logger.info(f"用户 {user_id} 的推文模板配置文件不存在: {config_file}")
                return None
            
            # 读取 JSON 文件
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 检查是否有字段配置
            if 'fields' not in config_data:
                logger.warning(f"用户推文模板配置格式不正确: {config_file}")
                return None
            
            logger.info(f"已加载用户 {user_id} 的推文模板配置")
            return config_data
        
        except Exception as e:
            logger.error(f"加载用户推文模板配置失败: {str(e)}")
            return None
    
    def delete_user_config(self, user_id: int) -> Dict:
        """
        删除用户的推文模板配置文件
        
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

            # 读取配置以删除相关文件
            related_files = []
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    related_files.extend([
                        config_data.get('template_file_path'),
                        config_data.get('paper_file_path'),
                        config_data.get('paper_cache_path')
                    ])
            except Exception as e:
                logger.warning(f"读取配置文件失败，无法删除相关文件: {str(e)}")

            # 删除配置文件
            config_file.unlink()
            logger.info(f"已删除用户 {user_id} 的推文模板配置文件: {config_file}")

            # 删除相关文件
            for file_path in related_files:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"已删除关联文件: {file_path}")
                    except Exception as e:
                        logger.warning(f"删除文件失败 {file_path}: {str(e)}")

            return {
                'success': True,
                'message': '推文模板配置删除成功'
            }
        
        except Exception as e:
            logger.error(f"删除用户推文模板配置失败: {str(e)}")
            return {
                'success': False,
                'message': f'删除配置失败: {str(e)}'
            }
    
    def has_user_config(self, user_id: int) -> bool:
        """
        检查用户是否有保存的推文模板配置
        
        Args:
            user_id: 用户ID
        
        Returns:
            True 如果有配置，False 如果没有
        """
        config_file = self.get_config_file_path(user_id)
        if not config_file.exists():
            return False
        
        # 检查配置是否有效
        config = self.load_user_config(user_id)
        return config is not None
