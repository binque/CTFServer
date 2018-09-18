# -*- coding: UTF-8 -*-
'''
@Created: 20170822
@author: leochechen
@summary: 异常检查模块。检查ctf在运行过程中是否出现了异常
'''
import datetime
from render import render_html
from exptions import *
from protocol import Command
from ctf_local import get_weakref_local_variate
from flow import CLEANUP_FLOWS
from context import VARPASS, VARFAIL, VARABORT, VARNOTRUN, VARUNSUPPORTED, GROUPABORT, EXCEPTION
from parse import convert_str
# 异常回调类型
(CALLBACK, RERUN) = range(0, 2)


class ICallback(object):
    '''
    异常回调逻辑类
    '''
    def __init__(self, worker):
        self.worker = worker
        self.hash_template = "Exception-{0},Category-{1}"
        # 支持的异常回调类型
        self.exceptions = (VarFail.__name__, VarAbort.__name__, VarNotRun.__name__, VarUnsupported.__name__,
                           GroupAbort.__name__, Exception.__name__)
        # 异常重跑的key
        self.rerun_key_info = {hash(self.hash_template.format(exception, RERUN)): exception
                               for exception in self.exceptions}
        # 异常回调的key
        self.recall_key_info = {hash(self.hash_template.format(exception, CALLBACK)): exception
                                for exception in self.exceptions}
        # client端注册的异常
        self.docker = {}

    def __call__(self, exception, category):
        key = hash(self.hash_template.format(exception, category))
        if key in self.docker:
            data = self.docker[key]
            if "moudle" not in data or "function" not in data:
                return
            else:
                self.worker.send_command(Command.EXEC_FNC, {
                    'moudle': data["moudle"],
                    'fnc': data["function"],
                    'args': []
                })
                try:
                    return convert_str(self.worker.wait_client())
                except Exception, ex:
                    self.worker.send_command(Command.RECV_MESSAGE, str(ex))

    def register_from_client(self, data):
        exception, category, data = data
        if exception in self.exceptions:
            key = hash(self.hash_template.format(convert_str(exception), category))
            self.docker[key] = data
        else:
            raise EnvironmentError("ctf不支持异常-{}的注册".format(convert_str(exception)))

    def get_register_value(self, status):
        '''
        获取注册的异常重跑的数据
        :param status: 异常名
        :return:
        '''
        t_key = hash(self.hash_template.format(status, RERUN))
        return self.docker[t_key] if t_key in self.docker else None

    def get_rerun_key(self):
        '''
        获取已经注册的异常重跑的key
        :return:
        '''
        return set(self.docker.keys()) & set(self.rerun_key_info.keys())

    def get_callback_key(self):
        '''
        获取已经注册的异常回调的key
        :return:
        '''
        return set(self.docker.keys()) & set(self.recall_key_info.keys())


