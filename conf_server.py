import asyncio
import threading
import uuid
import socket

from util import *

class ConferenceServer:
    def __init__(self, conference_id, server_ip, conf_server_port):
        self.conference_id = conference_id
        self.server_ip = server_ip
        self.conf_server_port = conf_server_port
        # text_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # text_socket.bind((server_ip, conf_serve_port))
        # text_socket.listen(10)
        # text_socket.setblocking(False)
        screen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        screen_socket.bind((server_ip, conf_server_port + 1))
        screen_socket.setblocking(False)
        camera_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        camera_socket.bind((server_ip, conf_server_port + 2))
        camera_socket.setblocking(False)
        audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        audio_socket.bind((server_ip, conf_server_port + 3))
        audio_socket.setblocking(False)
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
        print(f'handle {data_type} data')
        while self.running:
            data_server = self.data_servers[data_type]
            try:
                data, addr = await data_server.recvfrom(1024)
                for client_ip in self.clients_info:
                    client_addr = client_ip.split(':')
                    if client_addr != addr:
                        await data_server.sendto(data, client_addr)
            except BlockingIOError as e:
                pass

    async def handle_text(self, reader, writer):
        while self.running:
            try:
                data = await reader.read(1024)
                addr = writer.get_extra_info('peername')
                client_id = f"{addr[0]}:{addr[1]}"
                if client_id in self.clients_info:
                    self.client_conns[client_id] = writer
                if data:
                    for client_conn in self.client_conns:
                        # if client_conn != writer:
                        client_conn.write(data)
                        await client_conn.drain()
            except BlockingIOError as e:
                pass

    def handle_client(self, client_id):
        """
        running task: handle the in-meeting requests or messages from clients
        """
        if self.running:
            if client_id in self.clients_info:
                self.clients_info.remove(client_id)
                self.client_conns[client_id].close()
                self.client_conns.pop(client_id)
            else:
                self.clients_info.append(client_id)
                print(f'{client_id} has joined')

    async def log(self):
        while self.running:
            print('Server alive')
            await asyncio.sleep(LOG_INTERVAL)

    async def cancel_conference(self):
        """
        handle cancel conference request: disconnect all connections to cancel the conference
        """
        if self.running:
            for client_conn in self.client_conns:
                client_conn.close()
            self.client_conns.clear()
            self.clients_info.clear()
            self.running = False

    def start(self):
        '''
        start the ConferenceServer and necessary running tasks to handle clients in this conference
        '''
        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        async def event_loop():
            print('event loop')
            text_server = await asyncio.start_server(self.handle_text, self.server_ip, self.conf_server_port)
            print('event loop running')
            await text_server.serve_forever()
            print('event loop done')

        self.running = True
        try:
            loop1 = asyncio.new_event_loop()
            t1 = threading.Thread(target=start_loop, args=(loop1,))
            t1.start()
            asyncio.run_coroutine_threadsafe(self.handle_data(self.data_types[0]), loop1)

            loop2 = asyncio.new_event_loop()
            t2 = threading.Thread(target=start_loop, args=(loop2,))
            t2.start()
            asyncio.run_coroutine_threadsafe(self.handle_data(self.data_types[1]), loop2)

            loop3 = asyncio.new_event_loop()
            t3 = threading.Thread(target=start_loop, args=(loop3,))
            t3.start()
            asyncio.run_coroutine_threadsafe(self.handle_data(self.data_types[2]), loop3)

            loop4 = asyncio.new_event_loop()
            t4 = threading.Thread(target=start_loop, args=(loop4,))
            t4.start()
            asyncio.run_coroutine_threadsafe(event_loop(), loop4)
            print(f'conference server running on port {self.conf_server_port}')
        except Exception as e:
            print(e)


class MainServer:
    def __init__(self, server_ip, main_port):
        # async server
        self.server_ip = server_ip
        self.server_port = main_port
        self.main_server = None

        self.conference_conns = None
        self.conference_servers = {}

    def handle_create_conference(self, client_id):
        """
        create conference: create and start the corresponding ConferenceServer, and reply necessary info to client
        """
        conference_id = str(uuid.uuid4())
        conf_serve_ports = 8888 + len(self.conference_servers) * 4
        conference_server = ConferenceServer(conference_id, self.server_ip, conf_serve_ports)

        self.conference_servers[conference_id] = conference_server
        conference_server.start()
        print('started')
        conference_server.handle_client(client_id)
        message = conference_id + " " + str(conf_serve_ports)
        return message

    def handle_join_conference(self, conference_id, client_id):
        """
        join conference: search corresponding conference_info and ConferenceServer, and reply necessary info to client
        """
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.handle_client(client_id)
            message = f"{conference_server.conf_server_port}:Client joined"
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
            if len(conference_server.clients_info) == 0:
                conference_server.cancel_conference()
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
        print(111)
        data = await reader.read(1024)
        print(222)
        message = data.decode()
        addr = writer.get_extra_info('peername')

        client_id = f"{addr[0]}:{addr[1]}"

        if message.startswith("create"):
            print(f"{client_id}: create conference")
            response = self.handle_create_conference(client_id)
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

        print(response)
        writer.write(response.encode())
        await writer.drain()
        writer.close()

    async def start(self):
        print(f"Starting server at {self.server_ip}:{self.server_port}")
        self.main_server = await asyncio.start_server(self.request_handler, self.server_ip, self.server_port)
        print(f"Server started, listening on {self.server_ip}:{self.server_port}")
        await self.main_server.serve_forever()


if __name__ == '__main__':
    server = MainServer(SERVER_IP, MAIN_SERVER_PORT)
    asyncio.run(server.start())