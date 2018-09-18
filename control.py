# -*- coding=utf-8 -*-
'''
Created on 20170804
@author: leochechen
@summary: 标签运行逻辑控制
'''
from parse import *
from ctf_local import get_weakref_local_variate
from flow import FLOWS_ATTR, GROUP_FLOWS, TESTCASE_FLOWS
from cluster_template import ClusterGroup, ClusterTestCase
from exptions import *
TestGroup = ClusterGroup
TestCase = ClusterTestCase


class IControlBase(object):
    # 控制逻辑抽象基类

    __metaclass__ = ABCMeta

    def __init__(self):
        # 获取运行时必须的上下文管理器
        self.ctx = get_weakref_local_variate('worker').get_ctx
        # 获取运行时步骤的异常检测模块
        self.collectioner = get_weakref_local_variate('worker').get_collection

    @abstractmethod
    def driver(self):
        '''
        标签的运行逻辑的驱动方式。每种可运行的标签都需要提供一种标签运行逻辑的驱动方式
        :return:
        '''
        pass

    def parse_testcase_cls(self, cls):
        '''
        这是一个能接收参数的生成器，保存一个实例的对象中的方法，根据接收到的参数运行对应的方法
        :param cls: 脚本解析的类对象,测试用例逻辑类
        :return:
        '''
        # new the object
        instance = cls()
        public_methods = [eval("instance."+method) for method in dir(instance)
                          if callable(getattr(instance, method)) and not method.startswith('__')]
        flow_methods = dict([(eval("method.{}".format(FLOWS_ATTR)), method) for method in public_methods if hasattr(method, FLOWS_ATTR)])
        while True:
            step = yield
            if step in flow_methods:
                yield self.collectioner.run_callable_one_step(step, flow_methods[step])
            else:
                raise CTFRuntimeException("未识别的流程-{}".format(step))

    def run_testcase_one_step(self, testcase_instance, step_str):
        '''
        根据step字符串驱动目标生成器运行一次，并返回是否正常运行的布尔值
        :param testcase_instance: 目标生成器
        :param step_str: 控制脚本方法运行的特殊字符串
        :return: 返回bool值代表脚本有没有正常运行
        '''
        if testcase_instance.send(step_str):
            testcase_instance.send(None)
            return True
        else:
            testcase_instance.send(None)
            return False

    def run_testcase(self, pid):
        '''
        完整运行一整个测试用例脚本的所有流程
        :param pid: 用例重复运行编号
        :return:
        '''
        # 处理动态标签
        self.ctx.Record.set_id(pid)
        # TODO this will return a generator to detect the exception.
        generator_var = self.parse_testcase_cls(TestCase)
        generator_var.send(None)

        if self.run_testcase_one_step(generator_var, TESTCASE_FLOWS[0]) \
                and self.run_testcase_one_step(generator_var, TESTCASE_FLOWS[1]) \
                and self.run_testcase_one_step(generator_var, TESTCASE_FLOWS[2]):
                    self.run_testcase_one_step(generator_var, TESTCASE_FLOWS[-1])
                    pass
        else:
            self.run_testcase_one_step(generator_var, TESTCASE_FLOWS[-1])
        generator_var.close()


class IControlVar(IControlBase):
    '''
    var标签的运行逻辑
    '''
    def __init__(self, var):
        super(IControlVar, self).__init__()
        self._var = var

    def driver(self, pid):
        '''
        标签的运行逻辑的驱动方式。如指定pid运行对应pid的用例，否则根据标签的Period属性值来决定该标签运行多少次
        :param pid: 用例的运行序号
        :return:
        '''
        if pid:
            self.collectioner.run_callable(self._var, self.run_testcase, pid)
        else:
            for _pid in range(0, self._var.Period):
                self.collectioner.run_callable(self._var, self.run_testcase, _pid)

    def __str__(self):
        return str(self._var)

    def __repr__(self):
        return repr(self._var)


