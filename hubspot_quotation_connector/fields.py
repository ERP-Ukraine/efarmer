# -*- coding: UTF-8 -*-
# Copyright 2023 Solvve, Inc. <sales@solvve.com>

from odoo.fields import Integer


class BigInteger(Integer):
    column_type = ('int8', 'int8')
