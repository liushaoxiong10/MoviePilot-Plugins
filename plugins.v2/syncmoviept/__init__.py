from ast import Subscript
from asyncio.windows_events import NULL
import ipaddress
from typing import List, Tuple, Dict, Any, Optional

from app.core.event import eventmanager, Event
from app.helper.downloader import DownloaderHelper
from app.helper.mediaserver import MediaServerHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType, WebhookEventInfo, ServiceInfo
from app.schemas.types import EventType
from app.utils.ip import IpUtils
from app.helper.downloader import DownloaderHelper
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.subscribe_oper import SubscribeOper


class SyncMoviePT(_PluginBase):
    # 插件名称
    plugin_name = "SyncMoviePT"
    # 插件描述
    plugin_desc = "SyncMoviePT 是一个用于同步订阅，管理种子。"
    # 插件图标
    plugin_icon = "SyncMoviePT_A.png"
    # 插件版本
    plugin_version = "0.1"
    # 插件作者
    plugin_author = "K0ala"
    # 作者主页
    author_url = ""
    
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
    
    def get_command(self) -> List[Dict[str, Any]]:
        """
        指令格式:
        - syncmoviept
        """
        return [
        ]
    def get_api(self) -> List[Dict[str, Any]]:
        """
        插件API
        """
        return [
            {
                "path": "/syncmoviept",
                "endpoint": self.syncmoviept,
                "methods": ["GET"],
                "summary": "SyncMoviePT 是一个用于同步订阅，管理种子。",
                "description": "SyncMoviePT 是一个用于同步订阅，管理种子。",
            }
        ]
        
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
        return [], {}
    
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

