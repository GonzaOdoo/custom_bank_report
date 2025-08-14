# -*- coding: utf-8 -*-
{
    'name': "Reporte banco personalizado",

    'summary': """
        Genera un reporte de conciliación bancaria personalizado""",

    'description': """
        Este módulo permite generar un reporte de conciliación bancaria personalizado
        que incluye un historial de reportes y la posibilidad de seleccionar el diario contable.
        Permite a los usuarios gestionar y visualizar la información de conciliación bancaria de manera eficiente.
    """,

    'author': "GonzaOdoo",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['account_accountant'],
    'assets': {
        'web.assets_backend': [
            'custom_bank_report/static/src/*',
        ],
    },
    # always loaded
    "data": ["security/ir.model.access.csv",
             "views/report_views.xml",
            ],
}
