# -*- coding=utf-8 -*-
# @author: leochechen
import sys
import xml.sax
from abc import ABCMeta, abstractmethod
from inspect import getmro
from itertools import groupby, chain
from ctf_local import get_weakref_local_variate
from exptions import *


def convert_str(x):
    '''
    返回编码为utf-8的string字符串
    :param x: 需要转换的unicode
    :return:
    '''
    if sys.version_info.major == 2:
        return x.encode('utf-8') if type(x) is unicode else x
    elif sys.version_info.major == 3:
        return x


def convert_uni(x):
    '''
    返回unicode的字符串
    :param x: 需要转换的string
    :return:
    '''
    if sys.version_info.major == 2:
        return x.decode("utf-8") if type(x) is str else x
    elif sys.version_info.major == 3:
        return x


class Stack(object):
    '''
    使用list构造的一个简单堆栈:先进后出
    '''
    def __init__(self):
        self.items = []

    def is_empty(self):
        return self.items == []

    def push(self, item):
        self.items.append(item)

    def pop(self):
        return None if len(self.items) == 0 else self.items.pop()

    def size(self):
        return len(self.items)

    def peek(self):
        return None if len(self.items) == 0 else self.items[-1]

    def clear(self):
        self.items = []


class Node(object):
    # XML节点公有方法抽象基类。每个节点都是一个多叉树
    __metaclass__ = ABCMeta

    tag = "Node"

    @abstractmethod
    def _rule_position_limited(self):
        '''
        位置限定规则。每个标签都有自己的位置限定,能存在于哪边，不能存在于哪里。
        :return:
        '''
        pass

    @abstractmethod
    def _rule_count_limited(self):
        '''
        数量限定规则。其子类标签的数量限定。
        :return:
        '''
        pass

    @abstractmethod
    def _rule_quote_limited(self):
        '''
        引用规则。百分号引用规则等.
        :return:
        '''
        pass

    @abstractmethod
    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    @abstractmethod
    def _rule_attributes_limited(self):
        '''
        属性限定规则。一定要有的属性名称
        :return:
        '''
        for attr, val in type(self).attrs.items():
            if attr in self._attributes:
                if val:
                    if self._attributes[attr] not in val:
                        raise VarmapException("{}['{}']的取值只能在{}之中".format(str(self), attr, str(val)))
            else:
                raise VarmapException("{}必须含有属性：{}".format(str(self), type(self).attrs.keys()))

    @abstractmethod
    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        :return:
        '''
        pass

    def _set_attributes_str_to_int(self, atr):
        if atr in self.attributes:
            try:
                self.attributes[atr] = int(self.attributes[atr])
            except ValueError:
                raise VarmapException("{}['{}']的取值必须是整数".format(str(self), atr))

    def _is_repetition_val(self, attr, cmp_list):
        '''
        检查是否存在重复的属性值。
        :param attr:  需要检查的属性名
        :param cmp_list:  groupby之后的分组
        :return:
        '''
        for key, group in cmp_list:
            if len(group) > 1:
                targets = "和".join([str(_) for _ in group])
                raise VarmapException("{}中存在{}={}重复".format(targets,attr,key))

    def _groupby_list(self, attr, clses):
        '''
        根据给定属性，根据其属性值分组返回分组列表
        :param attr:  属性
        :param clses:  需要进行分组的标签类
        :return:
        '''
        assert hasattr(clses, '__iter__')
        origin_list = [cld for cld in self.child if type(cld) in clses]
        origin_list.sort(key=lambda cld: cld.attributes[attr])
        groupby_list = [(name, list(group)) for name, group in groupby(origin_list, lambda cld: cld.attributes[attr])]
        self._is_repetition_val(attr, groupby_list)

    def _replace_per_symbol(self, grp):
        '''
        标签值如以%开头并且以%结尾则会替换成grp标签中rec对应key的值
        :param grp: grp标签类
        :return:
        '''
        left = self.value.find('%') + 1
        right = self.value.rfind('%')
        value = grp.key_to_val(self.value[left:right])
        if value is None:
            raise VarmapException("{0}中没有key={1}的rec标签".format(grp, self.value[left:right]))
        else:
            self.value = self.value[:self.value.find('%')] + value + self.value[self.value.rfind('%')+1:]

    def do_limit(self):
        '''
        执行规则限定。对于实例对象instance，_rule_开头的内部方法视为规则限定
        :return:
        '''
        # self._rule_position_limited()
        # self._rule_count_limited()
        # self._rule_value_limited()
        # self._rule_attributes_limited()
        # self._rule_attributes_limited()
        # self._rule_attributes_uniqueness_limited()
        for _method in dir(self):
            if callable(getattr(self, _method)) and _method.startswith('_rule_'):
                eval("self.{}()".format(_method))

    @classmethod
    def change_self(cls, node):
        '''
        遍历当前节点下的所有节点的逻辑抽象,并使用规则限定改变他们
        :param node: 当前节点实例对象
        :return:
        '''
        if not isinstance(node, Node):
            raise VarmapException("{}必须是{}的子类的实例对象".format(node, "<CTF Node structure>"))

        # 对自己执行规则限定
        node.do_limit()
        # 蔓延至孩子节点
        if node.has_child():
            for child in node.child:
                Node.change_self(child)

    @property
    def attributes(self):
        return self._attributes

    @attributes.setter
    def attributes(self, _atr_dic):
        if not type(_atr_dic) == dict:
            raise VarmapException("初始化标签属性的值必须是一个字典")

        _dic = {}
        for k, v in _atr_dic.iteritems():
            _dic.setdefault(convert_str(k), convert_str(v))
        self._attributes = _dic

    def __init__(self):
        # 标签属性
        self._attributes = {}
        # 节点的content
        self.value = ""
        # 树的深度
        self.deep = 0
        # 长度
        self.len = 0
        # 用例脚本实例
        self.userObject = None
        # 父亲节点
        self.parent = None
        # 第几个孩子
        self.which_child = 0
        # 孩子节点
        self.child = []
        # 标签名字
        self.name = "CTF标签<{}>".format(type(self).tag)

    def copy_self(self, parent):
        '''
        节点深拷贝
        :param parent: 拷贝后的节点的父亲节点
        :return:
        '''
        instance = type(self)()
        instance._attributes = self._attributes
        instance.value = self.value
        instance.deep = self.deep
        instance.len = self.len
        instance.userObject = self.userObject
        instance.parent = parent
        instance.which_child = self.which_child
        instance.child = [child.copy_self(instance) for child in self.child]
        instance.name = self.name
        return instance

    def del_self(self):
        '''
        从自己的父亲节点的孩子节点中删除自己
        :return:
        '''
        for child in self.child:
            child.del_self()
            self.child.remove(child)
        # print self
        return self

    def left_child(self):
        if self.has_left_child():
            return self.parent.child[self.which_child - 1]

    def right_child(self):
        if self.has_right_child():
            return self.parent.child[self.which_child + 1]

    def has_child(self):
        return len(self.child)

    def has_left_child(self):
        return self.parent and len(self.parent.child) and self.which_child - 1 >= 0 \
               and self.parent.child[self.which_child - 1]

    def has_right_child(self):
        return self.parent and len(self.parent.child) and self.which_child + 1 <= len(self.parent.child)-1 \
               and self.parent.child[self.which_child + 1]

    def is_self(self):
        return self.parent and self.parent.child[self.which_child] == self

    def is_root(self):
        return not self.parent

    def is_leaf(self):
        return not (len(self.child))

    def __repr__(self):
        return "{},<Object at id=0x{}>".format(str(self),id(self))

    def __str__(self):
        '''
        标签描述模板中必有属性列表中存在的属性
        :return:
        '''
        tag_dsc = " ".join(["{}={}".format(attr, self.attributes[attr])
                            for attr in type(self).attrs.keys() if attr in self.attributes])

        return "CTF标签<{} {}>".format(type(self).tag, tag_dsc)

    def __len__(self):
        return self.len


class Bug(Node):
    # Bug标签允许的属性列表
    attrs = {'status': ('新建', '进行中', '已解决', '反馈', '已关闭', '已拒绝')}
    # Bug标签模板
    template = "<bug name='node'></node>"
    # 标签
    tag = 'bug'

    def _rule_position_limited(self):
        '''
        位置限定规则。每个标签都有自己的位置限定,能存在于哪边，不能存在于哪里。
        :return:
        '''
        pass

    def _rule_count_limited(self):
        '''
        数量限定规则。其子类标签的数量限定。
        :return:
        '''
        pass

    def _rule_quote_limited(self):
        '''
        引用规则。百分号引用规则等.
        :return:
        '''
        pass

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则。一定要有的属性名称
        :return:
        '''
        pass

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        :return:
        '''
        pass


class Val(Node):
    # val标签允许的属性列表
    attrs = {}
    # val标签模板
    template = "<val>0</val>"
    # 标签
    tag = 'val'

    def __init__(self):
        super(Val, self).__init__()

    def _rule_position_limited(self):
        '''
        位置限定规则。val标签只能存在于recm标签或者include标签下
        :return:
        '''
        if type(self.parent) == Recm:
            pass
        else:
            raise VarmapException("{0}只能存在于{1}下".format(str(self),Recm.tag))

    def _rule_count_limited(self):
        '''
        数量限定规则。其子类标签的数量限定。
        :return:
        '''
        pass

    def _rule_quote_limited(self):
        '''
        引用规则。百分号引用规则等.
        :return:
        '''
        if type(self.value) == str and self.value.find('%') < self.value.rfind('%'):
            self._replace_per_symbol(VarMap().grp)

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则
        '''
        super(Val, self)._rule_attributes_limited()

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        :return:
        '''
        pass


class Rec(Node):
    # Rec标签允许的属性列表
    attrs = {'key': None}
    # Rec标签模板
    template = "<rec key='test'>...</rec>"
    # 标签
    tag = 'rec'

    def __init__(self):
        super(Rec, self).__init__()

    def _rule_position_limited(self):
        '''
        位置限定规则。rec标签能存在于var或者它的派生类标签下，也能存在于snippet标签下
        :return:
        '''
        if type(self.parent) not in (Var, Grp):
            raise VarmapException("{0}只能存在于{1}、{2}标签下".format(str(self), Var.tag, Grp.tag))

    def _rule_count_limited(self):
        '''
        数量限定规则。其子类标签的数量限定。
        :return:
        '''
        pass

    def _rule_quote_limited(self):
        '''
        引用规则。
        :return:
        '''
        if type(self.value) == str and self.value.find('%') < self.value.rfind('%'):
            self._replace_per_symbol(VarMap().Grp)

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则
        '''
        super(Rec, self)._rule_attributes_limited()

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        :return:
        '''
        pass


class Recm(Node):
    # Recm标签允许的属性列表
    attrs = {'key': None}
    # val标签模板
    template = "<recm key='test'>...</recm>"
    # 标签
    tag = 'recm'

    def __init__(self):
        super(Recm, self).__init__()

    def _rule_position_limited(self):
        '''
        位置限定规则。recm标签能存在于var或者它的派生类标签下，也能存在于opt标签下
        :return:
        '''
        if Var in getmro(type(self.parent)) or isinstance(self.parent, Opt):
            pass
        else:
            raise VarmapException("{}只能存在于{}、{}标签下".format(str(self), Var.tag, Grp.tag))

    def _rule_count_limited(self):
        '''
        数量限定规则。其子类标签的数量限定。
        :return:
        '''
        pass

    def _rule_quote_limited(self):
        '''
        引用规则。百分号引用规则等。
        :return:
        '''
        pass

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则.
        '''
        super(Recm, self)._rule_attributes_limited()

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        :return:
        '''
        pass

    def __getitem__(self, pid):
        return self.child[pid].value

    def __len__(self):
        return len(self.child)


class Var(Node):
    # 使用方式
    # <var set="组id" lvl="优先级id" vid="用例id" id="描述" permutation="rows"></var>

    # Var标签允许的属性列表
    attrs = {
        'set': None,
        'lvl': None,
        'vid': None,
        'id': None,
        # full：全部取值,pict：随机挑选一个值,rows：顺序取值 中的一个。目前只支持rows
        'permutation': ("full", "pict", "rows")
    }

    # 标签
    tag = 'var'

    def __init__(self):
        super(Var, self).__init__()
        self.period = 0

    def _rule_position_limited(self):
        '''
        位置限定规则。var标签只能存在于varmap标签下
        :return:
        '''
        if not isinstance(self.parent, VarMap):
            raise VarmapException("{}只能存在于{}标签下".format(str(self), VarMap.tag))

    def _rule_count_limited(self):
        '''
        数量限定规则。
        :return:
        '''
        pass

    def _rule_quote_limited(self):
        '''
        引用规则。百分号引用规则等.
        :return:
        '''
        pass

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则。
        '''
        # 属性名称限定
        super(Var, self)._rule_attributes_limited()

        # set,lvl, id属性值限定
        map(self._set_attributes_str_to_int, ['set', 'lvl', 'vid'])

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        1.var及其派生类标签下rec标签、recm标签的key必须唯一
        :return:
        '''
        self._groupby_list('key', [Rec, Recm])

    @property
    def Period(self):
        recms_set = set(map(lambda child: len(child), [child for child in self.child if type(child) == Recm]))
        if recms_set:
            if len(recms_set) > 1:
                raise VarmapException("{}中存在长度不一致的{}标签".format(str(self),Recm.tag))
            elif len(recms_set) == 1 and "permutation" in self.attributes and self.attributes["permutation"] == "rows":
                self.period = recms_set.pop()
        else:
            self.period = 1
        return self.period

    @Period.setter
    def Period(self, val):
        assert type(val) == int
        self.period = val

    def key_to_val(self, key):
        '''
        根据key查找对应的值
        :param key: key
        :return:
        '''
        for child in self.child:
            if type(child) == Rec and key == child.attributes["key"]:
                return child.value


class Arg(Node):
    # Arg标签允许的属性列表
    # <arg>...</arg>
    attrs = {}
    # 标签
    tag = 'arg'

    def _rule_position_limited(self):
        '''
        位置限定规则。每个标签都有自己的位置限定,能存在于哪边，不能存在于哪里。
        :return:
        '''
        if not type(self.parent) == Opt:
            raise VarmapException("{}只能存在于{}下".format(str(self), Opt.tag))

    def _rule_count_limited(self):
        '''
        数量限定规则。其子类标签的数量限定。
        :return:
        '''
        pass

    def _rule_quote_limited(self):
        '''
        引用规则。
        :return:
        '''
        if type(self.value) == str and self.value.find('%') < self.value.rfind('%'):
            self._replace_per_symbol(VarMap().Grp)

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则。一定要有的属性名称
        :return:
        '''
        pass

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        :return:
        '''
        pass


class Opt(Node):
    # Opt标签允许的属性列表
    # <opt dsc='操作描述' fnc="解释操作的函数" />
    attrs = {
        'id': None,
        'fnc': None
    }
    # opt标签模板
    # 标签
    tag = 'opt'

    def __init__(self):
        super(Opt, self).__init__()

    def _rule_position_limited(self):
        '''
        位置限定规则。opt标签只能存在于cluster标签下
        :return:
        '''
        if not type(self.parent) == Cluster:
            raise VarmapException("{}只能存在于{}标签下".format(str(self), Cluster.tag))

    def _rule_count_limited(self):
        '''
        数量限定规则。opt标签下允许存在recm标签，但是要求不同recm标签的长度一致，并且长度和opt父类的cluster标签的repetition的属性值相等
        :return:
        '''
        recms_set = set(map(lambda child: len(child), [child for child in self.child if type(child) == Recm]))
        if recms_set:
            if len(recms_set) > 1:
                raise VarmapException("{}中存在长度不一致的{}标签".format(str(self),Recm.tag))
            elif len(recms_set) == 1:
                recms_size = recms_set.pop()
                if self.parent.attributes["repetition"] != recms_size:
                    raise VarmapException("{}中repetition属性值和下面的{}标签的长度不一致".format(str(self.parent),Recm.tag))

    def _rule_quote_limited(self):
        '''
        引用规则。特殊符号%引用规则：
        :return:
        '''
        pass

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则
        '''
        #属性名称限定
        super(Opt, self)._rule_attributes_limited()

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。opt标签下的rec标签、recm标签的key必须唯一
        :return:
        '''
        self._groupby_list('key', [Rec, Recm])


class Cluster(Node):
    # <cluster dsc="操作集合描述" module="操作集合默认模块地址" exec="解释脚本"  flow="CTF用例流程步骤">...</cluster>
    # Cluster标签允许的属性列表
    attrs = {
            "id": None,
            'module': None,
            'exec': None,
            'flow': ("setup", "run", "verify", "cleanup"),
    }
    # 标签
    tag = 'cluster'

    def __init__(self):
        super(Cluster, self).__init__()

    def _rule_position_limited(self):
        '''
        位置限定规则。cluster标签能存在于var,grp标签下
        :return:
        '''
        if type(self.parent) not in (Var, Grp):
            raise VarmapException("{}只能存在与{}、{}标签下".format(str(self), Var.tag, Grp.tag))

    def _rule_count_limited(self):
        '''
        数量限定规则。其子类标签的数量限定
        :return:
        '''
        pass

    def _rule_quote_limited(self):
        '''
        引用规则。百分号引用规则等.
        :return:
        '''
        pass

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则
        '''
        # 一、属性名称限定
        super(Cluster, self)._rule_attributes_limited()

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        :return:
        '''
        pass


class Grp(Var):
    # <grp cls="解释脚本位置" permutation="用例取值方式目前只支持row">...</grp>'
    # grp标签允许的属性列表
    attrs = {
            # full：全部取值,pict：随机挑选一个值,rows：顺序取值 中的一个。目前只支持rows
            'permutation': ("full", "pict", "rows")
    }

    # 标签
    tag = 'grp'

    def __init__(self):
        super(Grp, self).__init__()

    def _rule_position_limited(self):
        '''
        位置限定规则。每个标签都有自己的位置限定,能存在于哪边，不能存在于哪里。
        :return:
        '''
        if not type(self.parent) == VarMap:
            raise VarmapException("{}只能存在于{}标签下".format(str(self), VarMap.tag))

    def _rule_count_limited(self):
        '''
        数量限定规则。
        :return:
        '''
        pass

    def _rule_quote_limited(self):
        '''
        引用规则。百分号引用规则等.
        :return:
        '''
        super(Grp, self)._rule_quote_limited()

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        super(Grp, self)._rule_value_limited()

    def _rule_attributes_limited(self):
        '''
        属性限定规则
        '''
        # 属性名称限定
        super(Grp, self)._rule_attributes_limited()

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。var及其派生类标签下的cluster标签id必须唯一
        :return:
        '''
        super(Grp, self)._rule_attributes_uniqueness_limited()


