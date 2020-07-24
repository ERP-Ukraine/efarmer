Leads From External Websites
============================

Put the script (from the **/extwebsite/client.js** endpoint) on a website.

There is a **External Website Forms** tab in the **CRM > Configuration** dropdown.

Create a new record per form. Set form ID and referrer url there. Then ...

* It's necessary to map technical form fields ('name' attribute in the input e.g.) to the Odoo ones.
* (Optionally) tags can be added: if the website field has the value, then the tag will be set.
* (Optionally) you can pin a team for the form leads.

How to configure a form?
========================

Form ID is an alphanumeric. You can find it in the hidden atribute of the target form. E.g.:

.. code-block:: HTML

    <input type="hidden" name="form_id" value="w8b8l1b1">

The form ID is `w8b8l1b1` here.

The referrer is a path to your form. Just open a page with the form
and copy the url (without params and hash) e.g.: `https://www.example.com/form1/`.

ACL
===

You should be in the **Manage External Website Leads** group to configure external forms.
