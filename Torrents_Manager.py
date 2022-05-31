import asyncio
import socket
from typing import List, Any
import logging
import torf
import Parallel_Download_Manager
from requests import get

torrents_list: list[Parallel_Download_Manager.DownloadManager] = list()  # list of DownloadManager objects
ip = socket.gethostname()


async def __start():
    listener = await asyncio.start_server(__client_connected_cb, ip, 6881)
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
                logging.debug(f"{torrent.client_id} has accepted the handshake")
                await torrent.add_peer(reader, writer, recv_peer_id)
                return
    writer.close()
    await writer.wait_closed()
    asyncio.current_task().cancel()


async def create_new_torrent(client_id, torrent_path, path):
    download_manager = await asyncio.create_task(Parallel_Download_Manager.DownloadManager(client_id, path, torrent_path))
    torrents_list.append(download_manager)
    return download_manager
