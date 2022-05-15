import asyncio
import socket
from typing import List, Any
import logging

from torf import Magnet
import Parallel_Download_Manager
import Parallel_Download_Manager as PDM
import tracker_communication

torrents_list: list[Parallel_Download_Manager.DownloadManager] = list()  # list of DownloadManager objects
host = socket.gethostname()


async def __start():
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
                logging.debug(f"{torrent.client_id} has accepted the handshake")
                await torrent.add_peer(reader, writer, recv_peer_id)
                return
    writer.close()
    await writer.wait_closed()
    asyncio.current_task().cancel()


async def create_new_torrent(client_id, torrent_path, path):
    task = Parallel_Download_Manager.DownloadManager(host, client_id, path, torrent_path)
    torrents_list.append(await task)


async def magnet_link_handler(magnet_link):
    magnet = Magnet.from_string(magnet_link)
    for tracker in magnet.tr:
        if tracker[:4] == 'http':
            chosen_tr = tracker
    tracker_connection = await tracker_communication.TrackerCommunication(chosen_tr, bytes.fromhex(magnet.infohash), 'test', host, None)
    await tracker_connection.http_GET(0, 0, event="started")
    peer_info_list, interval = await tracker_connection.interpret_tracker_response()