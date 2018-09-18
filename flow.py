# -*- coding=utf-8 -*-
'''
@created: 20170808
@author: leochechen
被修饰的函数或者方法会按照GroupSetup->Setup->Run->Verify->Cleanup->GroupCleanup的步骤运行，并会在运行时检测异常，收集起来。
'''
from functools import wraps
from abc import ABCMeta, abstractmethod

FLOWS_ATTR = "_SETUP_"
GROUP_FLOWS = ("_CTF_Group_Setup_", "_CTF_Group_Cleanup_")
TESTCASE_FLOWS = ("_CTF_Setup_", "_CTF_Run_", "_CTF_Verify_", "_CTF_Cleanup_")
CLEANUP_FLOWS = ("_CTF_Group_Cleanup_", "_CTF_Cleanup_")


def GroupSetup(func):
    '''
    修饰脚本中的方法使其会被CTF脚本调用.Group初始化
    :param func: Group脚本中的方法
    :return:
    '''
    setattr(func, FLOWS_ATTR, GROUP_FLOWS[0])

    @wraps(func)
    def inner_deco(*args, **kwargs):
        func(*args, **kwargs)
    return inner_deco


def GroupCleanup(func):
    '''
    修饰脚本中的方法使其会被CTF脚本调用.Group清理
    :param func: Group脚本中的方法
    :return:
    '''
    setattr(func, FLOWS_ATTR, GROUP_FLOWS[-1])

    @wraps(func)
    def inner_deco(*args, **kwargs):
        func(*args, **kwargs)
    return inner_deco


def CaseSetup(func):
    '''
    修饰脚本中的方法使其会被CTF脚本调用.用例初始化
    :param func: 用例脚本中的方法
    :return:
    '''
    setattr(func.__func__, FLOWS_ATTR, TESTCASE_FLOWS[0])

    @wraps(func)
    def inner_deco(*args, **kwargs):
        func(*args, **kwargs)
    return inner_deco


def CaseRun(func):
    '''
    修饰脚本中的方法使其会被CTF脚本调用.用例运行
    :param func: 用例脚本中的方法
    :return:
    '''
    setattr(func, FLOWS_ATTR, TESTCASE_FLOWS[1])

    @wraps(func)
    def inner_deco(*args, **kwargs):
        func(*args, **kwargs)
    return inner_deco


def CaseVerify(func):
    '''
    修饰脚本中的方法使其会被CTF脚本调用.用例运行结果验证
    :param func: 用例脚本中的方法
    :return:
    '''
    setattr(func, FLOWS_ATTR, TESTCASE_FLOWS[2])

    @wraps(func)
    def inner_deco(*args, **kwargs):
        func(*args, **kwargs)
    return inner_deco


def CaseCleanup(func):
    '''
    修饰脚本中的方法使其会被CTF脚本调用.用例环境清理
    :param func: 用例脚本中的方法
    :return:
    '''
    setattr(func, FLOWS_ATTR, TESTCASE_FLOWS[3])

    @wraps(func)
    def inner_deco(*args, **kwargs):
        func(*args, **kwargs)
    return inner_deco


class CTFGroup(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        # 修饰脚本中的方法使其会被CTF脚本调用.Group初始化
        setattr(self.setup.__func__, FLOWS_ATTR, GROUP_FLOWS[0])
        # 修饰脚本中的方法使其会被CTF脚本调用.Group清理
        setattr(self.cleanup.__func__, FLOWS_ATTR, GROUP_FLOWS[-1])

    @abstractmethod
    def setup(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass


class CTFTestCase(object):
    __metaclass__ = ABCMeta

    def __init__(self):
        # 修饰脚本中的方法使其会被CTF脚本调用.用例运行结果验证
        setattr(self.setup.__func__, FLOWS_ATTR, TESTCASE_FLOWS[0])
        # 修饰脚本中的方法使其会被CTF脚本调用.用例运行
        setattr(self.run.__func__, FLOWS_ATTR, TESTCASE_FLOWS[1])
        # 修饰脚本中的方法使其会被CTF脚本调用.用例运行结果验证
        setattr(self.verify.__func__, FLOWS_ATTR, TESTCASE_FLOWS[2])
        # 修饰脚本中的方法使其会被CTF脚本调用.用例环境清理
        setattr(self.cleanup.__func__, FLOWS_ATTR, TESTCASE_FLOWS[3])

    @abstractmethod
    def setup(self):
        '''
        用例初始化
        :return:
        '''
        pass

    @abstractmethod
    def run(self):
        '''
        用例运行
        :return:
        '''
        pass

    @abstractmethod
    def verify(self):
        '''
        用例验证
        :return:
        '''
        pass

    @abstractmethod
    def cleanup(self):
        '''
        用例清理
        :return:
        '''
        pass

