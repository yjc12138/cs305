import threading
import uuid
import socket

from util import *

class ConferenceServer:
    def __init__(self, conference_id, server_ip, conf_server_port):
        self.conference_id = conference_id
        self.server_ip = server_ip
        self.conf_server_port = conf_server_port
        try:
            self.text_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.text_socket.bind((server_ip, conf_server_port))
            self.text_socket.listen(20)
            self.screen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.screen_socket.bind((server_ip, conf_server_port + 1))
            self.camera_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.camera_socket.bind((server_ip, conf_server_port + 2))
            self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_socket.bind((server_ip, conf_server_port + 3))
            self.text_socket = self.text_socket
            self.data_servers = {'screen': self.screen_socket, 'camera': self.camera_socket, 'audio': self.audio_socket}
        except Exception as e:
            print(f'conference socket error:{e}')
        self.data_types = ['screen', 'camera', 'audio']
        self.clients_info = []
        self.client_conns = {}
        self.mode = 'Client-Server'
        self.running = False

    def handle_data(self, data_type):
        """
        running task: receive sharing stream data from a client and decide how to forward them to the rest clients
        """
        while self.running:
            data_server = self.data_servers[self.data_types[data_type]]
            data, addr = data_server.recvfrom(BUFFER_SIZE)
            for client_ip in self.clients_info:
                client_addr = (client_ip.split(':')[0], int(client_ip.split(':')[1]) + data_type + 1)
                data_server.sendto(data, client_addr)

    def handle_text(self):
        def handle(conn, client_id):
            while self.running:
                try:
                    data = conn.recv(BUFFER_SIZE)
                    if client_id in self.clients_info:
                        self.client_conns[client_id] = conn
                    if data:
                        for client_conn in self.client_conns:
                            if client_conn != conn:
                                client_conn.send(data)
                except Exception as e:
                    break
        while True:
            new_client, client_address = self.text_socket.accept()
            client_id = f'{client_address[0]}:{client_address[1]}'
            print(f'{client_id} added into client_conns')
            self.client_conns[client_id] = new_client
            p = threading.Thread(target=handle, args=(new_client, client_id))
            p.start()

    def handle_client(self, client_id):
        """
        running task: handle the in-meeting requests or messages from clients
        """
        if self.running:
            if client_id in self.clients_info:
                self.clients_info.remove(client_id)
                print(self.client_conns)
                self.client_conns[client_id].close()
                self.client_conns.pop(client_id)
            else:
                self.clients_info.append(client_id)
                print(f'{client_id} has joined')

    def cancel_conference(self):
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
        self.running = True
        t1 = threading.Thread(target=self.handle_data, args=(0,))
        t1.start()
        t2 = threading.Thread(target=self.handle_data, args=(1,))
        t2.start()
        t3 = threading.Thread(target=self.handle_data, args=(2,))
        t3.start()
        t4 = threading.Thread(target=self.handle_text)
        t4.start()
        print(f'conference server running on port {self.conf_server_port}')


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
        conference_server = ConferenceServer(conference_id, self.server_ip, conf_serve_ports)

        self.conference_servers[conference_id] = conference_server
        conference_server.start()
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

    def request_handler(self, client_socket, client_address):
        """
        running task: handle out-meeting (or also in-meeting) requests from clients
        """

        while True:
            data = client_socket.recv(BUFFER_SIZE)
            client_id = f'{client_address[0]}:{client_address[1] + 1}'
            message = data.decode()
            if message.startswith("create"):
                print(f"{client_address}: create conference")
                response = self.handle_create_conference()
            elif message.startswith("join"):
                conference_id = message.split()[1]
                print(f"{client_address}: join conference {conference_id}")
                response = self.handle_join_conference(conference_id, client_id)
            elif message.startswith("quit"):
                conference_id = message.split()[1]
                print(f"{client_address}: quit conference {conference_id}")
                response = self.handle_quit_conference(conference_id, client_id)
            elif message.startswith("cancel"):
                conference_id = message.split()[1]
                print(f"{client_address}: cancel conference {conference_id}")
                response = self.handle_cancel_conference(conference_id)
            else:
                print("wrong command")
                response = "wrong message"

            print(response)
            client_socket.sendall(response.encode())

    def start(self):
        print(f"Starting server at {self.server_ip}:{self.server_port}")
        self.main_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.main_server.bind((self.server_ip, self.server_port))
        self.main_server.listen(20)
        print(f"Server started, listening on {self.server_ip}:{self.server_port}")

        while True:
            client_socket, client_address = self.main_server.accept()
            client_handler = threading.Thread(target=self.request_handler, args=(client_socket, client_address))
            client_handler.start()



if __name__ == '__main__':
    server = MainServer(SERVER_IP, MAIN_SERVER_PORT)
    server.start()