import asyncio
import torf
from torf import Torrent
import Torrents_Manager
import socket
import _sha1
import logging
import collections
import bencodepy


async def main():
    # t = torf.Torrent.read("C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\real_test\\big-buck-bunny.torrent")
    # print(t)
    print(socket.gethostname())
    logging.getLogger("asyncio").setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)
    task = asyncio.create_task(Torrents_Manager.__start())
    tpath1 = "C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\Test_files\\archvalemeleeonly1.torrent"
    path1 = "C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\Test_files\\archvalemeleeonly1.mp4"
    tpath2 = "C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\Test_files_2\\archvalemeleeonly2.torrent"
    path2 = "C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\Test_files_2\\archvalemeleeonly2.mp4"
    peer_info_list = [("Leecher1".ljust(20), socket.gethostname(), 6881)]
    await asyncio.sleep(1)
    task2 = asyncio.create_task(Torrents_Manager.create_new_torrent(torrent_path=tpath2, path=path2, peer_info_list=[], client_id="Leecher1".ljust(20)))
    task1 = asyncio.create_task(Torrents_Manager.create_new_torrent(torrent_path=tpath1, path=path1, peer_info_list=peer_info_list, client_id="Seeder".ljust(20)))
    await asyncio.gather(task2, task1)
    await asyncio.gather(*list(asyncio.all_tasks()))


asyncio.run(main(), debug=2)
