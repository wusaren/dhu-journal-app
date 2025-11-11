"""
推文模板配置服务 - 使用 JSON 文件存储每个期刊的推文模板配置
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
CONFIG_DIR = Path(__file__).parent.parent / 'configs'
TUIWEN_TEMPLATE_DIR = CONFIG_DIR / 'tuiwen_templates'
CONFIG_DIR.mkdir(exist_ok=True)
TUIWEN_TEMPLATE_DIR.mkdir(exist_ok=True)

class TuiwenTemplateService:
    """推文模板配置服务类"""
    
    def get_config_file_path(self, journal_id: int) -> Path:
        """获取配置文件的路径"""
        return CONFIG_DIR / f"journal_{journal_id}_tuiwen_template.json"
    
    def get_template_file_path(self, journal_id: int, filename: str) -> Path:
        """获取模板文件的路径"""
        return TUIWEN_TEMPLATE_DIR / f"journal_{journal_id}_{filename}"
    
    def save_template_config(self, journal_id: int, fields: List[Dict]) -> Dict:
        """
        保存推文模板字段配置到 JSON 文件
        
        Args:
            journal_id: 期刊ID
            fields: 字段配置列表，格式: [{'key': 'title', 'label': '标题', 'order': 1}, ...]
        
        Returns:
            {'success': True/False, 'message': '...'}
        """
        try:
            config_file = self.get_config_file_path(journal_id)
            
            # 准备保存的数据
            config_data = {
                'journal_id': journal_id,
                'fields': fields,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # 保存到 JSON 文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存期刊 {journal_id} 的推文模板字段配置到 {config_file}")
            return {
                'success': True,
                'message': '推文模板配置保存成功'
            }
        
        except Exception as e:
            logger.error(f"保存推文模板配置失败: {str(e)}")
            return {
                'success': False,
                'message': f'保存配置失败: {str(e)}'
            }
    
    def load_config(self, journal_id: int) -> Optional[Dict]:
        """
        从 JSON 文件加载期刊的推文模板配置
        
        Args:
            journal_id: 期刊ID
        
        Returns:
            配置字典，如果文件不存在则返回 None
        """
        try:
            config_file = self.get_config_file_path(journal_id)
            
            if not config_file.exists():
                logger.info(f"期刊 {journal_id} 的推文模板配置文件不存在: {config_file}")
                return None
            
            # 读取 JSON 文件
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 检查是否有字段配置（新格式）或模板文件路径（旧格式）
            if 'fields' not in config_data and 'template_file_path' not in config_data:
                logger.warning(f"推文模板配置格式不正确: {config_file}")
                return None
            
            logger.info(f"已加载期刊 {journal_id} 的推文模板配置")
            return config_data
        
        except Exception as e:
            logger.error(f"加载推文模板配置失败: {str(e)}")
            return None
    
    def delete_config(self, journal_id: int) -> Dict:
        """
        删除期刊的推文模板配置文件和模板文件
        
        Args:
            journal_id: 期刊ID
        
        Returns:
            {'success': True/False, 'message': '...'}
        """
        try:
            config_file = self.get_config_file_path(journal_id)
            
            if not config_file.exists():
                return {
                    'success': False,
                    'message': '配置文件不存在'
                }
            
            # 读取配置，删除模板文件（如果有旧格式的模板文件）
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                template_file_path = config_data.get('template_file_path')
                if template_file_path and Path(template_file_path).exists():
                    Path(template_file_path).unlink()
                    logger.info(f"已删除推文模板文件: {template_file_path}")
            except Exception as e:
                logger.warning(f"删除推文模板文件时出错: {str(e)}")
            
            # 删除配置文件
            config_file.unlink()
            logger.info(f"已删除期刊 {journal_id} 的推文模板配置文件: {config_file}")
            return {
                'success': True,
                'message': '推文模板配置删除成功'
            }
        
        except Exception as e:
            logger.error(f"删除推文模板配置失败: {str(e)}")
            return {
                'success': False,
                'message': f'删除配置失败: {str(e)}'
            }
    
    def has_config(self, journal_id: int) -> bool:
        """
        检查期刊是否有保存的推文模板配置
        
        Args:
            journal_id: 期刊ID
        
        Returns:
            True 如果有配置，False 如果没有
        """
        config_file = self.get_config_file_path(journal_id)
        if not config_file.exists():
            return False
        
        # 检查配置是否有效（模板文件是否存在）
        config = self.load_config(journal_id)
        return config is not None

