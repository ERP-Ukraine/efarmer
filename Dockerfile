FROM erpukraine/custom:odoo-13.0ee-erpu-latest

COPY --chown=odoo:odoo ./ /mnt/erpu-addons/
COPY --chown=odoo:odoo odoo.conf /etc/odoo/
