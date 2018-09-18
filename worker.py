# -*- coding: UTF-8 -*-
'''
Created on 20171031
@author: leochechen
@Summary: 一个Client连接过来，对应一个Worker。worker使用Python中的线程实现
'''
import os
import pickle
import argparse
import traceback
import threading
from threading import Thread
from operator import itemgetter
from protocol import Command
from ctf_local import CTFWorkerLocal, CTFGlobal, lock_self
from parse import VarMap, ParseHTMLTeamplate, convert_str
from control import IControl
from context import IContext
from collection import ICollection
from exptions import *


class Worker(Thread):
    '''
    ctf Server交互线程、抽象工作者
    '''
    def __init__(self, server, sock, addr):
        super(Worker, self).__init__()
        self.server, self.sock, (self.client, self.port) = server, sock, addr
        # 用于获取当前工作者的上下文实例
        self.get_varmap = None
        self.get_ctx = None
        self.get_collection = None
        self.cmd = {}
        self.env = {}
        self.serial = ""
        # project root
        self.root = ""

        # options
        self.filename = ""
        self.html = ""
        self.opt = ""
        # case pid
        self.pid = ""
        # exception
        self.exitcode = 0
        self.exception = None
        self.exc_traceback = ''
        self.server.log_info("ACCEPT:({0},{1}) connect now...".format(self.client, self.port))

    @property
    def log_directory(self):
        return self.env['TESTCASE']['report']['log']

    @property
    def html_directory(self):
        return self.log_directory

    def run(self):
        try:
            CTFWorkerLocal.worker = self
            # start work
            cmd, data = self.recv_command()
            if cmd == Command.CTF_START:
                self.ctf_start(data)
            else:
                raise CTFTestServerError("CTF Server 启动出错,Code:{} Data:{}".format(cmd, convert_str(data)))
        except Exception, e:
            self.exitcode = 1
            self.exception = e
            self.exc_traceback = traceback.format_exc()
            self.server.log_info("current thread {0}:{1}".format(threading.currentThread().getName(), self.exc_traceback))
            self.send_command(Command.RECV_MESSAGE, "{0}:\n{1}".format(type(e).__name__, e))
        finally:
            self.send_command(Command.CTF_CLOSE, "")
            self.sock.close()
            self.server.log_info("ACCEPT:({0},{1}) close now...".format(self.client, self.port))

    def ctf_start(self, data):
        self.cmd, self.serial, self.env = pickle.loads(data['cmd']), data['serial'], data['env']
        # 工程根目录
        self.root = os.path.dirname(self.cmd[0])
        # 解析command line
        pargs = self.parse_command_line(self.cmd[1:], encode=self.env['LANGUAGE_ENCODE'],
                                        decode=self.env['LANGUAGE_DECODE'])
        # 解析运行方式
        self.parse_opt(pargs)
        # 得到设定pid
        self.pid = pargs.pid
        # 获取需要运行的html
        for filename, html in self.parse_html(pargs):
            self.run_html(filename, html)

    def run_html(self, filename, html):
        '''
        运行指定一张html
        :param filename: html名
        :param html: 包含所有html信息的字符串
        :return:
        '''
        try:
            self.filename, self.html = filename, html
            # 解析html生成数据结构varmap
            ParseHTMLTeamplate.load_html(self.html)
            # 获取运行时必须的上下文管理器
            self.get_ctx = IContext(opt=self.opt, db=None)
            # 获取运行时步骤的异常检测模块
            self.get_collection = ICollection()
            IControl().start(self.pid)
        except Exception, ex:
            raise
            self.send_command(Command.RECV_MESSAGE, str(ex))

    def parse_command_line(self, args, encode, decode):
        parser = argparse.ArgumentParser("ctf")
        # ctf命令必须指定一张或者多张html
        parser.add_argument('-html', help='which html will run', action='append', default=[], dest="html",
                            type=lambda bytestring: bytestring.decode(decode).encode(encode))
        # ctf六种运行方式
        parser.add_argument('-vid', help='run the specified case in specified xml', dest="vid", type=str)
        parser.add_argument('-set', help='run the cases which have the same set value in specified xml', dest="set", type=str)
        parser.add_argument('-lvl', help='run the cases which have the same level value in specified xml', dest='lvl', type=str)
        parser.add_argument('-all', help='run the all cases in specified xml', dest="all", action='store_true')
        parser.add_argument('-section', help="run the cases which is in the same section", dest="section", type=str)
        parser.add_argument('-dir', help='run all xmls in the directory', dest="dir", action='store_true')
        # ctf拓展命令
        parser.add_argument('-pid', help="run the case which num is pid", dest="pid", type=int)
        parser.add_argument('-case', help='print the cases in specified xml', dest="cases", action='store_true')
        parser.add_argument('-version', help="print the ctf version and information about author", dest="version", action='store_true')
        parser.add_argument('-serial', dest="serial", help="adb devices android mobile serial", type=str)
        return parser.parse_args(args=args)

    def parse_opt(self, pargs):
        '''
        解析从命令行中获取的运行方式
        :param pargs: 命令行解析实例
        :return:
        '''
        opts = [("v", "vid"),
                ("s", "set"),
                ("l", "lvl"),
                ("st", "section"),
                ("a", "all")]

        reminder = "CTF现有运行方式 {}".format(",".join(["|".join(_) for _ in opts]))

        _opt = filter(itemgetter(1), [("v", pargs.vid), ("s", pargs.set), ("l", pargs.lvl),
                                      ("st", pargs.section), ("a", pargs.all)])
        if len(_opt) == 0:
            raise EnvironmentError("CTF命令必须指定一种运行方式：{}".format(reminder))
        elif len(_opt) > 1:
            raise EnvironmentError("CTF命令中只能含有一种运行方式：{}".format(reminder))
        elif len(_opt) == 1:
            _opt = itemgetter(0)(_opt)
            _opt = ("a", "") if _opt[0] == "a" \
                else _opt
        self.opt = _opt

    def parse_html(self, pargs):
        '''
        根据命令获取能运行的html文件
        :param pargs: 命令行解析实例
        :return:
        '''
        def load_xml(f):
            if '.html' not in f:
                _file = f + ".html"
                filename = f
            else:
                filename, suffix = os.path.splitext(f)
                _file = f
            self.send_command(Command.LOAD_HTML, {
                'html': _file,
                'kwargs': pargs.__dict__
            })
            data = self.wait_client()
            return convert_str(filename), convert_str(data['html'])

        if pargs.dir:
            self.send_command(Command.LOAD_DIRECTORY, {
                'directory': self.env['TESTCASE']['workspace']
            })
            data = self.wait_client()
            return [load_xml(filename) for filename in data['xmls']]
        elif pargs.html:
            return [load_xml(filename) for filename in pargs.html]
        else:
            raise EnvironmentError("需指定一张或者多张html")

    def send_command(self, cmd, params):
        '''
        向客户端发送一条命令
        :param cmd: 命令
        :param params: 数据
        :return:
        '''
        self.server.send_data(self.sock, {
            'CTFCMD': cmd,
            'CTFDATA': params
        })

    def recv_command(self):
        '''
        从客户端接收一个命令
        :return:
        '''
        ret = self.server.recv_data(self.sock)
        return ret['CTFCMD'], ret['CTFDATA']

    def wait_client(self):
        '''
        在等待client的消息过程中，服务端能够响应并作出应答的命令
        :return:
        '''
        while True:
            cmd, data = self.recv_command()
            if cmd == Command.SUCCESS:
                return data
            elif cmd == Command.ERROR:
                raise Exception(data)
            elif cmd == Command.RECV_MESSAGE:
                self.get_ctx.alw(data)
            elif cmd == Command.GET_VAR_RECORD:
                content = self.get_ctx.Record[convert_str(data)]
                self.send_command(Command.RECV_MESSAGE, content)
            elif cmd == Command.GET_TESTCASE_INFO:
                self.send_command(Command.RECV_MESSAGE, {
                    "attrs": self.get_ctx.Record.attributes,
                    "html": self.filename,
                    "env": self.env
                })
            elif cmd == Command.REG_CALLBACK:
                self.get_collection.callback.register_from_client(data)
                self.send_command(Command.RECV_MESSAGE, "")
            elif cmd == Command.RECV_IMG_SRC:
                self.get_collection.receive_img_src_from_client(data)
                self.send_command(Command.RECV_MESSAGE, "")
