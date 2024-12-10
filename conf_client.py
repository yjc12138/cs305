import socket
import threading
from config import *
from util import *
import cv2
import select
import numpy as np
import traceback
import time
import asyncio
from threading import Thread

from util import *
import config

cap=cv2.VideoCapture(0)


def init_socket(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('localhost', port))
        return sock
    except Exception as e:
        print(f"连接时出错: {e}")
        return None


class ConferenceClient:
    def __init__(self, ):
        # sync client
        self.is_connected = False
        self.username = None
        self.conference_id = None
        # udp
        self.screen_socket = None
        self.screen_port = None
        self.camera_socket = None
        self.camera_port = 5555
        self.audio_socket = None
        self.audio_port = None
        # tcp
        self.control_socket = None
        self.word_socket = None

        self.is_working = True
        self.server_addr = None  # server addr
        self.on_meeting = False  # status
        self.conns = None  # you may need to maintain multiple conns for a single conference
        self.support_data_types = []  # for some types of data
        self.share_data = {}

        self.conference_info = None  # you may need to save and update some conference_info regularly

        self.recv_data = None  # you may need to save received streamd data from other clients in conference

        self.reader = None
        self.writer = None

    def reconnect(self):
        """重新连接到服务器"""
        try:
            if self.control_socket:
                self.control_socket.close()
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((SERVER_IP, MAIN_SERVER_PORT))
            self.is_connected = True
            return True
        except Exception as e:
            print(f"重新连接失败: {e}")
            self.is_connected = False
            return False

    def check_connection(self):
        """检查连接是否活跃，如果不活跃则重新连接"""
        try:
            # 尝试发送空消息来测试连接
            self.control_socket.send(b'')
            return True
        except:
            print("DEBUG: 连接已断开，尝试重新连接...")
            return self.reconnect()

    def create_conference(self):
        try:
            if not self.check_connection():
                print("无法连接到服务器！")
                return None

            print("DEBUG: 准备创建会议...")
            msg = str('create').encode()
            self.control_socket.send(msg)
            print("DEBUG: 等待服务器响应...")
            response = self.control_socket.recv(BUFFER_SIZE).decode()
            print(f"DEBUG: 收到响应: {response}")
            conference_id, port = response.split()

            if conference_id:
                print(f"会议创建成功！会议ID: {conference_id}")
                self.conference_id = conference_id
                self.on_meeting = True
                print("DEBUG: 保持连接状态...")
                # 重新建立连接
                self.reconnect()
                return conference_id
            else:
                print(f"创建会议失败")
                return None

        except Exception as e:
            print(f"创建会议错误: {e}")
            print("DEBUG: 错误详情:")
            traceback.print_exc()
            self.is_connected = False
            return None

    def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data to
        """
        if not self.is_connected:
            print("请先连接服务器！")
            return False

        try:
            msg = str('join' + ' ' + conference_id).encode()
            self.control_socket.send(msg)

            response = self.control_socket.recv(BUFFER_SIZE).decode()
            print(response)
            port = int(response.split(":")[0])

            if port:
                print("加入会议成功！")
                self.conference_id = conference_id
                self.on_meeting = True
                self.screen_socket = init_socket(int(port) + 1)
                self.camera_socket = init_socket(int(port) + 2)
                self.audio_socket = init_socket(int(port) + 3)
                word_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                word_socket.connect((SERVER_IP, port))
                self.word_socket = word_socket
                print("连接会议成功！")
                #self.keep_recv_camera()

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
            self.reconnect()
            print("DEBUG: 准备发送退出请求...")
            if not self.check_connection():
                print("DEBUG: 连接已断开，尝试重连失败")
                return False

            print(f"DEBUG: 当前连接状态: {self.is_connected}")
            msg = str('quit' + ' ' + self.conference_id).encode()
            print(f"DEBUG: 发送消息: {msg}")

            self.control_socket.send(msg)
            print("DEBUG: 消息发送成功")

            print("DEBUG: 等待服务器响应...")
            try:
                response = self.control_socket.recv(BUFFER_SIZE).decode()
                print(f"DEBUG: 收到响应: {response}")
            except ConnectionAbortedError:
                print("DEBUG: 连接已断开，尝试重连...")
                if self.reconnect():
                    # 重新发送退出请求
                    self.control_socket.send(msg)
                    response = self.control_socket.recv(BUFFER_SIZE).decode()
                else:
                    print("DEBUG: 重连失败")
                    return False

            if response:
                print("已退出会议")
                self.on_meeting = False
                self.conference_id = None
                self.screen_socket = None
                self.camera_socket = None
                self.audio_socket = None
                self.word_socket = None
                # 重新建立连接
                self.reconnect()
                return True
            else:
                print(f"退出会议失败")
                return False

        except Exception as e:
            print(f"退出会议错误: {e}")
            print("DEBUG: 错误详情:")
            traceback.print_exc()
            self.is_connected = False
            return False

    def cancel_conference(self):
        if not self.is_connected and not self.reconnect():
            print("无法连接到服务器！")
            return False

        try:
            # 保存会议ID，因为quit_conference会将其设为None
            conference_id = self.conference_id

            # 先退出会议
            if self.on_meeting:
                if not self.quit_conference():
                    print("退出会议失败，无法取消会议")
                    return False

            if not conference_id:
                print("没有可取消的会议")
                return False

            print("DEBUG: 准备发送取消请求...")
            # 发送取消会议请求
            msg = str('cancel' + ' ' + conference_id).encode()
            self.control_socket.send(msg)

            print("DEBUG: 等待服务器响应...")
            response = self.control_socket.recv(BUFFER_SIZE).decode()
            print(f"DEBUG: 收到响应: {response}")

            if response:
                print("已取消会议")
                self.on_meeting = False
                self.conference_id = None
                # 重新建立连接
                self.reconnect()
                return True
            else:
                print(f"取消会议失败")
                return False

        except Exception as e:
            print(f"取消会议错误: {e}")
            print("DEBUG: 错误详情:")
            traceback.print_exc()
            self.is_connected = False
            return False

    async def keep_share_camera(self, send_conn,fps):
        """
        向服务器实时传输摄像头的视频流
        :param send_conn: 发送数据的网络连接（如UDP socket）
        :param capture_function: 捕获视频的函数，默认使用capture_camera
        :param compress: 图像压缩函数，默认使用compress_image
        :param fps_or_frequency: 视频发送的帧率（FPS）
        """
        interval=1.0/fps
        while self.on_meeting:  # 保证在会议进行时持续发送
            # 捕获摄像头图像
            try:
                _,frame = cap.read()
                frame= cv2.flip(frame, 1)
            except Exception as e:
                print(f"捕获摄像头图像失败: {e}")
                continue

            # 压缩图像
            _, send_data = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])

            # 创建消息并发送
            try:
                send_conn.sendto(send_data, (SERVER_IP, self.camera_port))  # 发送数据
            except Exception as e:
                print(f"发送视频帧失败: {e}")
            await asyncio.sleep(interval)


    async def keep_recv_camera(self, recv_conn):
        '''
        running task: keep receiving certain type of data (save or output)
        you can create other functions for receiving various kinds of data
        '''
        while self.on_meeting:  # 保证在会议进行时持续接收数据
            try:
                print("ready recv")
                # 接收数据
                data,_ = recv_conn.recvfrom(65536)
                if not data:
                    break  # 如果没有数据，表示连接已关闭或出现问题
                print("recv data")
                data = np.frombuffer(data, dtype=np.uint8)
                # 处理视频帧
                img = cv2.imdecode(data, 1)
                print("show img")
                # 显示或处理视频帧
                cv2.imshow('c',img)
                cv2.waitKey(1)

            except Exception as e:
                print(f"接收数据时发生错误: {e}")
                break
            await asyncio.sleep(0.02)

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

    def output_data(self, data, type):
        '''
        running task: output received stream data
        '''
        if type == 'camera':
            try:
                if data:
                    # 显示视频帧
                    frame = resize_image_to_fit_screen(data, my_screen_size)
                    cv2.imshow("Received Camera Feed", np.array(frame))  # 使用 OpenCV 显示视频
                    cv2.waitKey(1)  # 确保显示更新
            except Exception as e:
                print(f"显示摄像头视频时发生错误: {e}")

    def start(self):
        """
        execute functions based on the command line input
        """
        try:
            if not self.reconnect():
                print("无法连接到服务器！")
                return
        except Exception as e:
            print(f"初始连接失败: {e}")
            self.is_connected = False
            return

        while True:
            if not self.on_meeting:
                status = 'Free'
            else:
                status = f'OnMeeting-{self.conference_id}'

            recognized = True
            cmd_input = input(f'({status}) Please enter a operation (enter "?" to help): ').strip().lower()

            # 在执行命令前检查连接状态
            if not self.check_connection():
                print("与服务器的连接已断开，请重试")
                continue

            fields = cmd_input.split(maxsplit=1)
            if len(fields) == 1:
                if cmd_input in ('?', '？'):
                    print(HELP)
                elif cmd_input == 'create':
                    self.create_conference()
                    # await self.create_conference()
                elif cmd_input == 'quit':
                    self.quit_conference()
                elif cmd_input == 'cancel':
                    self.cancel_conference()
                else:
                    recognized = False
            elif len(fields) == 2:
                if fields[0] == 'join':
                    input_conf_id = fields[1]
                    self.join_conference(input_conf_id)
                elif fields[0] == 'camera' and fields[1] == 'enable':
                    self.keep_share_camera()
                else:
                    recognized = False
            else:
                recognized = False

            if not recognized:
                print(f'[Warn]: Unrecognized cmd_input {cmd_input}')

    async def test(self):
        camera_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        send_task_camera=asyncio.create_task(self.keep_share_camera(camera_socket,50))
        rev_task_camera=asyncio.create_task(self.keep_recv_camera(camera_socket))
        #send_task_audio=self.keep_share_audio(audio_socket,capture_voice)
        #rev_task_audio=self.keep_recv_audio(audio_socket)
        await asyncio.gather(send_task_camera, rev_task_camera)

if __name__ == '__main__':
    client1 = ConferenceClient()
    client1.start()