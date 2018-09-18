# -*- coding: UTF-8 -*-
'''
Created on 201708011
@author: leochechen
@Summary: 提供cluster标签操作组自动化运行的模板
'''
import re
import random
import inspect
from context import IContextOpt, IContextCluster
from context import get_ctx
from flow import CTFGroup, CTFTestCase
from exptions import VarFail, VarAbort, CTFRuntimeException

__author__ = "673965587@qq.com"
__all__ = ["INTURN", "RANDOM", "CUSTOM", "parse_cluster", "ClusterGroup", "ClusterTestCase"]


# cluster标签下opt标签解释规则
MODELS = {
    "INTURN": 0b000001,  # 依次解释cluster下的opt标签
    "RANDOM": 0b000100,   # 随机解释cluster下的opt标签
    "CUSTOM": 0b010000,   # 自定义解释cluster下的opt标签
}


def _get_function_name():
    return inspect.stack()[1][3]


def _is_callable(instance):
    '''
    instance必须是一个callable对象
    :param instance: instance
    :return:
    '''
    if not callable(instance):
        raise VarAbort("{}必须是callable对象".format(instance))


def _get_run_pattern(pattern):
    '''
    获取cluster标签的运行模式
    :param pattern: cluster的exec属性值
    :return:
    '''
    rets = re.split(r'\s*\|\s*', pattern)
    _CUSTOM = None
    _cluster_pattern = 0
    for i, item in enumerate(rets):
        matches = re.split(r'\((\w+)\)', item)
        mod = matches[0]
        if mod in MODELS:
            # 运行模式或运算
            _cluster_pattern |= MODELS[mod]
            if len(matches) > 1:
                _CUSTOM = matches[1]
        else:
            raise CTFRuntimeException("Cluster标签exec属性值不支持:{0},目前只支持:{1}".format(mod,",".join(MODELS.keys())))
    return _cluster_pattern, _CUSTOM


def _get_arguments(*args, **kwargs):
    '''
    从字典中按设定规则得到参数列表。
    规则：以下划线和数字结尾的属性，返回按数字排序的参数列表
    :param args: 字段中排除的key
    :param kwargs: 需要检查的字典
    :return:
    '''
    try:
        if "ret" in kwargs:
            result = re.split(r"cluster=|,|opt=", kwargs["ret"])
            if len(result) < 4:
                raise CTFRuntimeException("opt参数引用错误,请按照cluster={0},opt={1}的格式传入字符串")
            else:
                pid, oid = int(result[1]), int(result[-1])
                # return get_opt_ret(pid,oid)

        _sorted_arguments = sorted([(k, v) for (k, v) in kwargs.items() if k not in args and k[-2] == '_'],
                                   key=lambda (k, v): k[-1])

        return zip(*_sorted_arguments)[-1] if _sorted_arguments else []
    except Exception, ex:
        raise VarAbort("参数解析出错：{}".format(str(ex)))


def parse_cluster(cluster):
    '''
    解析一组cluster操作。
    根据cluster的exec属性值选址解释的模式
    :param cluster: cluster标签
    :return:
    '''
    if type(cluster) is not IContextCluster:
        raise VarAbort("{}参数必须是{}".format('parse_cluster', IContextCluster.__name__))

    def _in_turn(cst):
        map(lambda opt: opt.exec_fnc(), cst.icontext_opts)

    def _random(cst):
        for i in range(len(cst.icontext_opts)):
            opt = cluster.icontext_opts[random.randint(0, len(cst.icontext_opts)-1)]
            opt.exec_fnc()

    def _custom(cst, fnc):
        cst.load_exec(fnc)
        ctx = get_ctx()
        ctx.alw("{}加载完成".format(cst))

    ptn, fnc = _get_run_pattern(cluster.exec_dsc)
    if ptn == MODELS['INTURN']:
        _in_turn(cluster)
    elif ptn == MODELS['RANDOM']:
        _random(cluster)
    elif ptn == MODELS['CUSTOM']:
        _custom(cluster, fnc)
    elif ptn == MODELS['CUSTOM'] | MODELS['INTURN']:
        _custom(cluster, fnc)
        _in_turn(cluster)
    elif ptn == MODELS['CUSTOM'] | MODELS['RANDOM']:
        _custom(cluster, fnc)
        _random(cluster)
    else:
        raise CTFRuntimeException("暂时不支持该种运行模式：{}".format(cluster.exec_dsc))


class ClusterGroup(CTFGroup):
    def __init__(self):
        super(ClusterGroup, self).__init__()
        self.ctx = get_ctx()
        # 获取用例下所有的cluster标签，按setup和cleanup形成对应的字典
        self._cluster_flow = {
            'setup': filter(lambda cluster: cluster.flow == 'setup', self.ctx.Record.icontext_clusters),
            'cleanup': filter(lambda cluster: cluster.flow == 'cleanup', self.ctx.Record.icontext_clusters)
        }

    def setup(self):
        map(lambda cluster: parse_cluster(cluster), self._cluster_flow['setup'])

    def cleanup(self):
        map(lambda cluster: parse_cluster(cluster), self._cluster_flow['cleanup'])


class ClusterTestCase(CTFTestCase):
    # 驱动var标签的模板
    def __init__(self):
        super(ClusterTestCase, self).__init__()
        self.ctx = get_ctx()
        # 获取用例下所有的cluster标签，按setup,run,verify,cleanup形成对应的字典
        self._cluster_flow = {
            'setup': filter(lambda cluster: cluster.flow == 'setup', self.ctx.Record.icontext_clusters),
            'run': filter(lambda cluster: cluster.flow == 'run', self.ctx.Record.icontext_clusters),
            'verify': filter(lambda cluster: cluster.flow == 'verify', self.ctx.Record.icontext_clusters),
            'cleanup': filter(lambda cluster: cluster.flow == 'cleanup', self.ctx.Record.icontext_clusters)
        }

    def setup(self):
        map(lambda cluster: parse_cluster(cluster), self._cluster_flow['setup'])

    def run(self):
        map(lambda cluster: parse_cluster(cluster), self._cluster_flow['run'])

    def verify(self):
        map(lambda cluster: parse_cluster(cluster), self._cluster_flow['verify'])

    def cleanup(self):
        map(lambda cluster: parse_cluster(cluster), self._cluster_flow['cleanup'])


if __name__ == "__main__":
    _dict = {"id": "1", "dsc": "2D分屏页面按钮点击", "func":"Automation.common.wait_and_click_element_2d",
             "argument_3": "test_argument3",
             "Component_2": "Button",
             "GameObject_1": "/2DPart/OverLayUI/TopLayer/recommendTabPanel/FrameBar/#container_tabBar/3DItemBar/#btn_btn" ,
             }
    # print _get_arguments(*["id","dsc","func"],**_dict)
    print _get_run_pattern('CUSTOM(wait_video)')
    print _get_run_pattern('INTURN')
