# -*- coding: UTF-8 -*-
'''
@created on: 20170809
@modified on: 20171129
@author: leochechen
@summary: ctf framework上下文管理器
'''
import re
import os
import time
import StringIO
from parse import *
from exptions import *
from protocol import Command
from ctf_local import get_weakref_local_variate

TRUE = ('True', 'true', 'TRUE')
FALSE = ('False', 'false', 'FALSE')


class ILog(object):
    def __init__(self):
        self.worker = get_weakref_local_variate('worker')
        self.log = StringIO.StringIO()
        self.frm = '%Y-%m-%d %X'
        self.alw('\n***LOG START***\n', False)

    def alw(self, msg, flag=True):
        '''
        打印ctf自动化过程中需要打印的文本信息
        :param msg: 需要打印的字符串
        :param flag: 是否需要在打印的字符串前面打印当前时间
        :return:
        '''
        msg = convert_str(msg)
        if flag:
            frm_info = time.strftime(self.frm, time.localtime()) + " : " + msg
            self.worker.send_command(Command.RECV_MESSAGE, frm_info)
            self.log.write(frm_info + '\n')
        else:
            self.worker.send_command(Command.RECV_MESSAGE, msg)
            self.log.write(msg + '\n')

    def colse(self):
        if self.log:
            self.alw('\n***LOG DONE***\n', False)
            self.worker.send_command(Command.RECV_FILE, {
                "directory": self.worker.log_directory,
                "filename": self.worker.filename + ".txt",
                "content": self.log.getvalue()
            })
            self.log.close()
        else:
            raise RuntimeError("ctf日志文件{0}不能正常关闭".format(self.Path))


class IHtml(object):
    def __init__(self):
        self.worker = get_weakref_local_variate('worker')
        self.html = StringIO.StringIO()

    def write(self, data):
        self.html.write(data)

    def close(self):
        self.worker.send_command(Command.RECV_FILE, {
            "directory": self.worker.html_directory,
            "filename": self.worker.filename + ".html",
            "content": self.html.getvalue()
        })
        self.html.close()


class IContextRecord(object):
    '''
    ctf脚本运行时记录映射集合
    '''
    def __init__(self, tag):
        self._tag = tag
        self._keymap = {}
        self._pid = 0
        self.worker = get_weakref_local_variate('worker')
        self.varmap = VarMap()

    @property
    def pid(self):
        return self._pid

    @pid.setter
    def pid(self, i):
        self._pid = i

    @property
    def parent(self):
        return self._tag.parent

    @property
    def tag(self):
        return self._tag

    @property
    def attributes(self):
        return self._tag.attributes

    def get_attributes(self, atr):
        if atr in self._tag.attributes:
            return self._tag.attributes[atr]
        else:
            raise CTFRuntimeException(str(self)+"中不存在该属性...")

    def set_id(self, pid):
        '''
        映射规则：映射该层标签下所有rec或者recm的值
        :return:
        '''
        for cld in self._tag.child:
            if type(cld) == Rec:
                self._keymap[cld.attributes["key"]] = cld.value
            elif type(cld) == Recm:
                self._keymap[cld.attributes["key"]] = cld[pid]
        self.pid = pid

    def __str__(self):
        return "Record数据映射集合"

    def __repr__(self):
        return self.__str__()

    def __contains__(self, item):
        return True if item in self._keymap else False

    def __getitem__(self, item):
        if item not in self._keymap:
            return ""
        else:
            return self._keymap[item]


(VARPASS, VARFAIL, VARABORT, VARNOTRUN, VARUNSUPPORTED, GROUPABORT, EXCEPTION) = \
    ('VAR_PASS', 'VarFail', 'VarAbort', 'GroupAbort', 'VarNotRun', 'VarUnsupported', 'Exception')


class ITestCaseInfo(object):
    # 封装用例脚本运行时数据和状态
    def __init__(self, record):
        self.ctx = get_ctx()
        self.record = record
        self.is_pass = True
        self.start_time = 0
        self.stop_time = 0
        self.elapsed_time = 0
        self.dsc = record.attributes["dsc"] if "dsc" in record.attributes else ""
        self.vid = record.attributes["vid"] if "vid" in record.attributes else ""
        self.status = ""
        self.track_message = ""
        self.img_srcs = []

    def testcase_start(self):
        self.start_time = time.time()
        self.ctx.alw("{}".format(str(self.record)))

    def testcase_finished(self):
        self.stop_time = time.time()
        self.elapsed_time = self.stop_time - self.start_time
        if self.status != VARPASS:
            self.is_pass = False
        self.ctx.alw("{} : {}\n".format(self.dsc, self.status))

    def add_skip_info(self):
        self.status = VARNOTRUN
        self.track_message = ""

    def add_track_message(self, message):
        self.track_message = message
        self.ctx.alw(message)


