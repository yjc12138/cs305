import socket
import threading
from config import *
from util import *
import cv2
import select
import numpy as np
import traceback
import asyncio

from util import *
import config

def init_socket(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((SERVER_IP, port))
        print(f"成功连接到端口 {port}")
        return sock
    except Exception as e:
        print(f"连接端口 {port} 时出错: {e}")
        return None

class ConferenceClient:
    def __init__(self,):
        # sync client
        self.is_connected = False
        self.username = None
        self.conference_id = None

        self.control_socket=None
        self.screen_socket=None
        self.camera_socket=None
        self.audio_socket=None
        self.word_socket=None

        self.is_working = True
        self.server_addr = None  # server addr
        self.on_meeting = False  # status
        self.conns = None  # you may need to maintain multiple conns for a single conference
        self.support_data_types = []  # for some types of data
        self.share_data = {}

        self.conference_info = None  # you may need to save and update some conference_info regularly

        self.recv_data = None  # you may need to save received streamd data from other clients in conference

    def create_conference(self):
        """
        create a conference: send create-conference request to server and obtain necessary data to
        """
        if not self.is_connected:
            print("请先连接服务器！")
            return None

        try:
            msg =  'create'
            self.control_socket.send(msg)

            response = self.control_socket.recv(BUFFER_SIZE)
            conference_id, port = response.split()
            if conference_id:
                print(f"会议创建成功！会议ID: {conference_id}")
                self.conference_id = conference_id
                self.on_meeting = True

                return conference_id
            else:
                print(f"创建会议失败")
                return None

        except Exception as e:
            print(f"创建会议错误: {e}")
            traceback.print_exc()
            return None

    def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data to
        """
        if not self.is_connected:
            print("请先连接服务器！")
            return False

        try:
            msg =  'join'+' '+conference_id
            self.control_socket.send(msg)

            response = self.control_socket.recv(BUFFER_SIZE)
            port=response

            if port:
                print("加入会议成功！")
                self.conference_id = conference_id
                self.on_meeting = True
                self.screen_socket = init_socket(int(port) + 1)  # 屏幕共享
                self.camera_socket = init_socket(int(port) + 2)  # 摄像头
                self.audio_socket = init_socket(int(port) + 3)  # 音频
                self.word_socket = init_socket(int(port) + 4)  # 文本通信
                return True
            else:
                print(f"加入会议失败 ")
                return False

        except Exception as e:
            print(f"加入会议错误: {e}")
            traceback.print_exc()
            return False

    def quit_conference(self):
        """
        quit your on-going conference
        """
        if not self.on_meeting:
            print("当前不在会议中！")
            return False

        try:
            msg = 'quit'+' '+self.conference_id
            self.control_socket.send(msg)

            response = self.control_socket.recv(BUFFER_SIZE)

            if response:
                print("已退出会议")
                self.on_meeting = False
                self.conference_id = None
                self.screen_socket = None
                self.camera_socket = None
                self.audio_socket = None
                self.word_socket = None
                return True
            else:
                print(f"退出会议失败")
                return False

        except Exception as e:
            print(f"退出会议错误: {e}")
            traceback.print_exc()
            return False

    def cancel_conference(self):
        """
        cancel your on-going conference (when you are the conference manager): ask server to close all clients
        """
        #todo:权限
        try:
            self.quit_conference()
            msg = 'cancel'+' '+self.conference_id

            self.control_socket.send(msg)

            response = self.control_socket.recv(BUFFER_SIZE)

            if response:
                print("已取消会议")
                self.on_meeting = False
                self.conference_id = None
                return True
            else:
                print(f"取消会议失败")
                return False

        except Exception as e:
            print(f"取消会议错误: {e}")
            traceback.print_exc()
            return False

    def keep_share_camera(self, send_conn, capture_function, compress=None, fps_or_frequency=30):
        '''
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        '''
        pass

    def keep_share_screen(self, send_conn, capture_function, compress=None, fps_or_frequency=30):
        '''
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        '''
        pass

    def keep_share_audio(self, send_conn, capture_function, compress=None, fps_or_frequency=30):
        '''
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        '''
        pass

    def keep_share_word(self, send_conn, capture_function, compress=None, fps_or_frequency=30):
        '''
        running task: keep sharing (capture and send) certain type of data from server or clients (P2P)
        you can create different functions for sharing various kinds of data
        '''
        pass

    def keep_recv(self, recv_conn, data_type, decompress=None):
        '''
        running task: keep receiving certain type of data (save or output)
        you can create other functions for receiving various kinds of data
        '''

    def output_data(self):
        '''
        running task: output received stream data
        '''

    def start_conference(self):
        '''
        init conns when create or join a conference with necessary conference_info
        and
        start necessary running task for conference
        '''

    def close_conference(self):
        '''
        close all conns to servers or other clients and cancel the running tasks
        pay attention to the exception handling
        '''

    def start(self):
        """
        execute functions based on the command line input
        """
        # 创建client时，先和主服务器取得链接
        self.control_socket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self.control_socket.connect((SERVER_IP,MAIN_SERVER_PORT))

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
                elif cmd_input == 'exit':
                    break
                else:
                    recognized = False
            elif len(fields) == 2:
                if fields[0] == 'join':
                    input_conf_id = fields[1]
                    if input_conf_id.isdigit():
                        self.join_conference(input_conf_id)
                    else:
                        print('[Warn]: Input conference ID must be in digital form')
                #TODO: DELETE SWITCH
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