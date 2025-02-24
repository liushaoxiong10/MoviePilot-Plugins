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
from app.db.downloadhistory_oper import DownloadHistoryOper, DownloadHistory
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
    _titles = []
    _episodes = []

    # 弃用
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
            self._titles = config.get("titles") or []
            self._episodes = config.get("episodes") or []

        self.stop_service()
        self.clear_history(self._titles, self._episodes)
        config['titles'] = []
        config['episodes'] = []
        self.debug()

    def debug(self):
        downloader_obj = self.__get_downloader("qb")
        hashs = ["afa2efc0ade18bd41e1862eefe32f26b7b942cc0","829004616e1919c410120a53cc6fc2d04fa49c16"]
        torrents, error = downloader_obj.get_torrents(ids=hashs)
        if error:
            logger.error(f"获取QB种子失败: {error}")
        for t in torrents:
            logger.info(f"种子信息: {t}")
            hashs.remove(t.hash)
        for h in hashs:
            logger.info(f"种子 {h} 未找到")

    def clear_history(self, titles: List[str], episodes: List[str]):
        logger.info(f"清除下载历史记录：{titles} {episodes}")
        data = self.get_data()
        down_oper = DownloadHistoryOper()
        downloader_history ={}
        for d in data:
            if d.title in titles or d.id in episodes: 
                tmp = downloader_history.get(d.downloader)
                if not tmp:
                    tmp = []
                tmp.append(d)
                downloader_history[d.downloader] = tmp
                logger.info(f"清除下载历史记录：{d.id} {d.title} {d.seasons} {d.episodes} {d.download_hash}")
        for downloader, history in downloader_history.items():
            downloader_obj = self.__get_downloader(downloader)
            # 获取所有历史记录的hash值列表
            history_hashes = [h.download_hash for h in history]
            torrents, error = downloader_obj.get_torrents(ids=history_hashes)
            if error:
                logger.error(f"获取种子信息失败： {error}")
                continue
            for t in torrents:
                logger.info(f"种子信息: {t}")
                history_hashes.remove(t.hash)
            for h in history:
                # 判断当前历史记录的hash是否在未找到的hash列表中
                if h.download_hash in history_hashes:
                    logger.info(f"种子 {h.download_hash} 已不存在于下载器中")
                    self.delete_data(history=h)

    def delete_data(self, history: DownloadHistory):
        """
        从订阅记录中删除该信息
        """
        try:
            down_oper = DownloadHistoryOper()
            down_oper.delete_history(history.id)
            logger.info(f"删除下载历史记录：{history.id} {history.title} {history.seasons} {history.episodes} {history.download_hash}")
            return True
        except Exception as e:
            logger.error(f"删除下载历史记录失败：{str(e)}")
            return False


    
    def delete_download_history(self,history: DownloadHistory):
        downloader_name = history.downloader
        downloader_obj = self.__get_downloader(downloader_name)


            
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
        # 获取下载历史数据
        histories = self.get_data()
        
        # 构造标题和剧集列表
        titles = []
        episode_options = []
        
        for history in histories:
            # 标题列表
            if history.title not in titles:
                titles.append(history.title)
            
            # 剧集列表
            episode_str = history.title
            if history.seasons:
                episode_str += f" {history.seasons}"
            if history.episodes:
                episode_str += f" {history.episodes}"
            episode_options.append({"title": episode_str, "value": history.id})

                
        # 将列表转换为选择框选项格式
        title_options = [{"title": t, "value": t} for t in titles]

        # 标题和剧集选择框
        title_select = {
            'component': 'VRow',
            'content': [
                {
                    'component': 'VCol',
                    'props': {
                        'cols': 12,
                    },
                    'content': [
                        {
                            'component': 'VSelect',
                            'props': {
                                'model': 'titles',
                                'label': '标题',
                                'items': title_options,
                                'multiple': True,
                                'chips': True,
                                'clearable': True
                            }
                        }
                    ]
                }
            ]
        }
        
        episode_select = {
            'component': 'VRow', 
            'content': [
                {
                    'component': 'VCol',
                    'props': {
                        'cols': 12,
                    },
                    'content': [
                        {
                            'component': 'VSelect',
                            'props': {
                                'model': 'episodes',
                                'label': '剧集',
                                'items': episode_options,
                                'multiple': True,
                                'chips': True,
                                'clearable': True
                            }
                        }
                    ]
                }
            ]
        }
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
                    title_select,
                    episode_select
                 ]
            }
        ], {
            "enabled": False,
            "notify": False,
            "titles": [],
            "episodes": []
        }

    def get_data(self) -> List[DownloadHistory]:
        down_oper = DownloadHistoryOper() 
        downs = []
        page = 1
        while True:
            data = down_oper.list_by_page(page=page, count=100)
            downs.extend(data)
            if len(data) < 100:
                break
            page += 1
        return downs

    def get_page(self) -> List[dict]:
        items = []
        for down in self.get_data():
            items.append({
                'component': 'tr',
                'content': [
                    {
                        'component': 'td',
                        'text': down.id
                    },
                    {
                        'component': 'td',
                        'text': down.title
                    },
                    {
                        'component': 'td',
                        'text':down.seasons + " " + down.episodes
                    },
                    {
                        'component': 'td',
                        'text': down.torrent_name
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
                                                        'text': 'id'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '名称'
                                                    },
                                                      {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '剧集'
                                                    },
                                                    {
                                                        'component': 'th',
                                                        'props': {
                                                            'class': 'text-start ps-4'
                                                        },
                                                        'text': '种子名称'
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

  
    @staticmethod
    def get_api(self) -> List[Dict[str, Any]]:
        """
        注册API
        """
        pass
    
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
        services = self.downloader_helper.get_services(type_filter="qbittorrent")
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
