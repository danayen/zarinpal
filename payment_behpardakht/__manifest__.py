# -*- coding: utf-8 -*-

{
    'name': 'Behpardakht Payment Acquirer',
    'category': 'Accounting/Payment Acquirers',
    'sequence': 350,
    'summary': 'Payment Acquirer: Behpardakht Implementation',
    'version': '1.0.1',
    'author': 'moein data processes',
    'website': 'https://www.moeindp.ir',
    'support': 'info@moeindp.ir',
    'description': """Behpardakht Payment Acquirer""",
    #'depends': ['payment_iran'],
    'depends': ['payment'],
    'external_dependencies': {
        'python': ['urllib3', 'zeep'],
    },
    'data': [
        # Views
        'views/payment_views.xml',
        # Templates
        'views/payment_behpardakht_templates.xml',
        # Data
        'data/payment_acquirer_data.xml',
    ],
    'post_init_hook': 'create_missing_journal_for_acquirers',
    'uninstall_hook': 'uninstall_hook',
    'application': True,
}
