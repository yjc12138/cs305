import threading
import uuid
import socket

from util import *

class ConferenceServer:
    def __init__(self, conference_id, host_id, server_ip, conf_server_port):
        self.conference_id = conference_id
        self.server_ip = server_ip
        self.conf_server_port = conf_server_port
        try:
            text_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            text_socket.bind((server_ip, conf_server_port))
            text_socket.listen(20)
            self.text_socket = text_socket
            screen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            screen_socket.bind((server_ip, conf_server_port + 1))
            screen_socket.listen(20)
            self.screen_socket = screen_socket
            self.camera_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.camera_socket.bind((server_ip, conf_server_port + 2))
            self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_socket.bind((server_ip, conf_server_port + 3))
            self.udp_servers = {'camera': self.camera_socket, 'audio': self.audio_socket}
        except Exception as e:
            return
        self.udp_types = ['camera', 'audio']
        self.clients_info = []
        self.text_conns = {}
        self.screen_conns = {}
        self.host_id = host_id
        self.mode = 'P2P'
        self.running = False

    def handle_udp(self, data_type):
        while self.running:
            data_server = self.udp_servers[self.udp_types[data_type]]
            try:
                data, addr = data_server.recvfrom(BUFFER_SIZE)
                for client_ip in self.clients_info:
                    client_addr = (client_ip.split(':')[0], int(client_ip.split(':')[1]) + data_type + 2)
                    if client_addr != addr:
                        data_server.sendto(data, client_addr)
            except Exception as e:
                break

    def handle_text(self):
        def handle(conn):
            while self.running:
                try:
                    data = conn.recv(BUFFER_SIZE)
                    if data:
                        for client_conn in self.text_conns.values():
                            if client_conn != conn:
                                client_conn.send(data)
                except Exception as e:
                    conn.close()
                    break
        while self.running:
            try:
                text_client, client_address = self.text_socket.accept()
                if text_client:
                    client_id = f'{client_address[0]}:{client_address[1]}'
                    self.text_conns[client_id] = text_client
                    print(f'{client_id} added into text_conns')
                    t = threading.Thread(target=handle, args=(text_client, ))
                    t.start()
            except Exception as e:
                pass

    def handle_screen(self):
        def handle(conn):
            while self.running:
                try:
                    data = conn.recv(BUFFER_SIZE)
                    if data:
                        for client_conn in self.screen_conns.values():
                            if client_conn != conn:
                                client_conn.send(data)
                except Exception as e:
                    conn.close()
                    break
        while self.running:
            try:
                screen_client, client_address = self.screen_socket.accept()
                if screen_client:
                    client_id = f'{client_address[0]}:{client_address[1] - 1}'
                    self.screen_conns[client_id] = screen_client
                    print(f'{client_id} added into screen_conns')
                    t = threading.Thread(target=handle, args=(screen_client, ))
                    t.start()
            except Exception as e:
                pass

    def handle_client(self, client_id):
        if self.running:
            if client_id in self.clients_info:
                self.clients_info.remove(client_id)
                if self.text_conns.get(client_id):
                    self.text_conns[client_id].close()
                    self.text_conns.pop(client_id)
                if self.screen_conns.get(client_id):
                    self.screen_conns[client_id].close()
                    self.screen_conns.pop(client_id)
            else:
                self.clients_info.append(client_id)

    def cancel_conference(self):
        if self.running:
            self.running = False
            for text_conn in self.text_conns.values():
                text_conn.close()
            for screen_conn in self.screen_conns.values():
                screen_conn.close()
            self.text_conns.clear()
            self.screen_conns.clear()
            self.clients_info.clear()
            self.text_socket.close()
            self.screen_socket.close()
            self.camera_socket.close()
            self.audio_socket.close()

    def start(self):
        self.running = True
        t1 = threading.Thread(target=self.handle_udp, args=(0,))
        t1.start()
        t2 = threading.Thread(target=self.handle_udp, args=(1,))
        t2.start()
        t3 = threading.Thread(target=self.handle_text)
        t3.start()
        t4 = threading.Thread(target=self.handle_screen)
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
        self.client_socket = {}

    def handle_create_conference(self, client_id):
        conference_id = str(uuid.uuid4())
        conf_serve_ports = 12345 + len(self.conference_servers) * 4
        conference_server = ConferenceServer(conference_id, client_id, self.server_ip, conf_serve_ports)

        self.conference_servers[conference_id] = conference_server
        conference_server.start()
        message = SUCCESS(conference_id + " " + str(conf_serve_ports))
        return message

    def handle_join_conference(self, conference_id, client_id):
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.handle_client(client_id)
            if len(conference_server.clients_info) == 1:
                message = SUCCESS(f"{0} {0} Client joined")
            elif len(conference_server.clients_info) == 2:
                client_a = conference_server.clients_info[0]
                client_b = conference_server.clients_info[1]
                client_a_address = client_a.split(":")[0]
                client_a_port = client_a.split(":")[1]
                client_b_address = client_b.split(":")[0]
                client_b_port = client_b.split(":")[1]
                message_for_a = f"Connect {client_b_address} {client_b_port}"
                for client, client_conn in self.client_socket.items():
                    client_tmp = f'{client.split(":")[0]}:{int(client.split(":")[1]) + 1}'
                    if client_tmp == conference_server.clients_info[0]:
                        client_conn.send(message_for_a.encode())
                message = SUCCESS(f"{client_a_address} {client_a_port} Client joined")
            else:
                if len(conference_server.clients_info) == 3:
                    conference_server.mode = "CS"
                    for client, client_conn in self.client_socket.items():
                        client_tmp = f'{client.split(":")[0]}:{int(client.split(":")[1]) + 1}'
                        if client_tmp in conference_server.clients_info and client_tmp != client_id:
                            message_to_other = f"Connect {SERVER_IP} {conference_server.conf_server_port}"
                            client_conn.send(message_to_other.encode())
                message = SUCCESS(f"{SERVER_IP} {conference_server.conf_server_port} Client joined")
        else:
            message = FAIL("Conference not found")
        return message

    def handle_quit_conference(self, conference_id, client_id):
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            conference_server.handle_client(client_id)
            if len(conference_server.clients_info) == 2:
                conference_server.mode = "P2P"
                client_a = conference_server.clients_info[0]
                client_b = conference_server.clients_info[1]
                client_a_address = client_a.split(":")[0]
                client_a_port = client_a.split(":")[1]
                client_b_address = client_b.split(":")[0]
                client_b_port = client_b.split(":")[1]
                message_for_a = f"Connect {client_b_address} {client_b_port}"
                message_for_b = f"Connect {client_a_address} {client_a_port}"
                for client, client_conn in self.client_socket.items():
                    client_tmp = f'{client.split(":")[0]}:{int(client.split(":")[1]) + 1}'
                    if client_tmp == conference_server.clients_info[0]:
                        client_conn.send(message_for_a.encode())
                    elif client_tmp == conference_server.clients_info[1]:
                        client_conn.send(message_for_b.encode())
            elif len(conference_server.clients_info) == 0:
                conference_server.cancel_conference()
                del self.conference_servers[conference_id]
            client_new_id = f"{client_id.split(':')[0]}:{int(client_id.split(':')[1]) - 1}"
            self.client_socket[client_new_id].send('Quitted'.encode())
            message = SUCCESS("Client removed")
        else:
            message = FAIL("Conference not found")
        return message

    def handle_cancel_conference(self, conference_id, client_id):
        if conference_id in self.conference_servers:
            conference_server = self.conference_servers[conference_id]
            if client_id == conference_server.host_id:
                for client, client_conn in self.client_socket.items():
                    client_tmp = f'{client.split(":")[0]}:{int(client.split(":")[1]) + 1}'
                    if client_tmp in conference_server.clients_info:
                        client_conn.send('Cancelled'.encode())
                conference_server.cancel_conference()
                del self.conference_servers[conference_id]
                message = SUCCESS("Conference cancelled")
            else:
                message = FAIL("You are not conference host")
        else:
            message = FAIL("Conference not found")
        return message

    def request_handler(self, client_socket, client_address):
        while True:
            try:
                data = client_socket.recv(BUFFER_SIZE)
                client_id = f'{client_address[0]}:{client_address[1] + 1}'
                message = data.decode()
                if message.startswith("create"):
                    print(f"{client_address}: create conference")
                    response = self.handle_create_conference(client_id)
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
                    response = self.handle_cancel_conference(conference_id, client_id)
                else:
                    response = FAIL("Wrong command")

                print(response)
                client_socket.sendall(response.encode())
                if response.startswith("404:You"):
                    client_socket.sendall(response.encode())
            except Exception as e:
                break

    def start(self):
        print(f"Starting server at {self.server_ip}:{self.server_port}")
        self.main_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.main_server.bind((self.server_ip, self.server_port))
        self.main_server.listen(20)
        print(f"Server started, listening on {self.server_ip}:{self.server_port}")

        while True:
            client_socket, client_address = self.main_server.accept()
            client_id = f'{client_address[0]}:{client_address[1]}'
            self.client_socket[client_id] = client_socket
            client_handler = threading.Thread(target=self.request_handler, args=(client_socket, client_address))
            client_handler.start()

if __name__ == '__main__':
    server = MainServer(SERVER_IP, MAIN_SERVER_PORT)
    server.start()