# -*- coding: UTF-8 -*-
'''
Created on 20171025
@author: leochechen
@Summary: ctf服务端Socket代码
'''
from __future__ import print_function
import time
import sys
import json
import socket
import struct
import weakref
from exptions import *
from worker import Worker
from ctf_local import lock_self

# 一次性能够接受的连接数
BACKLOG = 50
(HOST, PORT) = '0.0.0.0', 6777


class ISocketServer(object):
    '''
    ctf测试框架socket服务端
    '''
    def __init__(self):
        self.timeout = 30
        self.retry_sleep_time = 30
        self.count = 0
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((HOST, PORT))
        self.socket.listen(BACKLOG)
        self.log_file = file("ctfServer.log", 'w')
        self.thread_pool = []

    def rebuild(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.bind((HOST, PORT))
            self.socket.listen(BACKLOG)
        except Exception, e:
            self.log_info("rebuild-{0}:{1}".format(type(e), e))

    def log_info(self, info):
        print (info, file=sys.stdout)
        print (info, file=self.log_file)
        self.log_file.flush()

    def start(self):
        self.log_info("CTF Server start now...")
        self.accept()

    def accept(self):
        '''
        监听某端口，如有连接到则开一个线程负责与之交互
        :return:
        '''
        while True:
            try:
                sock, addr = self.socket.accept()
                woker = Worker(weakref.proxy(self), sock, addr)
                woker.start()
            except Exception, e:
                self.log_info("accept-{0}:{1}".format(type(e), e))
                time.sleep(self.retry_sleep_time)
                self.rebuild()

    @lock_self
    def send_data(self, sock, data):
        try:
            serialized = json.dumps(data)
        except (TypeError, ValueError) as e:
            raise CTFInvaildArg('你只能发送JSON序列化之后的数据')
        try:
            length = len(serialized)
            buff = struct.pack("i", length)
            sock.send(buff)
            sock.sendall(serialized)
        except socket.timeout:
            sock.close()
        except socket.error as e:
            sock.close()

    def recv_data(self, sock):
        length_buffer = sock.recv(4)
        if length_buffer:
            total = struct.unpack_from("i", length_buffer)[0]
        else:
            raise CTFTestServerError('recv length is None?')

        view = memoryview(bytearray(total))
        next_offset = 0
        while total - next_offset > 0:
            recv_size = sock.recv_into(view[next_offset:], total - next_offset)
            next_offset += recv_size

        try:
            deserialized = json.loads(view.tobytes())
            return deserialized
        except (TypeError, ValueError) as e:
            raise CTFInvaildArg('Data received was not in JSON format')


if __name__ == "__main__":
    ISocketServer().start()
