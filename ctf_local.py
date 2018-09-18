# -*- coding=utf-8 -*-
'''
Created on 20171031
@author: leochechen
@summary: ctf全局变量
'''
import weakref
import threading
from functools import wraps

# 线程级全局变量，该变量会存储CTF Server和Client连接中
CTFWorkerLocal = threading.local()

# CTF全局字典
CTFGlobal = {}

# CTF全局互斥锁
CTFLock = threading.Lock()


# 获取当前线程的local变量的弱引用
def get_weakref_local_variate(name):
    return weakref.proxy(getattr(CTFWorkerLocal, name))


# 对操作进行加锁
def lock_self(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            CTFLock.acquire()
            return func(*args, **kwargs)
        finally:
            CTFLock.release()
    return wrapper
