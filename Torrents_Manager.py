import asyncio
import socket
from typing import List, Any
import logging

import torf
import Parallel_Download_Manager

torrents_list: list[Parallel_Download_Manager.DownloadManager] = list()  # list of DownloadManager objects


async def __start():
    host = socket.gethostname()
    listener = await asyncio.start_server(__client_connected_cb, host, 6881)
    async with listener:
        await listener.serve_forever()


async def __client_connected_cb(reader, writer):
    len_protocol_str = int.from_bytes((await reader.read(1)), "big")
    protocol_str = (await reader.read(len_protocol_str)).decode()
    await reader.read(8)
    peer_info_hash = (await reader.read(20))
    recv_peer_id = (await reader.read(20)).decode()
    if protocol_str == "BitTorrent protocol":
        for torrent in torrents_list:
            if bytes.fromhex(torrent.meta_info.infohash) == peer_info_hash:
                logging.debug(f"{torrent.downloader_id} has accepted the handshake")
                await torrent.add_peer(reader, writer)
                return
    writer.close()
    await writer.wait_closed()
    asyncio.current_task().cancel()


async def create_new_torrent(torrent_path, path, peer_info_list, downloader_id):
    torrents_list.append((await Parallel_Download_Manager.DownloadManager(torrent_path, path, peer_info_list, downloader_id)))
