from odoo import models, fields

class CustomCalendarEvent(models.Model):
    _inherit = 'calendar.event'

    custom_field = fields.Char(string="Custom Field", help="This is an example field.")
    appointment_type_id = fields.Many2one('appointment.type', string="Appointment Type", ondelete="cascade")