class ICollection(object):
    '''
    1.异常检测
    2.异常回调
    2.用例统计
    3.日志输出统计
    '''
    def __init__(self):
        self.worker = get_weakref_local_variate('worker')
        self.callback = ICallback(self.worker)
        self.ctx = self.worker.get_ctx
        # html header渲染数据
        self.header = {}
        # 精确度
        self.precision = 4
        self.time_format = '%Y-%m-%d %X'
        self.total_tests = 0
        self.var_expect = 0
        self.var_pass = 0
        self.var_abort = 0
        self.var_fail = 0
        self.var_not_run = 0

    def run_callable_one_step(self, flow, callable_instance):
        '''
        探测ctf的callable对象，记录运行时的状态信息，并在最后判断用例是否通过
        :param flow: 探测流程
        :param callable_instance: 被探测的一个流程方法对象
        :return:
        '''
        try:
            callable_instance()
            # 清理流程不会影响异常状态
            if flow not in CLEANUP_FLOWS:
                self.ctx.Record.testcase_info.status = VARPASS
            return True
        except Exception, e:
            # 异常时堆栈信息
            self.ctx.Record.testcase_info.add_track_message(str(e))
            if type(e) == VarFail:
                self.ctx.Record.testcase_info.status = VARFAIL
            else:
                self.ctx.Record.testcase_info.status = VARABORT

            # 异常回调
            self.callback(type(e).__name__, CALLBACK)
            return False

    def run_callable(self, var, callable_instance, *args, **kwargs):
        '''
        探测一个用例是否运行通过
        :param var: 用例标签逻辑类
        :param callable_instance: 用例逻辑对象
        :param args: callable_instance的args
        :param kwargs: callable_instance的kwargs
        :return:
        '''
        def target():
            self.ctx.Record = self.ctx.get_copy_record(var)
            self.ctx.Record.testcase_info.testcase_start()
            if self.ctx.ParentContext.testcase_info.is_pass:
                callable_instance(*args, **kwargs)
            else:
                self.ctx.Record.testcase_info.add_skip_info()
            self.ctx.Record.testcase_info.testcase_finished()
        target()

        # 检查是否注册异常重跑
        rerun_data = self.callback.get_register_value(self.ctx.Record.testcase_info.status)
        if rerun_data and 'count' in rerun_data:
            self.run_callable_when_exception(target, rerun_data['count'])

    def run_callable_when_exception(self, inner_fnc, count):
        '''
        当注册了异常重跑后，用例发生异常将会调用该函数
        :param inner_fnc: 重跑执行函数
        :param count: 重跑次数
        :return:
        '''
        for i in range(count):
            inner_fnc()
            self.ctx.Record.testcase_info.dsc = "{0}-重跑次数:{1}".format(self.ctx.Record.testcase_info.dsc, i)
            if self.ctx.Record.testcase_info.status == VARPASS:
                break
            # print self.ctx.Record.testcase_info.status

    def receive_img_src_from_client(self, data):
        '''
        接收client端的截图路径
        :param data:
        :return:
        '''
        self.ctx.Record.testcase_info.img_srcs.append(convert_str(data))

    def collect_runtime_info(self):
        html_tag = {
                    VARPASS: "success",
                    VARFAIL: "danger",
                    VARABORT: "warning",
                    VARNOTRUN: "info"
                    }

        test_cases_list = []
        total_test_id = []
        for Record in self.ctx.Runned_Record[1:-1]:
            total_test_id.append(Record.get_attributes('vid'))
            test_cases_list.append((Record.testcase_info.dsc,
                                    Record.testcase_info.vid,
                                    Record.pid,
                                    html_tag[Record.testcase_info.status],
                                    Record.testcase_info.track_message,
                                    Record.testcase_info.img_srcs))

            if Record.testcase_info.status == VARPASS:
                self.var_pass += 1
            elif Record.testcase_info.status == VARFAIL:
                self.var_fail += 1
            elif Record.testcase_info.status == VARABORT:
                self.var_abort += 1
            elif Record.testcase_info.status == VARNOTRUN:
                self.var_not_run += 1
        self.var_expect = self.var_pass + self.var_fail + self.var_abort + self.var_not_run
        self.total_tests = len(set(total_test_id))
        return test_cases_list

    def gather(self):
        test_cases_list = self.collect_runtime_info()
        self.ctx.alw('Vars expected    :[%d]'  % self.var_expect, False)
        self.ctx.alw('Vars passed      :[%d]'  % self.var_pass, False)
        self.ctx.alw('Vars aborted     :[%d]'  % self.var_abort, False)
        self.ctx.alw('Vars failed      :[%d]'  % self.var_fail, False)
        self.ctx.alw('Vars Not Run     :[%d]'  % self.var_not_run, False)
        self.ctx.alw('Vars Total       :[%d]'  % self.total_tests, False)

        # html头部数据处理
        self.header['title'] = "CTF云测报告-{}".format(self.worker.serial)
        self.header['rerun'] = ','.join(["{0}: {1}".format(self.callback.rerun_key_info[key],
                                                           self.callback.docker[key]['count'])
                                         for key in self.callback.get_rerun_key()])

        self.header['callback'] = ','.join(["{0}: {1}.{2}".format(self.callback.recall_key_info[key],
                                                                  self.callback.docker[key]['moudle'],
                                                                  self.callback.docker[key]['function'])
                                            for key in self.callback.get_callback_key()])
        self.header['root'] = self.worker.root
        self.header['html'] = self.worker.filename
        self.header['option'] = str(self.worker.opt)
        self.header["start_time"] = datetime.datetime.fromtimestamp(int(self.ctx.ParentContext.testcase_info.start_time))\
            .strftime(self.time_format)
        self.header["duration"] = str(round(self.ctx.ParentContext.testcase_info.elapsed_time, self.precision))
        self.header["status"] = "Pass: {0}, Fail: {1}, Error: {2}, Skip: {3}, TestCases: {4}"\
            .format(self.var_pass, self.var_fail, self.var_abort, self.var_not_run, self.total_tests)

        # 异常回调信息处理
        html_file = render_html(None, headers=self.header, tests_results=test_cases_list)
        self.ctx.html.write(html_file)

