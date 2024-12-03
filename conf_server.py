import asyncio
import uuid

from util import *

class ConferenceServer:
    def __init__(self, conference_id, conf_serve_ports):
        self.conference_id = conference_id
        self.conf_serve_ports = conf_serve_ports
        self.data_serve_ports = {'screen': conf_serve_ports + 1,
                                 'camera': conf_serve_ports + 2,
                                 'audio' : conf_serve_ports + 3}
        self.data_types = ['screen', 'camera', 'audio']
        self.clients_info = []
        self.client_conns = {}
        self.mode = 'Client-Server'

    async def handle_data(self, reader, writer, data_type):
        """
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """

    async def handle_client(self, client_id):
        """
        running task: handle the in-meeting requests or messages from clients
        """
        if client_id in self.clients_info:
            self.clients_info.append(client_id)
            self.client_conns = {}

        else:
            self.clients_info.remove(client_id)

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
        conf_serve_ports = 8888 + len(self.conference_servers) * 4
        conference_server = ConferenceServer(conference_id, conf_serve_ports)

        self.conference_servers[conference_id] = conference_server
        asyncio.create_task(conference_server.start())
        message = conference_id + " " + str(conf_serve_ports)
        return message

    def handle_join_conference(self, conference_id, client_id):
        """
        join conference: search corresponding conference_info and ConferenceServer, and reply necessary info to client
        """
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.handle_client(client_id)
            message = "Client joined"
        else:
            message = "Conference not found"
        return message

    def handle_quit_conference(self, conference_id, client_id):
        """
        quit conference (in-meeting request & or no need to request)
        """
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.handle_client(client_id)
            message = "Client removed"
        else:
            message = "Conference not found"
        return message

    def handle_cancel_conference(self, conference_id):
        """
        cancel conference (in-meeting request, a ConferenceServer should be closed by the MainServer)
        """
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.cancel_conference()
            del self.conference_servers[conference_id]
            message = "Conference cancelled"
        else:
            message = "Conference not found"
        return message

    async def request_handler(self, reader, writer):
        """
        running task: handle out-meeting (or also in-meeting) requests from clients
        """
        data = await reader.read(1024)
        message = data.decode()
        addr = writer.get_extra_info('peername')

        client_id = f"{addr[0]}:{addr[1]}"

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

        writer.write(response)
        await writer.drain()
        writer.close()

    async def start(self):
        self.main_server = await asyncio.start_server(self.request_handler, self.server_ip, self.server_port)
        await self.main_server.serve_forever()


if __name__ == '__main__':
    server = MainServer("127.0.0.1", 8000)
    asyncio.run(server.start())