class VarMap(Node):
    # VarMap是一个多叉树查找树.

    # VarMap标签允许的属性列表
    attrs = {
        'id': "ctf-testcases",
        "xmlns": "https://github.com/leoche666",
    }

    # 标签
    tag = 'varmap'

    def __new__(cls, *args, **kwargs):
        worker = get_weakref_local_variate('worker')
        if worker.get_varmap is not None:
            return worker.get_varmap
        else:
            self = object.__new__(cls, *args, **kwargs)
            worker.get_varmap = self
            # __init__ 初始化
            super(VarMap, self).__init__()
            # grp
            self._grp = None
            # vars
            self._vars = []
            return self

    def _rule_position_limited(self):
        '''
        位置限定规则。varmap标签只能是根节点
        :return:
        '''
        if self.parent is not None:
            raise VarmapException("{}只能是根节点".format(str(self)))

    def _rule_count_limited(self):
        '''
        数量限定规则。一张数据配置文件中grp标签数量有且仅有一个。
        :return:
        '''
        grps = [child for child in self.child if type(child) == Grp]
        if len(grps) == 0:
            raise VarmapException("{}标签中必须包含一个{}标签".format(VarMap.tag, Grp.tag))
        elif len(grps) > 1:
            raise VarmapException("{}标签中有且仅有一个{}标签".format(VarMap.tag, Grp.tag))
        else:
            self._grp = grps[0]

    def _rule_quote_limited(self):
        '''
        引用规则。百分号引用规则等.
        :return:
        '''
        pass

    def _rule_value_limited(self):
        '''
        取值规则。
        :return:
        '''
        pass

    def _rule_attributes_limited(self):
        '''
        属性限定规则
        '''
        super(VarMap, self)._rule_attributes_limited()

    def _rule_attributes_uniqueness_limited(self):
        '''
        节点下的子标签属性唯一限定规则。
        1. varmap标签下的var标签vid必须唯一
        :return:
        '''
        self._get_all_var()
        sorted_vars = sorted(self._vars, key=lambda cld: int(cld.attributes['vid']), reverse=False)
        vars_uniq = [(name, list(group)) for name, group in groupby(sorted_vars, lambda cld:cld.attributes['vid'])]
        self._is_repetition_val('vid', vars_uniq)

    def _get_all_var(self):
        '''
        取出当前节点下的所有var标签
        :param node: 当前节点实例对象
        :return:
        '''
        for cld in self.child:
            if type(cld) == Var:
                self._vars.append(cld)

    @property
    def grp(self):
        return self._grp

    @property
    def vars(self):
        return self._vars

    def pretreatment(self):
        '''
        预处理
        :return:
        '''
        # 递归预处理一些XML的语法规则。每个标签都有自己的语法规则，规则函数都是以_rule_为前缀的方法
        Node.change_self(self)

    def _pick_redundant_from_list(self, _list):
        '''
        从列表中挑选出重复元素，并返回重复项的（元素）列表
        :param _list: 目标列表
        :return:
        '''
        keys = [item[-1] for item in _list]
        return [_list[i] for i in range(len(keys)) if keys.count(keys[i]) > 1]