class IContextVar(IContextRecord):
    # var标签运行时映射key-map集合

    def __init__(self, var):
        super(IContextVar, self).__init__(var)
        # 用例运行时各项指标的统计
        self.testcase_info = ITestCaseInfo(self)
        # 待处理的操作集上下文
        self.icontext_clusters = [IContextCluster(self, child) for child in self.tag.child if child.__class__ is Cluster]
        # 已被导入的操作集
        self.imported = []

    @property
    def Period(self):
        return self.tag.Period

    def set_id(self, pid):
        '''
        映射用例运行时的数据集合
        :param pid: pid
        :return: key-map字典
        '''
        super(IContextVar, self).set_id(pid)

        if self.icontext_clusters:
            self._keymap.setdefault("_CTF_CLUSTER_", self.icontext_clusters)
            for cluster in self.icontext_clusters:
                for opt in cluster.icontext_opts:
                    opt.set_id(pid)

    def __str__(self):
        return "{}".format(self.tag)


class IContextArg(IContextRecord):
    # arg标签运行时映射关系

    def __init__(self, iopt, arg):
        super(IContextArg, self).__init__(arg)
        self.iopt = iopt

    def contents(self):
        '''
        arg标签数据映射时参数匹配规则。
        :return:
        '''
        c = self.match_cite(self.tag.value)
        if c:
            yield c
        else:
            yield self.tag.value

    def match_cite(self, value):
        '''
        {数字，数字}的匹配形式，第一个数字代表cluster在var标签中的位置，第二个数字代表opt在前一个cluster标签中的位置
        :param value: 匹配数据
        :return:
        '''
        m = re.match(r"^{(-?\d+),(\d+)}$", value)
        if m:
            c, p = int(m.group(1)), int(m.group(2))
            if c == -1:
                return self.iopt.icluster.icontext_opts[p].ret
            else:
                return self.iopt.icluster.ivar.icontext_clusters[c].icontext_opts[p].ret

    def __str__(self):
        return "{}".format(self.tag)


class IContextOpt(IContextRecord):
    '''
    Opt标签运行时映射关系
    '''
    def __init__(self, icluster, tag):
        super(IContextOpt, self).__init__(tag)
        self.icluster = icluster
        self.ret = None

    def exec_fnc(self):
        '''
        以cluster的module的属性值为模块，opt的fnc的属性值为函数，arg标签的内容为参数，来调用函数
        :return:
        '''
        t_error =  "执行%s出错，Error：{}" % self.tag
        try:
            ctx = get_ctx()
            moudle = self.icluster.load_moudle()

            arguments = self._get_arguments()
            self.worker.send_command(Command.EXEC_FNC, {
                'moudle': moudle,
                'fnc': self.tag.attributes['fnc'],
                'args': arguments.args
            })
            self.ret = self.worker.wait_client()
            ctx.alw("{},需载入模块：{}, 参数{}..."
                    .format(self.get_attributes("id"), self.get_attributes("fnc"), arguments))
        except VarFail, ex:
            raise VarFail(t_error.format(ex))
        except VarAbort, ex:
            raise VarAbort(t_error.format(ex))
        except Exception, ex:
            raise Exception(t_error.format(ex))

    def _get_arguments(self):
        cls = self

        class Arguments(object):
            def __init__(self):
                # IContexArg的Context返回的参数生成器，顾使用list取出所有值，最后进行列表连接
                self.args = list(chain(*[list(IContextArg(cls, child).contents()) for child in cls._tag.child
                                         if type(child) == Arg]))

            def __str__(self):
                # 字符串化参数
                targs = [str(arg) for arg in self.args]
                return '[' + ','.join(targs) + ']'

            def __repr__(self):
                return self.__str__()

        return Arguments()

    def __str__(self):
        return "{}".format(self.tag)


class IContextCluster(IContextRecord):
    def __init__(self, ivar, tag):
        super(IContextCluster, self).__init__(tag)
        self.ivar = ivar
        self.icontext_opts = [IContextOpt(self, child) for child in self.tag.child if type(child) == Opt]
        # cls加载后是一个callable对象，可以是函数或者类
        self._instance = None
        self._module = None
        self._exec = None
        self.exec_dsc =  self.get_attributes('exec')
        self.flow = self.get_attributes('flow')

    def load_moudle(self):
        try:
            if not self._module:
                # TODO second,if mould is None,to do load_moudle
                model_name = self.tag.attributes['module']
                self.worker.send_command(Command.EXEC_MOUDLE, model_name)
                self._module = self.worker.wait_client()
            return self._module
        except Exception, ex:
            raise Exception("{0}加载错误：\n {1}".format(self,ex))

    def load_exec(self, fnc):
        try:
            if not self._module:
                self.load_moudle()

            self.worker.send_command(Command.EXEC_EXEC, {
                'moudle': self._module,
                'exec': fnc,
            })
            self._exec = self.worker.wait_client()
        except Exception, ex:
            raise Exception(str(ex))

    def __str__(self):
        return "{}".format(self.tag)

    def __getitem__(self, item):
        return self.icontext_opts[item]


