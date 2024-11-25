from util import *
import socket
import threading
import json
import time

class ConferenceClient:
    def __init__(self):
        self.is_working = True
        self.server_addr = ('127.0.0.1', MAIN_SERVER_PORT)
        self.on_meeting = False
        self.conns = []
        self.support_data_types = ['screen', 'camera', 'audio']
        self.share_data = {}
        self.conference_info = None
        self.recv_data = {}

    def create_conference(self):
        """
        Create a conference: send create-conference request to server and obtain necessary data.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.server_addr)

            request_data = {'action': 'create'}
            sock.send(json.dumps(request_data).encode('utf-8'))

            response = sock.recv(1024)
            response_data = json.loads(response.decode('utf-8'))

            if 'conference_id' in response_data:
                self.conference_info = response_data
                self.conference_id = response_data['conference_id']
                self.manager = response_data['manager']
                print(f'Conference created. Conference ID: {self.conference_id}, Manager: {self.manager}')
                self.on_meeting = True
                self.start_conference()
            else:
                print('[Error]: Failed to create conference')

            sock.close()

        except Exception as e:
            print(f'[Error]: {str(e)}')

    def join_conference(self, conference_id):
        """
        Join a conference: send join-conference request with given conference_id.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.server_addr)

            request_data = {'action': 'join', 'conference_id': conference_id}
            sock.send(json.dumps(request_data).encode('utf-8'))

            response = sock.recv(1024)
            response_data = json.loads(response.decode('utf-8'))

            if 'conference_id' in response_data:
                self.conference_info = response_data
                self.conference_id = response_data['conference_id']
                print(f'Joined conference {self.conference_id}')
                self.on_meeting = True
                self.start_conference()
            else:
                print('[Error]: Failed to join conference')

            sock.close()

        except Exception as e:
            print(f'[Error]: {str(e)}')

    def quit_conference(self):
        """
        Quit your ongoing conference.
        """
        if not self.on_meeting:
            print('[Warn]: Not in a conference.')
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.server_addr)

            request_data = {'action': 'quit', 'conference_id': self.conference_id}
            sock.send(json.dumps(request_data).encode('utf-8'))

            response = sock.recv(1024)
            response_data = json.loads(response.decode('utf-8'))

            if response_data.get('status') == 'success':
                print(f'Left conference {self.conference_id}')
                self.close_conference()
            else:
                print('[Error]: Failed to quit conference')

            sock.close()

        except Exception as e:
            print(f'[Error]: {str(e)}')

    def cancel_conference(self):
        """
        Cancel your ongoing conference (if you are the manager).
        """
        if not self.on_meeting or self.manager != self.conference_info.get('manager'):
            print('[Warn]: You are not the manager or not in a conference.')
            return

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(self.server_addr)

            request_data = {'action': 'cancel', 'conference_id': self.conference_id}
            sock.send(json.dumps(request_data).encode('utf-8'))

            response = sock.recv(1024)
            response_data = json.loads(response.decode('utf-8'))

            if response_data.get('status') == 'success':
                print(f'Conference {self.conference_id} canceled.')
                self.close_conference()
            else:
                print('[Error]: Failed to cancel conference')

            sock.close()

        except Exception as e:
            print(f'[Error]: {str(e)}')

    def keep_share(self, data_type, send_conn, capture_function, compress=None, fps_or_frequency=30):
        """
        Keep sharing certain type of data from server or clients (P2P).
        """
        if data_type not in self.support_data_types:
            print(f'[Warn]: Unsupported data type {data_type}')
            return

        try:
            while self.on_meeting:
                data = capture_function()
                if compress:
                    data = compress(data)
                send_conn.send(data)
                time.sleep(1 / fps_or_frequency)

        except Exception as e:
            print(f'[Error]: {str(e)}')

    def share_switch(self, data_type):
        """
        Switch for sharing certain types of data (screen, camera, audio, etc.)
        """
        if data_type not in self.share_data:
            print(f'[Warn]: {data_type} is not enabled for sharing.')
            return

        self.share_data[data_type] = not self.share_data.get(data_type, False)
        print(f'{"Started" if self.share_data[data_type] else "Stopped"} sharing {data_type}')

    def keep_recv(self, recv_conn, data_type, decompress=None):
        """
        Keep receiving certain types of data (save or output).
        """
        try:
            while self.on_meeting:
                data = recv_conn.recv(1024)
                if decompress:
                    data = decompress(data)
                self.output_data(data)
                time.sleep(0.1)

        except Exception as e:
            print(f'[Error]: {str(e)}')

    def output_data(self, data):
        """
        Output received stream data.
        """
        print(f'Received data: {data}')

    def start_conference(self):
        """
        Initialize connections and start running tasks for the conference.
        """
        print(f'Starting conference {self.conference_id}')
        self.on_meeting = True

    def close_conference(self):
        """
        Close all connections and cancel running tasks.
        """
        self.on_meeting = False
        print(f'Conference {self.conference_id} closed.')

    def start(self):
        """
        Execute functions based on the command line input.
        """
        while True:
            if not self.on_meeting:
                status = 'Free'
            else:
                status = f'OnMeeting-{self.conference_id}'

            recognized = True
            cmd_input = input(f'({status}) Please enter a operation (enter "?" to help): ').strip().lower()
            fields = cmd_input.split(maxsplit=1)
            if len(fields) == 1:
                if cmd_input in ('?', '？'):
                    print(HELP)
                elif cmd_input == 'create':
                    self.create_conference()
                elif cmd_input == 'quit':
                    self.quit_conference()
                elif cmd_input == 'cancel':
                    self.cancel_conference()
                else:
                    recognized = False
            elif len(fields) == 2:
                if fields[0] == 'join':
                    input_conf_id = fields[1]
                    if input_conf_id.isdigit():
                        self.join_conference(input_conf_id)
                    else:
                        print('[Warn]: Input conference ID must be in digital form')
                elif fields[0] == 'switch':
                    data_type = fields[1]
                    if data_type in self.share_data.keys():
                        self.share_switch(data_type)
                else:
                    recognized = False
            else:
                recognized = False

            if not recognized:
                print(f'[Warn]: Unrecognized cmd_input {cmd_input}')


if __name__ == '__main__':
    client1 = ConferenceClient()
    client1.start()