# -*- coding: UTF-8 -*-
'''
@author: leochechen
@summary: ctf framework运行过程中会出现的异常
'''


class FrameworkException(RuntimeError):
    '''
    框架异常
    '''
    pass


class CTFRuntimeException(Exception):
    '''
    CTF流程运行时会出现的异常
    '''
    pass


class VarAbort(CTFRuntimeException):
    '''
    用例运行异常
    '''
    pass


class VarFail(CTFRuntimeException):
    '''
    用例验证失败
    '''
    pass


class GroupAbort(CTFRuntimeException):
    '''
    用例组异常
    '''
    pass


class VarNotRun(CTFRuntimeException):
    '''
    用例没有运行
    '''
    pass


class VarUnsupported(CTFRuntimeException):
    '''
    不支持该运行方式
    '''
    pass


class VarmapException(FrameworkException):
    '''
    XML文件解析错误
    '''
    pass


class VarmapParseException(FrameworkException):
    '''
    标签驱动解析遇到无法识别的标签时抛出的异常
    '''
    pass


class CTFTestServerError(FrameworkException):
    '''
    ctf server出现异常
    '''
    pass


class CTFInvaildArg(FrameworkException):
    '''
    ctf传输数据异常
    '''
    pass


