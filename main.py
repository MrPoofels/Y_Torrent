import asyncio
import torf
from torf import Torrent
from torf import Magnet
import Torrents_Manager
import socket
import _sha1
import logging
import collections
import bencodepy
from bitstring import BitArray


async def main():
    # t = torf.Torrent.read("C:\\Users\\Yahav\\PycharmProjects\\Y_Torrent\\Test_files\\archvalemeleeonly1.torrent")
    # magnet = Magnet.from_string('magnet:?xt=urn:btih:A7B3BED8FA0F9BC4272321807033F56D1ED4EB61&dn=Avatar%20-%20The%20Last%20Airbender%20-%20The%20Promise%201-3%20(2012)%20(Son%20of%20Ult&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969%2Fannounce&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A6969%2Fannounce&tr=udp%3A%2F%2F9.rarbg.to%3A2710%2Fannounce&tr=udp%3A%2F%2F9.rarbg.me%3A2780%2Fannounce&tr=udp%3A%2F%2F9.rarbg.to%3A2730%2Fannounce&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337&tr=http%3A%2F%2Fp4p.arenabg.com%3A1337%2Fannounce&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=udp%3A%2F%2Ftracker.tiny-vps.com%3A6969%2Fannounce&tr=udp%3A%2F%2Fopen.stealth.si%3A80%2Fannounce')
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
