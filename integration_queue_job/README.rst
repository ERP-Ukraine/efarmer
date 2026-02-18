===============================
Integration Job Queue
===============================

This module is a **fork of OCA's `queue_job`**
(https://github.com/OCA/queue/tree/18.0/queue_job).

It provides a background job queue for Odoo, used to run asynchronous
tasks outside of normal user transactions.

Why this fork?
==============

We created this fork to offer an **alternative that is simpler and
lighter**, focusing on exactly what is needed for our
`integration_*` e-commerce connectors
(https://ecosystem.ventor.tech/).

Many of our customers don't need the full range of advanced features
from the original project. This fork provides a streamlined version that
is easier to use and maintain, while remaining compatible with our
connectors.

The original `queue_job` module is powerful and feature-rich, and our
connectors work fully with it as well.

Usage example
=============

Postpone any method call with ``with_delay()``:

.. code:: python

   class MyModel(models.Model):
       _name = "my.model"

       def my_method(self, value):
           _logger.info("Executed with value: %s", value)

   class MyOtherModel(models.Model):
       _name = "my.other.model"

       def button_do_stuff(self):
           self.env["my.model"].with_delay(priority=10).my_method("Hello")

In the above snippet, the call to ``my_method("Hello")`` is not executed
immediately but stored as a background job, to be processed by the job
runner.

Credits
=======

- Original authors: ACSONE SA/NV, Camptocamp SA, Odoo Community Association (OCA)  
- Fork & modifications: © 2025 VentorTech R&D (https://ventor.tech)  
- License: LGPL-3.0-or-later  
