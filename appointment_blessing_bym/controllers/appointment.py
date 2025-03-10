from datetime import datetime, timedelta
from pytz import all_timezones 
import json
import math

import pytz
from odoo import http
from odoo.http import request

class AppointmentWebsite(http.Controller):

    @http.route(['/appointment', '/appointment/page/<int:page>'], type='http', auth='public', website=True)
    def list_appointments(self, page=1, **kwargs):
        Appointments = request.env['appointment.type'].sudo()
        total_appointments = Appointments.search_count([])

        
        per_page = 4  # Number of appointments per page
        total_pages = math.ceil(total_appointments / per_page)
        offset = (page - 1) * per_page

        appointments = Appointments.search([], limit=per_page, offset=offset)

        pager = request.website.pager(
            url="/appointment",
            total=total_appointments,
            page=page,
            step=per_page
        )

        return request.render("appointment_blessing_bym.appointment_list_page", {
            'appointments': appointments,
            'pager': pager
        })

    @http.route('/appointment/<int:appointment_id>', type='http', auth='public', website=True)
    def appointment_details(self, appointment_id, **kwargs):
        appointment = request.env['appointment.type'].sudo().browse(appointment_id)
        if not appointment.exists():
            return request.not_found()

        timezones = all_timezones  
        return request.render("appointment_blessing_bym.appointment_detail_page", {
            'appointment': appointment,
            'timezones':timezones,
        })
        
    @http.route('/appointment/get_slots', type='json', auth="public", methods=['POST'])
    def get_slots(self, **kwargs):
        """ Return available slots for a given appointment type and date, but exclude booked times. """
        appointment_type_id = kwargs.get('appointment_type_id')
        selected_date = kwargs.get('selected_date')

        print(f"DEBUG: Checking slots for Date: {selected_date}")

        if not appointment_type_id or not selected_date:
            return {'error': 'Missing required parameters'}

        appointment_type = request.env['appointment.type'].sudo().browse(appointment_type_id)
        if not appointment_type.exists():
            return {'error': 'Invalid appointment type'}

        # ✅ Get all available slots for the selected date
        available_slots = appointment_type._get_recurring_slots('UTC')
        slots_for_date = available_slots.get(selected_date, [])

        print(f"DEBUG: Slots before filtering booked ones -> {slots_for_date}")

        # ✅ Find booked slots in `calendar.event`
        booked_events = request.env['calendar.event'].sudo().search([
            ('start', '>=', f"{selected_date} 00:00:00"),
            ('start', '<', f"{selected_date} 23:59:59"),
        ])

        # Extract booked times in "HH:MM" format
        booked_times = {event.start.strftime("%H:%M") for event in booked_events}

        # ✅ Remove booked slots from the available ones
        remaining_slots = [slot for slot in slots_for_date if slot.split(" - ")[0] not in booked_times]

        print(f"DEBUG: Available slots after filtering -> {remaining_slots}")

        return {'slots': remaining_slots}


    @http.route('/appointment/get_available_dates', type='json', auth="public", methods=['POST'])
    def get_available_dates(self, **kwargs):
        """ Return a list of dates that have available slots """
        appointment_type_id = kwargs.get('appointment_type_id')

        if not appointment_type_id:
            return {'error': 'Missing appointment type ID'}

        appointment_type = request.env['appointment.type'].sudo().browse(appointment_type_id)
        if not appointment_type.exists():
            return {'error': 'Invalid appointment type'}

        available_slots = appointment_type._get_recurring_slots('UTC')

        available_dates = list(available_slots.keys())  # Extract available dates
        print(f"Available dates: {available_dates}")
        
        return {'dates': available_dates}

    
    @http.route('/appointment/<int:appointment_id>/booking', type='http', auth='public', website=True)
    def appointment_booking_form(self, appointment_id, **kwargs):
        """ Render the booking form with optional pre-filled hidden fields for date and time """
        
        appointment = request.env['appointment.type'].sudo().browse(appointment_id)
        if not appointment.exists():
            return request.not_found()
        
       
        selected_date = kwargs.get('date', '')
        appointment_time = kwargs.get('appointment_time', '')  
        timezone = kwargs.get('timezone', 'UTC')
        
        print(f"Received Date: {selected_date}, Time: {appointment_time}")  
        
        try:
            user_tz = pytz.timezone(timezone)  # Convert to user-selected timezone
            datetime_str = f"{selected_date} {appointment_time}"
            appointment_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")

            # Convert from UTC to the selected timezone
            appointment_datetime_local = pytz.utc.localize(appointment_datetime).astimezone(user_tz)

            formatted_time = appointment_datetime_local.strftime("%H:%M")  # Show only HH:MM in user timezone

            print(f"DEBUG: Converted Time in {timezone} -> {formatted_time}")

        except Exception as e:
            print(f"ERROR: Time conversion failed -> {e}")
            formatted_time = appointment_time

        return request.render("appointment_blessing_bym.appointment_booking_form", {
            'appointment': appointment,
            'date': selected_date,
            'appointment_time': formatted_time,
            'timezone': timezone,
        })



    @http.route('/appointment/submit', type='http', auth='public', website=True, methods=['POST'])
    def submit_appointment(self, **post):
        """ Process the appointment booking and create an event """
        
        name = post.get('name')
        email = post.get('email')
        phone = post.get('phone')
        selected_date = post.get('date')  
        appointment_time = post.get('appointment_time')
        
        print('app_time .....' , appointment_time)
        timezone = post.get('timezone')
        appointment_id = post.get('appointment_id')
        
        appointment = request.env['appointment.type'].sudo().browse(int(appointment_id))
        duration= appointment.appointment_duration
        
        
        print('appointment duration ...',duration)
        print('selected time ............', appointment_time) 

        if not (name and email and phone and selected_date and appointment_time):
            return request.redirect('/appointment/booking?error=missing_fields')

        try:
           
            print(f"Received Date: {selected_date}, Time: {appointment_time}")

            
            # if " - " in selected_time_value:
            #     start_time = selected_time_value.split(" - ")[0].strip()
            # else:
            #     start_time = selected_time_value.strip()
            # start_time = "09:00"
            
            try:
                user_tz = pytz.timezone(timezone)
            except pytz.UnknownTimeZoneError:
                user_tz = pytz.utc  # Default to UTC if the timezone is invalid

            
            local_datetime_str = f"{selected_date} {appointment_time}"
            local_datetime = datetime.strptime(local_datetime_str, "%Y-%m-%d %H:%M")

            
            local_datetime = user_tz.localize(local_datetime)

           
            utc_datetime = local_datetime.astimezone(pytz.utc)
            print(f"UTC DateTime: {utc_datetime}")
            
            naive_utc_datetime = utc_datetime.replace(tzinfo=None)
            
            datetime_str = f"{selected_date} {appointment_time}"
            print(f"Parsed DateTime String: {datetime_str}")

            
            appointment_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
            print(f"Converted DateTime: {appointment_datetime}")

            admin_user = request.env['res.users'].sudo().browse(2)  # Replace 2 with actual admin ID if needed
            admin_partner = admin_user.partner_id 
            
            partner = request.env['res.partner'].sudo().search([('email', '=', email)], limit=1)
            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': name,
                    'email': email,
                    'phone': phone,
                })
                
            request.env['calendar.event'].sudo().create({
                'name': f"Appointment with {name}",
                'start': naive_utc_datetime,
                'stop': naive_utc_datetime + timedelta(hours=duration),  # Default 1-hour duration
                'partner_ids': [(4, partner.id),(4, admin_partner.id)], # Add the admin as a follower
                'description': f"Appointment booked by {name}, Contact: {phone}, Email: {email},Timezone: {timezone}",
            })

            return request.redirect('/appointment/confirmation')

        except ValueError as e:
            print(f"Error parsing date/time: {e}")  
            return request.redirect('/appointment/booking?error=invalid_time_format')
