from typing import Iterable

import bencodepy
import asyncio
import Parallel_Download_Manager as PMD
import torf


@PMD.Async_init
class TrackerCommunication:
    async def __init__(self, announce, info_hash, peer_id, ip, download_manager):
        """

        Args:
            announce (torf._utils.URL):
        """
        print(announce[:-5])
        self.reader, self.writer = await asyncio.open_connection(announce, 80)
        self.announce = announce
        self.info_hash = info_hash
        self.peer_id = peer_id
        self.ip = ip
        self.download_manager = download_manager
        self.periodic_GET_task = None

    async def http_GET(self, uploaded, downloaded, left, event=None):
        message = self.announce + f"?info_hash={self.info_hash}&peer_id={self.peer_id}&port=6881&uploaded={uploaded}&downloaded={downloaded}&left={left}&compact=0"
        if event is not None:
            message += f"&event={event}"
        message += f"&ip={self.ip}"
        self.writer.write(message.encode())
        await self.writer.drain()

    async def periodic_GET(self, interval):
        while True:
            await asyncio.sleep(interval)
            await self.http_GET(self.download_manager.bytes_downloaded, self.download_manager.bytes_uploaded, self.download_manager.meta_info.size - self.download_manager.bytes_downloaded)
            await self.get_tracker_response()

    async def interpret_tracker_response(self):
        response_dict = (await self.get_tracker_response())
        interval = response_dict["interval"]
        peer_info_list = []
        for peer in response_dict["peers"]:
            peer_info_list.append((peer["peer_id"], peer["ip"], peer["port"]))
        return peer_info_list, interval


    async def get_tracker_response(self):
        data = (await self.reader.read(-1)).decode("utf-8")
        response_dict: dict = bencodepy.decode(data)
        return response_dict
