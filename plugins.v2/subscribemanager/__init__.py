import re
import threading
import time
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional

import pytz

from app.core.config import settings
from app.helper.downloader import DownloaderHelper
from app.log import logger
from app.plugins import _PluginBase
from app.schemas import NotificationType, ServiceInfo
from app.utils.string import StringUtils
from app.db.downloadhistory_oper import DownloadHistoryOper
from app.db.subscribe_oper import SubscribeOper

lock = threading.Lock()


class SubscribeManager(_PluginBase):
    # 插件名称
    plugin_name = "订阅管理"
    # 插件描述
    plugin_desc = "管理已订阅内容和PT种子。"
    # 插件图标
    plugin_icon = "Moviepilot_A.png"
    # 插件版本
    plugin_version = "0.4"
    # 插件作者
    plugin_author = "k0ala"
    # 作者主页
    author_url = "https://github.com/liushaoxiong10"
    # 插件配置项ID前缀
    plugin_config_prefix = "subscribemanager_"
    # 加载顺序
    plugin_order = 8
    # 可使用的用户级别
    auth_level = 1

    # 私有属性
    downloader_helper = None
    _event = threading.Event()
    _scheduler = None
    _enabled = False
    _onlyonce = False
    _notify = False
    # pause/delete
    _downloaders = []
    _action = "pause"
    _cron = None
    _samedata = False
    _mponly = False
    _size = None
    _ratio = None
    _time = None
    _upspeed = None
    _labels = None
    _pathkeywords = None
    _trackerkeywords = None
    _errorkeywords = None
    _torrentstates = None
    _torrentcategorys = None

    def init_plugin(self, config: dict = None):
        self.downloader_helper = DownloaderHelper()
        if config:
            self._enabled = config.get("enabled")
            self._onlyonce = config.get("onlyonce")
            self._notify = config.get("notify")
            self._downloaders = config.get("downloaders") or []
            self._action = config.get("action")
            self._cron = config.get("cron")
            self._samedata = config.get("samedata")
            self._mponly = config.get("mponly")
            self._size = config.get("size") or ""
            self._ratio = config.get("ratio")
            self._time = config.get("time")
            self._upspeed = config.get("upspeed")
            self._labels = config.get("labels") or ""
            self._pathkeywords = config.get("pathkeywords") or ""
            self._trackerkeywords = config.get("trackerkeywords") or ""
            self._errorkeywords = config.get("errorkeywords") or ""
            self._torrentstates = config.get("torrentstates") or ""
            self._torrentcategorys = config.get("torrentcategorys") or ""

        self.stop_service()

    def get_state(self) -> bool:
        return True if self._enabled else False

    @staticmethod
    def get_command() -> List[Dict[str, Any]]:
        pass

    def get_api(self) -> List[Dict[str, Any]]:
        pass

    def get_service(self) -> List[Dict[str, Any]]:
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
        return []

    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
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
                            },
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
                                            'model': 'notify',
                                            'label': '发送通知',
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
            "notify": False,
        }

    def get_page(self) -> List[dict]:
        subs = SubscribeOper().list()
        items = []
        for sub in subs:
            items.append({
                'component': 'tr',
                'content': [
                    {
                        'component': 'td',
                        'text': sub.name
                    },
                    {
                        'component': 'td', 
                        'text': sub.type
                    },
                    {
                        'component': 'td',
                        'text': sub.state
                    },
                    {
                        'component': 'td',
                        'content': [
                            {
                                'component': 'VBtn',
                                'props': {
                                    'size': 'small',
                                    'color': 'error',
                                    'onClick': {
                                        'action': 'delete',
                                        'url': '/api/v1/subscribe/delete',
                                        'params': {
                                            'id': sub.id
                                        }
                                    }
                                },
                                'content': [
                                    {
                                        'component': 'VIcon',
                                        'props': {
                                            'size': 'small'
                                        },
                                        'content': 'mdi-delete'
                                    }
                                ]
                            }
                        ]
                    }
                ]
            })

        return [
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
                                'component': 'VTable',
                                'props': {
                                    'hover': True
                                },
                                'content': [
                                    {
                                        'component': 'thead',
                                        'content': [
                                            {
                                                'component': 'tr',
                                                'content': [
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '订阅名称'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '类型'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '状态'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '操作'
                                                    }
                                                ]
                                            }
                                        ]
                                    },
                                    {
                                        'component': 'tbody',
                                        'content': items
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        # subs = SubscribeOper().list()
        # items = []
        # for sub in subs:
        #     items.append({
        #         "id": sub.id,
        #         "name": sub.name,
        #         "state": sub.state,
        #         "actions": [{
        #             'component': 'VBtn',
        #             'props': {
        #                'size': 'small',
        #                'color': 'error',                                 'onClick': {
        #                     'action': 'delete',
        #                     'url': '/api/v1/subscribe/delete',
        #                     'params': {
        #                     'id': sub.id,
        #                     }
        #                 }
        #             }
        #         }]
        #     })


        
        # return [
        #     {
        #         'component': 'VRow',
        #         "content": [
        #             {
        #                 'component': 'VCol',
        #                 'props': {
        #                     'cols': 12,
        #                 },
        #                 'content': [
        #                      {
        #                         'component': 'VDataTable',
        #                         'props': {
        #                             'headers': [
        #                                 {'title': '订阅名称', 'key': 'name'},
        #                                 {'title': '类型', 'key': 'type'},
        #                                 {'title': '状态', 'key': 'state'},
        #                                 {'title': '操作', 'key': 'actions'}
        #                             ],
        #                             'items': items,
        #                             'items-per-page-options': 10
        #                         },
        #                     }
        #                 ]
        #             }
        #         ]
        #     }
        # ]

  
    @staticmethod
    def get_api(self) -> List[Dict[str, Any]]:
        """
        注册API
        """
        return [
            {
                "path": "/api/v1/history/list",
                "endpoint": self.list_history,
                "methods": ["GET"],
                "summary": "查询下载历史记录",
                "description": "分页查询下载历史记录列表"
            },
            {
                "path": "/api/v1/history/delete", 
                "endpoint": self.delete_history,
                "methods": ["DELETE"],
                "summary": "删除下载历史记录",
                "description": "根据ID删除指定的下载历史记录"
            },
            {
                "path": "/api/v1/subscribe/list",
                "endpoint": self.list_subscribe,
                "methods": ["GET"],
                "summary": "查询订阅列表",
                "description": "分页查询订阅列表"
            }
        ]

    @staticmethod   
    def list_subscribe(request):
        """
        查询订阅列表
        """
        page = request.query.get("page") or 1
        size = request.query.get("size") or 10
        
        # 调用订阅查询接口
        subscribe_list = SubscribeOper().list(page=int(page), size=int(size))
        return {
            "code": 0,
            "items": subscribe_list,
            "total": len(subscribe_list)
        }

    @staticmethod
    def list_history(request):
        """
        查询下载历史记录
        """
        page = request.query.get("page") or 1
        size = request.query.get("size") or 10
        
        # 调用下载历史记录查询接口
        history_list = DownloadHistoryOper().list(page=int(page), size=int(size))
        
        # 组装返回数据
        items = []
        for history in history_list:
            items.append({
                "id": history.id,
                "title": history.title,
                "downloader": history.downloader,
                "path": history.path,
                "state": history.state
            })
            
        return {
            "code": 0,
            "items": items,
            "total": len(items)
        }

    @staticmethod
    def delete_history(request):
        """
        删除下载历史记录
        """
        history_id = request.query.get("id")
        if not history_id:
            return {"code": 1, "msg": "未指定要删除的记录"}
            
        # 调用下载历史记录删除接口
        DownloadHistoryOper().delete(history_id)
        
        return {"code": 0}

    def stop_service(self):
        """
        退出插件
        """
        pass

    @property
    def service_infos(self) -> Optional[Dict[str, ServiceInfo]]:
        """
        服务信息
        """
        if not self._downloaders:
            logger.warning("尚未配置下载器，请检查配置")
            return None

        services = self.downloader_helper.get_services(name_filters=self._downloaders)
        if not services:
            logger.warning("获取下载器实例失败，请检查配置")
            return None

        active_services = {}
        for service_name, service_info in services.items():
            if service_info.instance.is_inactive():
                logger.warning(f"下载器 {service_name} 未连接，请检查配置")
            else:
                active_services[service_name] = service_info

        if not active_services:
            logger.warning("没有已连接的下载器，请检查配置")
            return None

        return active_services

    def __get_downloader(self, name: str):
        """
        根据类型返回下载器实例
        """
        return self.service_infos.get(name).instance

    def __get_downloader_config(self, name: str):
        """
        根据类型返回下载器实例配置
        """
        return self.service_infos.get(name).config

    def delete_torrents(self):
        """
        定时删除下载器中的下载任务
        """
        for downloader in self._downloaders:
            try:
                with lock:
                    # 获取需删除种子列表
                    torrents = self.get_remove_torrents(downloader)
                    logger.info(f"自动删种任务 获取符合处理条件种子数 {len(torrents)}")
                    # 下载器
                    downlader_obj = self.__get_downloader(downloader)
                    if self._action == "pause":
                        message_text = f"{downloader.title()} 共暂停{len(torrents)}个种子"
                        for torrent in torrents:
                            if self._event.is_set():
                                logger.info(f"自动删种服务停止")
                                return
                            text_item = f"{torrent.get('name')} " \
                                        f"来自站点：{torrent.get('site')} " \
                                        f"大小：{StringUtils.str_filesize(torrent.get('size'))}"
                            # 暂停种子
                            downlader_obj.stop_torrents(ids=[torrent.get("id")])
                            logger.info(f"自动删种任务 暂停种子：{text_item}")
                            message_text = f"{message_text}\n{text_item}"
                    elif self._action == "delete":
                        message_text = f"{downloader.title()} 共删除{len(torrents)}个种子"
                        for torrent in torrents:
                            if self._event.is_set():
                                logger.info(f"自动删种服务停止")
                                return
                            text_item = f"{torrent.get('name')} " \
                                        f"来自站点：{torrent.get('site')} " \
                                        f"大小：{StringUtils.str_filesize(torrent.get('size'))}"
                            # 删除种子
                            downlader_obj.delete_torrents(delete_file=False,
                                                          ids=[torrent.get("id")])
                            logger.info(f"自动删种任务 删除种子：{text_item}")
                            message_text = f"{message_text}\n{text_item}"
                    elif self._action == "deletefile":
                        message_text = f"{downloader.title()} 共删除{len(torrents)}个种子及文件"
                        for torrent in torrents:
                            if self._event.is_set():
                                logger.info(f"自动删种服务停止")
                                return
                            text_item = f"{torrent.get('name')} " \
                                        f"来自站点：{torrent.get('site')} " \
                                        f"大小：{StringUtils.str_filesize(torrent.get('size'))}"
                            # 删除种子
                            downlader_obj.delete_torrents(delete_file=True,
                                                          ids=[torrent.get("id")])
                            logger.info(f"自动删种任务 删除种子及文件：{text_item}")
                            message_text = f"{message_text}\n{text_item}"
                    else:
                        continue
                    if torrents and message_text and self._notify:
                        self.post_message(
                            mtype=NotificationType.SiteMessage,
                            title=f"【自动删种任务完成】",
                            text=message_text
                        )
            except Exception as e:
                logger.error(f"自动删种任务异常：{str(e)}")

    def __get_qb_torrent(self, torrent: Any) -> Optional[dict]:
        """
        检查QB下载任务是否符合条件
        """
        # 完成时间
        date_done = torrent.completion_on if torrent.completion_on > 0 else torrent.added_on
        # 现在时间
        date_now = int(time.mktime(datetime.now().timetuple()))
        # 做种时间
        torrent_seeding_time = date_now - date_done if date_done else 0
        # 平均上传速度
        torrent_upload_avs = torrent.uploaded / torrent_seeding_time if torrent_seeding_time else 0
        # 大小 单位：GB
        sizes = self._size.split('-') if self._size else []
        minsize = float(sizes[0]) * 1024 * 1024 * 1024 if sizes else 0
        maxsize = float(sizes[-1]) * 1024 * 1024 * 1024 if sizes else 0
        # 分享率
        if self._ratio and torrent.ratio <= float(self._ratio):
            return None
        # 做种时间 单位：小时
        if self._time and torrent_seeding_time <= float(self._time) * 3600:
            return None
        # 文件大小
        if self._size and (torrent.size >= int(maxsize) or torrent.size <= int(minsize)):
            return None
        if self._upspeed and torrent_upload_avs >= float(self._upspeed) * 1024:
            return None
        if self._pathkeywords and not re.findall(self._pathkeywords, torrent.save_path, re.I):
            return None
        if self._trackerkeywords and not re.findall(self._trackerkeywords, torrent.tracker, re.I):
            return None
        if self._torrentstates and torrent.state not in self._torrentstates:
            return None
        if self._torrentcategorys and (not torrent.category or torrent.category not in self._torrentcategorys):
            return None
        return {
            "id": torrent.hash,
            "name": torrent.name,
            "site": StringUtils.get_url_sld(torrent.tracker),
            "size": torrent.size
        }

    def __get_tr_torrent(self, torrent: Any) -> Optional[dict]:
        """
        检查TR下载任务是否符合条件
        """
        # 完成时间
        date_done = torrent.date_done or torrent.date_added
        # 现在时间
        date_now = int(time.mktime(datetime.now().timetuple()))
        # 做种时间
        torrent_seeding_time = date_now - int(time.mktime(date_done.timetuple())) if date_done else 0
        # 上传量
        torrent_uploaded = torrent.ratio * torrent.total_size
        # 平均上传速茺
        torrent_upload_avs = torrent_uploaded / torrent_seeding_time if torrent_seeding_time else 0
        # 大小 单位：GB
        sizes = self._size.split('-') if self._size else []
        minsize = float(sizes[0]) * 1024 * 1024 * 1024 if sizes else 0
        maxsize = float(sizes[-1]) * 1024 * 1024 * 1024 if sizes else 0
        # 分享率
        if self._ratio and torrent.ratio <= float(self._ratio):
            return None
        if self._time and torrent_seeding_time <= float(self._time) * 3600:
            return None
        if self._size and (torrent.total_size >= int(maxsize) or torrent.total_size <= int(minsize)):
            return None
        if self._upspeed and torrent_upload_avs >= float(self._upspeed) * 1024:
            return None
        if self._pathkeywords and not re.findall(self._pathkeywords, torrent.download_dir, re.I):
            return None
        if self._trackerkeywords:
            if not torrent.trackers:
                return None
            else:
                tacker_key_flag = False
                for tracker in torrent.trackers:
                    if re.findall(self._trackerkeywords, tracker.get("announce", ""), re.I):
                        tacker_key_flag = True
                        break
                if not tacker_key_flag:
                    return None
        if self._errorkeywords and not re.findall(self._errorkeywords, torrent.error_string, re.I):
            return None
        return {
            "id": torrent.hashString,
            "name": torrent.name,
            "site": torrent.trackers[0].get("sitename") if torrent.trackers else "",
            "size": torrent.total_size
        }

    def get_remove_torrents(self, downloader: str):
        """
        获取自动删种任务种子
        """
        remove_torrents = []
        # 下载器对象
        downloader_obj = self.__get_downloader(downloader)
        downloader_config = self.__get_downloader_config(downloader)
        # 标题
        if self._labels:
            tags = self._labels.split(',')
        else:
            tags = []
        if self._mponly:
            tags.append(settings.TORRENT_TAG)
        # 查询种子
        torrents, error_flag = downloader_obj.get_torrents(tags=tags or None)
        if error_flag:
            return []
        # 处理种子
        for torrent in torrents:
            if downloader_config.type == "qbittorrent":
                item = self.__get_qb_torrent(torrent)
            else:
                item = self.__get_tr_torrent(torrent)
            if not item:
                continue
            remove_torrents.append(item)
        # 处理辅种
        if self._samedata and remove_torrents:
            remove_ids = [t.get("id") for t in remove_torrents]
            remove_torrents_plus = []
            for remove_torrent in remove_torrents:
                name = remove_torrent.get("name")
                size = remove_torrent.get("size")
                for torrent in torrents:
                    if downloader_config.type == "qbittorrent":
                        plus_id = torrent.hash
                        plus_name = torrent.name
                        plus_size = torrent.size
                        plus_site = StringUtils.get_url_sld(torrent.tracker)
                    else:
                        plus_id = torrent.hashString
                        plus_name = torrent.name
                        plus_size = torrent.total_size
                        plus_site = torrent.trackers[0].get("sitename") if torrent.trackers else ""
                    # 比对名称和大小
                    if plus_name == name \
                            and plus_size == size \
                            and plus_id not in remove_ids:
                        remove_torrents_plus.append(
                            {
                                "id": plus_id,
                                "name": plus_name,
                                "site": plus_site,
                                "size": plus_size
                            }
                        )
            if remove_torrents_plus:
                remove_torrents.extend(remove_torrents_plus)
        return remove_torrents
