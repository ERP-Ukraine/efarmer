# Copyright 2021 VentorTech OU
# See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    cr.execute('ALTER TABLE IF EXISTS "printnode_workstation" RENAME COLUMN "uuid" TO "name"')