class IControlGrp(IControlBase):
    '''
    grp标签标签运行逻辑控制
    '''
    def __init__(self):
        super(IControlGrp, self).__init__()
        self.gen = self.run_testcase()

    def run_testcase(self):
        # 切换成IContextGrp
        self.ctx.set_parentContext()
        self.ctx.Record = self.ctx.ParentContext
        self.ctx.ParentContext.set_id(0)
        self.ctx.ParentContext.testcase_info.testcase_start()
        gGrp = self.parse_testcase_cls(TestGroup)
        gGrp.send(None)
        self.run_testcase_one_step(gGrp, GROUP_FLOWS[0])
        yield
        # 切换回IContextGrp
        self.ctx.Record = self.ctx.ParentContext
        self.run_testcase_one_step(gGrp, GROUP_FLOWS[-1])
        gGrp.close()
        self.ctx.Record.testcase_info.testcase_finished()

    def driver(self):
        '''
        标签的运行逻辑的驱动方式。先运行grp标签对应用例脚本的setup方法，再运行用例脚本，最后运行grp标签对应用例脚本的cleanup方法。
        由于该标签的驱动需要分开运行，所以使用yield暂停，等需要运行时在启动
        :return:
        '''
        try:
            self.gen.send(None)
        except StopIteration:
            pass


class IControl(IControlBase):
    '''
    标签的运行逻辑控制集合
    '''
    def __init__(self):
        super(IControl, self).__init__()
        # 用例标签驱动逻辑运行列表
        self._icontrols = []

    def classify(self, vs):
        '''
        把var分为section组和在varmap下的var，返回一个归类好的列表
        :param vs:
        :return:
        '''
        stack = Stack()
        for var in vs:
            if var is None:
                raise EnvironmentError("var doesn't find")

            if type(var.parent) == VarMap:
                stack.push(IControlVar(var))
        self._icontrols += stack.items

    def init_self_by_vid(self, vid):
        '''
        通过var标签的vid属性值初始化varmap运行逻辑集合
        :param vid: var标签的vid属性值
        :return:
        '''
        self.classify([self.ctx.get_var_by_vid(vid)])

    def init_self_by_set(self, set):
        '''
        通过var标签的set属性值初始化varmap运行逻辑集合
        :param set: var标签的set属性值
        :return:
        '''
        self.classify(list(self.ctx.get_var_by_set(set)))

    def init_self_by_lvl(self, lvl):
        '''
        通过var标签的lvl属性值初始化varmap运行逻辑集合
        :param lvl: var标签的lvl属性值
        :return:
        '''
        self.classify(list(self.ctx.get_var_by_lvl(lvl)))

    def init_self_by_empty(self):
        '''
        使用所有的var标签初始化varmap运行逻辑集合
        :return:
        '''
        self.classify(list(self.ctx.get_all_var()))

    def init_self_by_section(self, st):
        '''
        通过section标签的sid属性值初始化varmap运行逻辑集合
        :param st: section标签的sid属性值
        :return:
        '''
        self.classify(list(self.ctx.get_var_by_section(st)))

    def driver(self, pid):
        '''
        标签的运行逻辑的驱动方式。先运行grp.setup->运行驱动列表中的驱动逻辑->grp.cleanup
        :param pid: 用例的运行序号
        :return:
        '''
        # grp标签驱动逻辑
        ic_grp = IControlGrp()
        ic_grp.driver()
        map(lambda ic: ic.driver(pid), self._icontrols)
        ic_grp.driver()

    def generate_report(self):
        self.collectioner.gather()
        self.ctx.close()

    def start(self, pid):
        '''
        根据命令行设定的运行逻辑运行脚本.
        '' :'the tool will run the all case in the varmap'
        'v':'the tool will run the specified case'
        's':'the tool will run the specified cases which set is the same'
        'l':'the tool will run the specified cases which lvl is the same'
        :param pid: 用例的运行序号
        :return:
        '''
        if self.ctx.model == 'a':
            '''
            empty:  the tool will run the all case in the varmap.Support this model in the future
            '''
            self.init_self_by_empty()
        elif self.ctx.model == 'v':
            '''
            v:  the tool will run the specified case
            ：提供2种运行逻辑
            1.如果var标签在varmap标签下，grp.setup->var.setup->var.run->var.verify->var.cleanup->grp.cleanup
            2.如果var标签在section标签下,grp.setup->section.setup->var.setup->var.run->var.verify->var.cleanup->section.cleanup->grp.cleanup
            :param vid: 用例编号
            :return:
            '''
            self.init_self_by_vid(int(self.ctx.model_val))
        elif self.ctx.model == 's':
            '''
            s:  the tool will run the specified cases which set is the same
            '''
            self.init_self_by_set(int(self.ctx.model_val))
        elif self.ctx.model == 'l':
            '''
            l: the tool will run the specified cases which lvl is the same
            '''
            self.init_self_by_lvl(int(self.ctx.model_val))

        # 运行逻辑
        self.driver(pid)
        # 统计结果
        self.generate_report()

