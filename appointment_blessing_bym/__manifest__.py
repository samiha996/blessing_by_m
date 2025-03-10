{
    'name': 'Custom Appointment',
    'version': '1.0',
    'category': 'appointment',
    'summary': 'A simple module inheriting Odoo Calendar',
    'depends': ['base','calendar'],
    'data': [
        'security/ir.model.access.csv',
        'views/base_menu.xml',
        'views/calendar_view.xml',
        'views/appointment_type_view.xml',
        'views/appointment_list_page.xml',
        'views/appointment_calendar_template.xml',
        'views/appointment_booking_form.xml',
        'views/appointment_confirmation.xml',
    ],
    'assets': {
    'web.assets_frontend': [
        'https://code.jquery.com/jquery-3.6.0.min.js',
        'appointment_blessing_bym/static/src/css/appointment_calendar.css',
        'appointment_blessing_bym/static/src/css/appointment_calendar.css',
        ],
    },

    'installable': True,
    'application': True,
}
