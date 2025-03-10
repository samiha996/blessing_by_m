from odoo import models, fields, api,_
from odoo.exceptions import ValidationError

from datetime import datetime, time, timedelta
from dateutil.rrule import rrule, DAILY
import pytz


class AppointmentType(models.Model):
    _name = 'appointment.type'
    _description = 'Appointment Type'
    _inherit = ['image.mixin', 'mail.thread', 'mail.activity.mixin']
    
    
    
    name = fields.Char('Appointment Title', required=True, translate=True)
    active=fields.Boolean('Active',default=True)
    
    image_1920 = fields.Image("Background Image")
    category = fields.Selection([
        ('recurring', 'Recurring'),
        ('punctual', 'Punctual'),
        ('custom', 'Custom'),
        ('anytime', 'Any Time')],
        string="Category",default='recurring', store="True")
    
    appointment_duration = fields.Float('Duration', required=True, default=1.0)
    
    slot_creation_interval = fields.Float('Create a slot every ', required=True, default=1.0)
    
    min_schedule_hours = fields.Float('Schedule before (hours)', required=True, default=1.0)
    
    
    category_time_display = fields.Selection([
        ('recurring_fields', 'Available now'),
        ('punctual_fields', 'Within a date range')],
        string="Displayed category time fields", readonly=False)
    
    max_schedule_days = fields.Integer('Schedule not after (days)', required=True, default=15)
    
    # 'punctual' types are time-bound
    start_datetime = fields.Datetime('Start Datetime')
    end_datetime = fields.Datetime('End Datetime')
    
    #notebook slots dor weekdays and weekends
    slot_ids = fields.One2many('appointment.slot', 'appointment_type_id', 'Availabilities', copy=True)
    
    staff_user_ids = fields.Many2many(
        'res.users',
        'appointment_type_res_users_rel',
        domain="[('share', '=', False)]",
        string="Users", default=lambda self: self.env.user,
        store=True, readonly=False, tracking=True)
    
    
    
    @api.depends('start_datetime', 'end_datetime')
    def _compute_category(self):
        for appointment_type in self:
            appointment_type.category = 'punctual' if appointment_type.start_datetime or appointment_type.end_datetime else 'recurring'
    
    
    @api.constrains('appointment_duration')
    def _check_appointment_duration(self):
        for record in self:
            if not record.appointment_duration > 0.0:
                raise ValidationError(_('Appointment Duration should be higher than 0.00.'))
    
    
    
    def _get_recurring_slots(self, timezone):
        """Fetch only recurring slots and return slots based on the slot creation interval,
        while ensuring slots are not within the min_schedule_hours restriction and do not overlap with booked events.
        """

        if not self.active:
            return {}

        today = datetime.utcnow()

        try:
            requested_tz = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            requested_tz = pytz.utc

        now_utc = datetime.utcnow()
        now_local = requested_tz.localize(now_utc)  # Convert current UTC time to the user's timezone

        if self.category_time_display == "punctual_fields" and self.start_datetime and self.end_datetime:
            first_day = self.start_datetime.astimezone(requested_tz)
            last_day = self.end_datetime.astimezone(requested_tz)
        else:
            first_day = requested_tz.localize(today)
            last_day = requested_tz.localize(today + timedelta(days=self.max_schedule_days))

        recurring_slots = self.slot_ids.filtered(lambda slot: slot.slot_type == "recurring")
        if not recurring_slots:
            return {}

        slots_dict = {}

        for day in rrule(DAILY, dtstart=first_day.date(), until=last_day.date()):
            day_str = day.strftime("%Y-%m-%d")
            slots_for_day = recurring_slots.filtered(lambda s: int(s.weekday) == day.isoweekday())

            if not slots_for_day: 
                continue

            slots_dict[day_str] = []

            # ✅ Fetch booked calendar events for this day
            booked_events = self.env['calendar.event'].sudo().search([
                ('start', '>=', f"{day_str} 00:00:00"),
                ('start', '<', f"{day_str} 23:59:59"),
            ])
            booked_times = {event.start.astimezone(requested_tz).strftime("%H:%M") for event in booked_events}

            for slot in slots_for_day:
                interval = slot.appointment_type_id.appointment_duration or 1.0  # Default to 1 hour if not set
                min_schedule_hours = slot.appointment_type_id.min_schedule_hours or 0.0  # Default to 0 hours
                min_schedule_cutoff = now_local + timedelta(hours=min_schedule_hours)  # Calculate cutoff time

                slot_start_time = time(hour=int(slot.start_hour), minute=int((slot.start_hour % 1) * 60))
                slot_end_time = time(hour=int(slot.end_hour), minute=int((slot.end_hour % 1) * 60))

                current_time = requested_tz.localize(datetime.combine(day, slot_start_time))

                while current_time.time() < slot_end_time:
                    next_time = current_time + timedelta(hours=interval)

                    # ✅ Exclude slots that are within the min_schedule_hours restriction
                    if current_time < min_schedule_cutoff:
                        current_time = next_time
                        continue  # Skip this iteration
                    
                    if self.category_time_display == "punctual_fields" and current_time > last_day:
                        break
                    # ✅ Ensure we don't create slots that exceed the end time
                    if next_time.time() > slot_end_time:
                        break

                    # ✅ Exclude slots that are already booked
                    start_time_str = current_time.strftime('%H:%M')
                    if start_time_str in booked_times:
                        print(f"DEBUG: Slot {start_time_str} is already booked, skipping...")
                    else:
                        slot_time = f"{start_time_str} - {next_time.strftime('%H:%M')}"
                        slots_dict[day_str].append(slot_time)

                    current_time = next_time  # Move to next interval

        return slots_dict

    
    # def book_appointment(self, user_id, start_time, duration, partner_id):
    #     """
    #     Book an appointment and create a calendar event for the assigned staff user.
    #     """
    #     start_datetime = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
    #     end_datetime = start_datetime + timedelta(hours=duration)

    #     staff_user = self.staff_user_ids.filtered(lambda u: u.id == user_id)
    #     if not staff_user:
    #         raise ValueError("No staff user assigned for this appointment.")

    #     # Create the calendar event
    #     event_vals = {
    #         'name': self.name,
    #         'start': start_datetime,
    #         'stop': end_datetime,
    #         'allday': False,
    #         'user_id': staff_user.id,
    #         'partner_ids': [(4, partner_id)],  # Link the customer to the event
    #         'appointment_type_id': self.id,
    #     }

    #     event = self.env['calendar.event'].sudo().create(event_vals)
    #     return event.id
