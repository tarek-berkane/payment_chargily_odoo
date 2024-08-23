{
    'version': '0.1',
    'name': "Payment Provider: Chargily",
    'category': 'Accounting/Payment Providers',
    'sequence': 400,
    'summary': "A payment provider in Algeria.",
    'description': "Chargily Pay, a gateway that allows you to accept online payments with many payment methods in Algeria such as EDAHABIA and CIB cards. ", 
    'depends': [
        'payment',
    ],
    'data': [
        'views/payment_chargily_templates.xml',
        'views/payment_provider_views.xml',

        'data/payment_method_data.xml', 
        'data/payment_provider_data.xml', 
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}
