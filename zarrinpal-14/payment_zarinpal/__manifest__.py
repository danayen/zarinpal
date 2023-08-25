{
    'name': 'ZarinPal Payment Acquirer',
    'category': 'Accounting/Payment Acquirers',
    'sequence': 386,
    'summary': 'Payment Acquirer: ZarinPal Payment Implementation',
    'version': '14.0.0.0.1.210817',
    'description': """ZarinPal Payment Acquirer""",
    'depends': ['l10n_ir_payment'],
    'data': [
        'views/payment_views.xml',
        'views/payment_zarinpal_templates.xml',
        'data/payment_acquirer_data.xml',
    ],
    'application': True,
    'post_init_hook': 'create_missing_journal_for_acquirers',
    'uninstall_hook': 'uninstall_hook',
}