class IContextGrp(IContextVar):
    '''
    grp标签运行时映射key-map集合
    '''
    def __init__(self, grp):
        super(IContextGrp, self).__init__(grp)
        self.vid = -1

    # @property
    # def attributes(self):
    #     obj = self
    #
    #     class GrpAttributes(object):
    #         def __getitem__(self, item):
    #             if item in obj.tag.attributes:
    #                 return obj.tag.attributes[item]
    #             elif item == 'vid':
    #                 return obj.vid
    #             elif item == 'dsc':
    #                 return obj.dsc
    #     return GrpAttributes()

    def __str__(self):
        return "{}".format(self.tag)


class IContext(object):
    '''
    用例运行时的数据和逻辑的集合。上下文管理器
    主要功能有：
    1.varmap数据
    2.日志文件
    3.报告文件
    4.var标签的变量映射
    5.流程步骤运行信息保存
    6.运行逻辑判定
    7.用例解析脚本选择
    8.封装相关数据库操作
    9.用例全局缓存
    '''
    def __init__(self, opt, db=None):
        self.varmap = VarMap()
        self.logger = ILog()
        self.html = IHtml()
        self._runned_Record = []
        self._running_record = None
        self.parentContext = None
        self.model = opt[0]
        self.model_val = opt[1]
        self.db = db
        # 用于全局保存一些东西，需用户自己维护
        self._buffer = {}

    @property
    def Runned_Record(self):
        '''
        返回已经运行过的记录
        :return:
        '''
        return self._runned_Record

    @property
    def ParentContext(self):
        '''
        用户获取Grp的上下文管理器
        :return:
        '''
        return self.parentContext

    @property
    def Record(self):
        return self._running_record

    @Record.setter
    def Record(self, record):
        '''
        Context切换
        :param record: record必须是IContextRecord的派生类
        :return:
        '''
        if IContextRecord in getmro(record.__class__):
            self._running_record = record
            self._runned_Record.append(record)
        else:
            raise CTFRuntimeException("只能用于IContextRecord派生类的切换")

    def set_parentContext(self):
        self.parentContext = IContextGrp(self.varmap.grp)

    def get_copy_record(self, var):
        '''
        返回一个深度拷贝的var标签实例
        :param var: var标签实例
        :return:
        '''
        copy_var = var.copy_self(var.parent)
        return self.get_icontextvar_by_var(copy_var)

    def clear_copy_records(self):
        for record in self._runned_Record[1:-1]:
            tag = record.tag
            tag.del_self()
            del tag

    def alw(self, msg, isPrtTime=True):
        '''
        格式化日志输出
        :param msg:
        :param isPrtTime:
        :return:
        '''
        self.logger.alw(msg, isPrtTime)

    def get_icontextvar_by_vid(self, vid):
        '''
        获取对应vid的var实例,并返回IContextVar实例
        :param vid: var编号
        :return:
        '''
        for child in self.varmap.vars:
            if child.__class__.__name__ == 'Var' and child.attributes['vid'] == vid:
                return IContextVar(child)

    def get_icontextvar_by_var(self, var):
        '''
        获取var实例对应的IContextVar实例
        :param var: var标签实例
        :return:
        '''
        return IContextVar(var)

    def get_var_by_vid(self, vid):
        '''
        通过vid获取var标签的实例
        :param vid: 用例编号
        :return:
        '''
        for child in self.varmap.vars:
            if child.attributes['vid'] == vid:
                return child

    def get_var_by_set(self, set):
        '''
        获取一组相同set的var实例
        :param set: 组号
        :return:
        '''
        for child in self.varmap.vars:
            if child.attributes['set'] == set:
                yield child

    def get_var_by_lvl(self, lvl):
        '''
        获取一组相同lvl的var实例
        :param lvl: lvl
        :return:
        '''
        for child in self.varmap.vars:
            if child.attributes['lvl'] == lvl:
                yield child

    def get_all_var(self):
        '''
        获取所有的var实例
        :return:
        '''
        for child in self.varmap.vars:
            yield child

    def close(self):
        # 日志写入
        self.logger.colse()
        # 报告写入
        self.html.close()
        # 记录数据清理
        self.clear_copy_records()

    def __str__(self):
        return "CTF 上下文管理器"

    def __repr__(self):
        return self.__str__()


XML_ICONTEXT_STRUCTURE = dict((
    (Var, IContextVar),
    (Arg, IContextArg),
    (Opt, IContextOpt),
    (Cluster, IContextCluster),
    (Grp, IContextGrp)
))


def get_ctx():
    '''
    用于获取框架运行所需要的上下文管理器。线程级单例模式
    :return:
    '''
    return get_weakref_local_variate('worker').get_ctx
