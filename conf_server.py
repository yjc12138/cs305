import asyncio
import uuid
import socket

from util import *

class ConferenceServer:
    def __init__(self, conference_id, server_ip, conf_serve_port):
        self.conference_id = conference_id
        self.server_ip = server_ip
        self.conf_server_port = conf_serve_port
        screen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        screen_socket.bind((server_ip, conf_serve_port + 1))
        camera_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        camera_socket.bind((server_ip, conf_serve_port + 2))
        audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        audio_socket.bind((server_ip, conf_serve_port + 3))
        self.data_servers = {'screen': screen_socket, 'camera': camera_socket, 'audio': audio_socket}
        self.data_types = ['screen', 'camera', 'audio']
        self.clients_info = []
        self.client_conns = {}
        self.mode = 'Client-Server'
        self.running = False

    async def handle_data(self, data_type):
        """
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """
        while self.running:
            data_server = self.data_servers[data_type]
            if data_type == 'screen':
                data_port = CLIENT_SCREEN_PORT
            elif data_type == 'camera':
                data_port = CLIENT_CAMERA_PORT
            else:
                data_port = CLIENT_AUDIO_PORT
            data, addr = await data_server.recvfrom(1024)
            for client_ip in self.clients_info:
                await data_server.sendto(data, (client_ip, data_port))

    async def handle_text(self, reader, writer):
        while self.running:
            data = await reader.read(1024)
            if data:
                for client_conn in self.client_conns:
                    if client_conn != writer:
                        client_conn.write(data)
                        await client_conn.drain()

    def handle_client(self, client_id):
        """
        conference_id: str ip

        running task: handle the in-meeting requests or messages from clients
        """
        while self.running:
            if client_id in self.clients_info:
                self.clients_info.remove(client_id)
                self.client_conns.pop(client_id)
            else:
                try:
                    control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    control_socket.connect(client_id)
                    self.client_conns[client_id] = control_socket
                except socket.error as e:
                    print(f'socket error: {e}')
                    return
                self.clients_info.append(client_id)


    async def log(self):
        while self.running:
            print('Server alive')
            await asyncio.sleep(LOG_INTERVAL)

    async def cancel_conference(self):
        """
        handle cancel conference request: disconnect all connections to cancel the conference
        """
        if self.running:
            self.client_conns.clear()
            self.clients_info.clear()
            self.running = False

    def start(self):
        '''
        start the ConferenceServer and necessary running tasks to handle clients in this conference
        '''
        self.running = True
        loop = asyncio.get_event_loop()
        tasks = [loop.create_task(self.handle_data('screen')),
                 loop.create_task(self.handle_data('camera')),
                 loop.create_task(self.handle_data('audio')),
                 loop.create_task(asyncio.start_server(self.handle_text, self.server_ip, self.conf_server_port)),]
        try:
            loop.run_until_complete(asyncio.gather(*tasks))
        finally:
            loop.close()


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

        if message.startswith("create"):
            print(f"{client_id}: create conference")
            response = self.handle_create_conference()
        elif message.startswith("join"):
            conference_id = message.split()[1]
            print(f"{client_id}: join conference {conference_id}")
            response = self.handle_join_conference(conference_id, client_id)
        elif message.startswith("quit"):
            conference_id = message.split()[1]
            print(f"{client_id}: quit conference {conference_id}")
            response = self.handle_quit_conference(conference_id, client_id)
        elif message.startswith("cancel"):
            conference_id = message.split()[1]
            print(f"{client_id}: cancel conference {conference_id}")
            response = self.handle_cancel_conference(conference_id)
        else:
            print("wrong command")
            response = "wrong message"

        writer.write(response)
        await writer.drain()
        writer.close()

    async def start(self):
        print(f"Starting server at {self.server_ip}:{self.server_port}")
        self.main_server = await asyncio.start_server(self.request_handler, self.server_ip, self.server_port)
        print(f"Server started, listening on {self.server_ip}:{self.server_port}")
        await self.main_server.serve_forever()


if __name__ == '__main__':
    server = MainServer("127.0.0.1", 8000)
    asyncio.run(server.start())
