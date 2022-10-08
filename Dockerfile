FROM erpukraine/custom:odoo-15.0ee-erpu-latest

COPY --chown=odoo:odoo ./ /mnt/erpu-addons/
COPY --chown=odoo:odoo odoo.conf /etc/odoo/
