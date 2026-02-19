=====================
Integration Queue Job
=====================

Overview
--------
The **Integration Queue Job** module is a lightweight fork of the OCA `queue_job` addon.
It provides background job processing for Odoo, optimized to work seamlessly with
VentorTech's e-commerce connectors (`https://ecosystem.ventor.tech/ <https://ecosystem.ventor.tech/>`_).

This fork keeps only the features needed for our connectors, simplifying the codebase
while remaining compatible with the original `queue_job`. You can safely use either
module with our connectors.

Why this fork?
--------------
- Focused and simplified job queue system (reduced complexity).
- Fully compatible with VentorTech e-commerce connectors.
- Preserves compatibility with the original OCA `queue_job`.
- Easier maintenance across Odoo versions.

Usage Example
-------------
You can postpone method calls to be executed asynchronously:

.. code:: python

   class MyModel(models.Model):
       _name = 'my.model'

       def my_method(self, a, k=None):
           _logger.info("executed with a=%s, k=%s", a, k)

   class MyOtherModel(models.Model):
       _name = 'my.other.model'

       def button_do_stuff(self):
           # This will run in the background
           self.env['my.model'].with_delay().my_method('a', k=2)

Release Notes
-------------
* 1.0.3 (2025-11-10)
    - Fixed create method to handle empty vals_list (Odoo tests compatibility).

* 1.0.2 (2025-10-28)
    - Fixed database lock issues.

* 1.0.1 (2025-09-23)
    - Small fixes and improvements.

* 1.0.0 (2025-09-16)
    - Initial release (forked from OCA/queue, cleaned up for VentorTech connectors).

Credits
-------
**Original Authors (queue_job):**
- Camptocamp
- ACSONE SA/NV
- Odoo Community Association (OCA)

**Maintained Fork (integration_queue_job):**
- VentorTech (https://ventor.tech)

License
-------
LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html)
