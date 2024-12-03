import socket

from util import *
import config
import time


class ConferenceClient:
    def __init__(self,):
        # sync client
        #udp
        self.screen_socket=None
        self.screen_port=None
        self.camera_socket=None
        self.camera_port = None
        self.audio_socket=None
        self.audio_port = None
        #tcp
        self.control_socket = None
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
        pass

    def join_conference(self, conference_id):
        """
        join a conference: send join-conference request with given conference_id, and obtain necessary data to
        """
        pass

    def quit_conference(self):
        """
        quit your on-going conference
        """
        pass

    def cancel_conference(self):
        """
        cancel your on-going conference (when you are the conference manager): ask server to close all clients
        """
        pass

    import time
    import cv2

    def keep_share_camera(self, send_conn, capture_function, compress=None, fps_or_frequency=30):
        """
        向服务器实时传输摄像头的视频流
        :param send_conn: 发送数据的网络连接（如UDP socket）
        :param capture_function: 捕获视频的函数，默认使用capture_camera
        :param compress: 图像压缩函数，默认使用compress_image
        :param fps_or_frequency: 视频发送的帧率（FPS）
        """
        # 设置帧间隔
        frame_interval = 1.0 / fps_or_frequency

        while self.on_meeting:  # 保证在会议进行时持续发送
            # 捕获摄像头图像
            try:
                frame = capture_function()
            except Exception as e:
                print(f"捕获摄像头图像失败: {e}")
                continue

            # 压缩图像
            if compress:
                compressed_frame = compress(frame)
            else:
                compressed_frame = frame

            # 创建消息并发送
            try:
                send_conn.sendto(compressed_frame, (SERVER_IP, self.camera_port))  # 发送数据
            except Exception as e:
                print(f"发送视频帧失败: {e}")

            # 等待到达下一个帧时间点
            time.sleep(frame_interval)

    def keep_recv_camera(self, recv_conn, decompress=None):
        '''
        running task: keep receiving certain type of data (save or output)
        you can create other functions for receiving various kinds of data
        '''
        while self.on_meeting:  # 保证在会议进行时持续接收数据
            try:
                # 接收数据
                data = recv_conn.recv()
                if not data:
                    break  # 如果没有数据，表示连接已关闭或出现问题

                # 处理视频帧
                if decompress:
                    # 如果提供了解压函数，则解压视频数据
                    video_frame = decompress(data)
                else:
                    # 如果没有解压函数，直接使用数据
                    video_frame = data

                # 显示或处理视频帧
                self.output_data(data,'camera')

            except Exception as e:
                print(f"接收数据时发生错误: {e}")
                break

            # 控制接收频率（避免过高的处理负荷）
            time.sleep(0.01)  # 可根据需求调整

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
        if type=='camera':
            try:
                if data:
                    # 显示视频帧
                    frame = resize_image_to_fit_screen(data, my_screen_size)
                    cv2.imshow("Received Camera Feed", np.array(frame))  # 使用 OpenCV 显示视频
                    cv2.waitKey(1)  # 确保显示更新
            except Exception as e:
                print(f"显示摄像头视频时发生错误: {e}")

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
                elif fields[0]=='camera' and fields[1]=='enable':
                    self.keep_share_camera()
                else:
                    recognized = False
            else:
                recognized = False

            if not recognized:
                print(f'[Warn]: Unrecognized cmd_input {cmd_input}')


if __name__ == '__main__':
    client1 = ConferenceClient()
    client1.start()