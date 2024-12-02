import asyncio
import uuid

from util import *

class ConferenceServer:
    def __init__(self, conference_id):
        self.conference_id = conference_id
        self.conf_serve_ports = None
        self.data_serve_ports = {}
        self.data_types = ['screen', 'camera', 'audio']
        self.clients_info = []
        self.client_conns = None
        self.mode = 'Client-Server'

    async def handle_data(self, reader, writer, data_type):
        """
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """

    async def handle_client(self, reader, writer):
        """
        running task: handle the in-meeting requests or messages from clients
        """

    async def log(self):
        while self.running:
            print('Something about server status')
            await asyncio.sleep(LOG_INTERVAL)

    async def cancel_conference(self):
        """
        handle cancel conference request: disconnect all connections to cancel the conference
        """

    def start(self):
        '''
        start the ConferenceServer and necessary running tasks to handle clients in this conference
        '''


class MainServer:
    def __init__(self, server_ip, main_port):
        # async server
        self.server_ip = server_ip
        self.server_port = main_port
        self.main_server = None

        self.conference_conns = None
        self.conference_servers = {}

    def handle_create_conference(self):
        """
        create conference: create and start the corresponding ConferenceServer, and reply necessary info to client
        """
        conference_id = str(uuid.uuid4())
        conference_server = ConferenceServer(conference_id)
        self.conference_servers[conference_id] = conference_server
        asyncio.create_task(conference_server.start())
        return conference_id

    def handle_join_conference(self, conference_id, client_id):
        """
        join conference: search corresponding conference_info and ConferenceServer, and reply necessary info to client
        """
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.clients_info.append(client_id)
            return "Client joined"
        else: return "Conference not found"

    def handle_quit_conference(self, conference_id, client_id):
        """
        quit conference (in-meeting request & or no need to request)
        """
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.remove_client(client_id)
            return "Client removed"
        else: return "Conference not found"

    def handle_cancel_conference(self, conference_id):
        """
        cancel conference (in-meeting request, a ConferenceServer should be closed by the MainServer)
        """
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.cancel_conference()
            del self.conference_servers[conference_id]
            return "Conference cancelled"
        else: return "Conference not found"

    async def request_handler(self, reader, writer):
        """
        running task: handle out-meeting (or also in-meeting) requests from clients
        """
        data = await reader.read(1024)
        message = data.decode()
        addr = writer.get_extra_info('peername')

        client_id = f"{addr[0]}_{addr[1]}"

        if message.startswith("CREATE"):
            response = self.handle_create_conference()
        elif message.startswith("JOIN"):
            conference_id = message.split()[1]
            response = self.handle_join_conference(conference_id, client_id)
        elif message.startswith("QUIT"):
            conference_id = message.split()[1]
            response = self.handle_quit_conference(conference_id, client_id)
        elif message.startswith("CANCEL"):
            conference_id = message.split()[1]
            response = self.handle_cancel_conference(conference_id)
        else: response = "wrong message"

        writer.write(response.encode())
        await writer.drain()
        writer.close()

    def start(self):
        loop = asyncio.get_event_loop()
        self.main_server = loop.run_until_complete(
            asyncio.start_server(self.request_handler, self.server_ip, self.server_port)
        )
        loop.run_until_complete(self.main_server.serve_forever())


if __name__ == '__main__':
    server = MainServer("127.0.0.1", 8000)
    server.start()