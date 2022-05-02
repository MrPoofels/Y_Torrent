import bencodepy
import asyncio
import Parallel_Download_Manager as PMD
import torf


@PMD.Async_init
class TrackerCommunication:
    async def __init__(self, announce, info_hash, peer_id, ip):
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
        self.interval = None

    async def http_GET(self, uploaded, downloaded, left, event=None):
        message = self.announce + f"?info_hash={self.info_hash}&peer_id={self.peer_id}&port=6881&uploaded={uploaded}&downloaded={downloaded}&left={left}"
        if event is not None:
            message += f"&event={event}"
        message += f"&ip={self.ip}"
        self.writer.write(message.encode())
        await self.writer.drain()

    async def tracker_response(self):
        data = await self.reader.read(-1)
        response_dict = bencodepy.decode(data)
        self.interval = response_dict["interval"]
        peer_info_list = []
        for peer in response_dict["peers"]:
            peer_info_list.append((peer["peer_id"], peer["ip"], peer["port"]))
        return peer_info_list