class ParseHTMLTeamplate(xml.sax.ContentHandler):
    def __init__(self):
        xml.sax.ContentHandler.__init__(self)
        self._tag_structure_dict = dict(self.get_supports_list())
        self.stack = Stack()
        self.varmap = None

    def get_supports_list(self):
        current_module = sys.modules[__name__]
        support_list = []
        for key in dir(current_module):
            instance = getattr(current_module, key)
            if callable(instance) and issubclass(instance, Node):
                support_list.append((instance.tag, instance))
        return support_list

    def startDocument(self):
        self.varmap = VarMap()

    def endDocument(self):
        self.varmap.pretreatment()

    def startElement(self, tag, attributes):
        if tag in self._tag_structure_dict:
            cls = self._tag_structure_dict[tag]
            instance = self.varmap if cls is VarMap else cls()
            instance.attributes = attributes._attrs
            instance.deep = self.stack.size()
            instance.parent = self.stack.peek()
            if self.stack.peek() is not None:
                instance.which_child = self.stack.peek().len
                self.stack.peek().child.append(instance)
                self.stack.peek().len += 1
            self.stack.push(instance)
        else:
            raise VarmapParseException("Cann't support the tag : ", tag)

    def characters(self, content):
        elem = self.stack.peek()
        if elem.__class__.__name__ == 'Rec' \
                or elem.__class__.__name__ == 'Val' \
                or elem.__class__.__name__ == 'Arg':
                elem.value = content

    def endElement(self, tag):
        self.stack.pop()
        '''
        for child in elem.child:
            elem.len += 1
        if child.__class__.__name__ == 'Rec':
            elem.mapping.append([child.attributes['key'],child.value])
        elif child.__class__.__name__ == 'Recm':
            elem.mapping.append([child.attributes['key'],child.child])
       '''

    @classmethod
    def load_html(cls, f):
        handler = cls()
        xml.sax.parseString(f, handler)
        return handler.varmap
