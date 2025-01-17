from asyncio.windows_events import NULL
from typing import List, Tuple, Dict, Any, Optional

from app.core.event import eventmanager, Event
from app.helper.downloader import DownloaderHelper
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType, WebhookEventInfo, ServiceInfo
from app.schemas.types import EventType
from app.helper.downloader import DownloaderHelper
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.subscribe_oper import SubscribeOper


class SyncMoviePT(_PluginBase):
    # 插件名称
    plugin_name = "订阅种子同步管理"
    # 插件描述
    plugin_desc = "SyncMoviePT 是一个用于同步订阅，管理种子。"
    # 插件图标
    plugin_icon = "Moviepilot_A.png"
    # 插件版本
    plugin_version = "0.3"
    # 插件作者
    plugin_author = "k0ala"
    # 作者主页
    author_url = "https://github.com/liushaoxiong10"
    
    enabled = False
    onlyonce = False
    cron = ""
    downloadOper = NULL
    subscript = NULL

    def init_plugin(self, config = None):
        self.enabled = config.get("enabled")
        self.onlyonce = config.get("onlyonce")
        self.cron = config.get("cron")
        self.downloadOper = DownloadHistoryOper()
        self.subscript = SubscribeOper()
        
    def get_state(self) -> bool:
        return self.enabled
   
    @staticmethod 
    def get_command(self) -> List[Dict[str, Any]]:
        """
        指令格式:
        - syncmoviept
        """
        pass
    
    def get_api(self) -> List[Dict[str, Any]]:
        """
        插件API
        """
        pass
        
    def syncmoviept(self):
        """
        同步种子
        """
        logger.info("syncmoviept")
        down = self.downloadOper.list_by_page(1, 100)
        for item in down:
            logger.info("download item", item)
            sub = self.subscript.get_by_tmdbid(item.tmdbid)
            if sub:
                logger.info("sub item", sub)
                if sub.torrentid == item.torrentid:
                    logger.info("sub item torrentid", sub.torrentid)
                    continue
                else:
                    logger.info("sub item torrentid not equal", sub.torrentid, item.torrentid)
                    sub.torrentid = item.torrentid
                    self.subscript.update(sub)
            else:
                logger.info("sub item not exist", sub)
                self.subscript.add(tmdbid=item.tmdbid, torrentid=item.torrentid)
        return "success"
 
    
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        """
        拼装插件配置页面，需要返回两块数据：1、页面配置；2、数据结构
        """
        # 遍历 NotificationType 枚举，生成消息类型选项
        msg_type_options = []
        default_msg_type_values = []
        for item in NotificationType:
            msg_type_options.append({
                "title": item.value,
                "value": item.name
            })
            default_msg_type_values.append(item.name)
        return [
            {
                'component': 'VForm',
                'content': [
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12,
                                    'md': 6
                                },
                                'content': [
                                    {
                                        'component': 'VSwitch',
                                        'props': {
                                            'model': 'enabled',
                                            'label': '启用插件',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'webhookurl',
                                            'label': 'WebHook地址',
                                            'placeholder': 'https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxxxxxx',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VTextField',
                                        'props': {
                                            'model': 'secret',
                                            'label': '密钥',
                                            'placeholder': '如设置了签名校验，请输入密钥',
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                    {
                        'component': 'VRow',
                        'content': [
                            {
                                'component': 'VCol',
                                'props': {
                                    'cols': 12
                                },
                                'content': [
                                    {
                                        'component': 'VSelect',
                                        'props': {
                                            'multiple': True,
                                            'chips': True,
                                            'model': 'msgtypes',
                                            'label': '消息类型',
                                            'items': msg_type_options
                                        }
                                    }
                                ]
                            }
                        ]
                    },
                ]
            }
        ], {
            "enabled": False,
            'webhookurl': '',
            'msgtypes': default_msg_type_values,
            'secret': '',
        }
    
    def get_page(self) -> List[dict]:

        
        return []
        
    def get_service(self)-> List[Dict[str, Any]]:
        """
        注册插件公共服务
        [{
            "id": "服务ID",
            "name": "服务名称",
            "trigger": "触发器：cron/interval/date/CronTrigger.from_crontab()",
            "func": self.xxx,
            "kwargs": {} # 定时器参数
        }]
        """
        pass

    def get_dashboard(self, key: str, **kwargs) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], List[dict]]]:
        return None
    
    
    def stop_service(self):
        """
        停止插件服务
        """
        pass
    

    @eventmanager.register(EventType.DownloadAdded)
    def download_add(self, event: Event):
        """
        同步种子
        """
        logger.info("download add", event)
        
    @eventmanager.register(EventType.DownloadDeleted)
    def download_delete(self, event: Event):
        """
        同步种子
        """
        logger.info("download delete", event)
    
    @eventmanager.register(EventType.SubscribeAdded)
    def subscribe_add(self, event: Event):
        """
        同步种子
        """
        logger.info("subscribe add", event)
    
    @eventmanager.register(EventType.SubscribeDeleted)
    def subscribe_delete(self, event: Event):
        """
        同步种子
        """
        logger.info("subscribe delete", event)

