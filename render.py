# -*- coding: UTF-8 -*-
'''
Created on 20170816
@author: leochechen
@summary: html模板渲染
'''
import os
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
from libs.jinja2.environment import Template


DEFAULT_TEMPLATE = os.path.join(os.path.dirname(__file__), "template",
                                "report_template_2.html")


def load_template(template):
    """ Try to read a file from a given path, if file
        does not exist, load default one. """
    file = None
    try:
        if template:
            with open(template, "r") as f:
                file = f.read()
    except Exception as err:
        print "Error: Your Template wasn't loaded"
        print err
        print "Loading Default Template"
    finally:
        if not file:
            with open(DEFAULT_TEMPLATE, "r") as f:
                file = f.read()
        return file


def render_html(template, **kwargs):
    template_file = load_template(template)
    if template_file:
        template = Template(template_file)
        template.globals['os'] = os
        return template.render(**kwargs)

