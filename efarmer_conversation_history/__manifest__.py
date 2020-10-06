{
    'name': 'Conversation History, eFarmer',

    'version': '1.4',
    'category': 'Other',
    'author': 'ERP Ukraine',
    'website': 'https://erp.co.ua',
    'support': 'support@erp.co.ua',
    'license': 'OPL-1',
    'auto_install': False,
    'installable': True,
    'application': True,

    'demo': [],

    'depends': [
        'mail',
        'crm',
        'helpdesk',
    ],

    'data': [
        'views/mail_message_views.xml',
        'views/efarmer_conversation_history_menus.xml',
    ],
}
