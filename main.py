import time
from datetime import datetime, timedelta, time as tm
import json
import module_wifi_sprinkler
from threading import Thread
from flask import *
import logging
from flask_socketio import SocketIO, send
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import PrimaryKeyConstraint
from flask_apscheduler import APScheduler

# Create flask app and global pi 'ws' object.
app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')
logging.getLogger('socketio').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)

# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////root/WifiApp/wifi_data.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wifi_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# app.config['SQLALCHEMY_ECHO'] = True

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

job_id = 0

db = SQLAlchemy(app)

################################## DB Classes ############################################################

class Zone(db.Model):
	__tablename__ = 'Zone'

	zone_id = db.Column(db.Integer, primary_key=True)
	description = db.Column(db.String(120), unique=False, nullable=True)
	enabled = db.Column(db.Boolean)
	program_zones = db.relationship('Program_Zones', backref='zone')

class Program(db.Model):
	__tablename__ = 'Program'

	program_id = db.Column(db.Integer, primary_key=True)
	description = db.Column(db.String(120), unique=False, nullable=True)
	enabled = db.Column(db.Boolean)
	program_zones = db.relationship('Program_Zones', backref='program', cascade="all, delete-orphan")
	program_run = db.relationship('Program_Run', backref='program', cascade="all, delete-orphan")
	program_schedule = db.relationship('Program_Schedule', backref='program', cascade="all, delete-orphan")
	program_adjustment = db.relationship('Program_Adjustment', backref='program', cascade="all, delete-orphan")
	program_restriction = db.relationship('Program_Restriction', backref='program', cascade="all, delete-orphan")

class Program_Zones(db.Model):
	__tablename__ = 'Program_Zones'

	__table_args__ = (
		PrimaryKeyConstraint('zone_id', 'program_id'),
	)
	zone_id = db.Column(db.Integer, db.ForeignKey('Zone.zone_id'), nullable=False)
	program_id = db.Column(db.Integer, db.ForeignKey('Program.program_id'), nullable=False)
	run_time = db.Column(db.Integer, unique=False)

class Program_Zones_History(db.Model):
	__tablename__ = 'Program_Zones_History'
	__table_args__ = (
		PrimaryKeyConstraint('zone_id', 'program_id', 'zone_run_timestamp'),
	)

	zone_id = db.Column(db.Integer, db.ForeignKey('Zone.zone_id'), nullable=False)
	program_id = db.Column(db.Integer, db.ForeignKey('Program.program_id'), nullable=False)
	zone_run_timestamp = db.Column(db.DateTime, unique=False, primary_key=True, default=datetime.utcnow)
	zone_run_duration = db.Column(db.Integer, unique=False)
	completion = db.Column(db.Boolean)

class Program_Run(db.Model):
	__tablename__ = 'Program_Run'
	__table_args__ = (
		PrimaryKeyConstraint('program_id', 'start_time'),
	)

	program_id = db.Column(db.Integer, db.ForeignKey("Program.program_id"), primary_key=True)
	start_time = db.Column(db.DateTime, unique=False, primary_key=True, default=datetime.now)
	last_run = db.Column(db.DateTime, unique=False)

class Schedule(db.Model):

	__tablename__ = 'Schedule'
	schedule_id = db.Column(db.Integer, primary_key=True)
	day_interval = db.Column(db.Integer, unique=False)
	description = db.Column(db.String(120), unique=False, nullable=False)
	start_date = db.Column(db.DateTime, unique=False, default=datetime.now)
	end_date = db.Column(db.DateTime, unique=False, default=datetime.now)
	enabled = db.Column(db.Boolean)
	program_schedule = db.relationship('Program_Schedule', backref='schedule', cascade="all, delete-orphan")

class Program_Schedule(db.Model):
	__tablename__ = 'Program_Schedule'

	__table_args__ = (
		PrimaryKeyConstraint('program_id', 'schedule_id'),
	)
	program_id = db.Column(db.Integer, db.ForeignKey("Program.program_id"), primary_key=True)
	schedule_id = db.Column(db.Integer, db.ForeignKey("Schedule.schedule_id"), primary_key=True)

class Restriction(db.Model):

	__tablename__ = 'Restriction'
	restriction_id = db.Column(db.Integer, primary_key=True)
	restriction_type = db.Column(db.String(20), unique=False, nullable=False)
	restriction_value = db.Column(db.String(20), unique=False, nullable=True)
	description = db.Column(db.String(120), unique=False, nullable=False)
	start_date = db.Column(db.DateTime, unique=False, nullable=True, default=datetime.now)
	end_date = db.Column(db.DateTime, unique=False, nullable=True, default=datetime.now)
	start_range = db.Column(db.Float, unique=False, nullable=True)
	end_range = db.Column(db.Float, unique=False, nullable=True)
	allow_disallow_indicator = db.Column(db.Boolean)
	enabled = db.Column(db.Boolean)
	program_restriction = db.relationship('Program_Restriction', backref='restriction', cascade="all, delete-orphan")

class Program_Restriction(db.Model):
	__tablename__ = 'Program_Restriction'
	__table_args__ = (
		PrimaryKeyConstraint('program_id', 'restriction_id'),
	)
	program_id = db.Column(db.Integer, db.ForeignKey("Program.program_id"), primary_key=True)
	restriction_id = db.Column(db.Integer, db.ForeignKey("Restriction.restriction_id"), primary_key=True)

class Adjustment(db.Model):

	__tablename__ = 'Adjustment'
	adjustment_id = db.Column(db.Integer, primary_key=True)
	adjust_value = db.Column(db.Integer, unique=False)
	description = db.Column(db.String(120), unique=False, nullable=False)
	start_date = db.Column(db.DateTime, unique=False, default=datetime.now)
	end_date = db.Column(db.DateTime, unique=False, default=datetime.now)
	enabled = db.Column(db.Boolean)
	program_adjustment = db.relationship('Program_Adjustment', backref='adjustment', cascade="all, delete-orphan")

class Program_Adjustment(db.Model):
	__tablename__ = 'Program_Adjustment'

	__table_args__ = (
		PrimaryKeyConstraint('program_id', 'adjustment_id'),
	)
	program_id = db.Column(db.Integer, db.ForeignKey("Program.program_id"), primary_key=True)
	adjustment_id = db.Column(db.Integer, db.ForeignKey("Adjustment.adjustment_id"), primary_key=True)

##############################################################################################


##############################################################################################
#            Flask custom functions, globals and filters
##############################################################################################

ws = module_wifi_sprinkler.WifiSprinkler()

def isAllowedTime(StartTime, EndTime, ProgramStartTime, AllowDisallow):
	if AllowDisallow:
		return ProgramStartTime.time() >= StartTime.time() and ProgramStartTime.time() <= EndTime.time()
	else:
		return (ProgramStartTime.time() < StartTime.time() and ProgramStartTime.time() < EndTime.time()) or\
				 (ProgramStartTime.time() > StartTime.time() and ProgramStartTime.time() > EndTime.time())

def isAllowedDate(StartDate, EndDate, ProgramStartDate, AllowDisallow):
	if AllowDisallow:
		return ProgramStartDate.date() >= StartDate.date() and ProgramStartDate.date() <= EndDate.date()
	else:
		return (ProgramStartDate.date() < StartDate.date() and ProgramStartDate.date() < EndDate.date()) or\
				 (ProgramStartDate.date() > StartDate.date() and ProgramStartDate.date() > EndDate.date())

def isAllowedWeekDay(Weekdays, ProgramStartDate, AllowDisallow):
	weekday = ProgramStartDate.weekday()
	weekdays = Weekdays.split(',')
	if AllowDisallow:
		return str(weekday) in weekdays
	else:
		return str(weekday) not in weekdays

@app.context_processor
def utility_processor():
	return dict(isAllowedTime=isAllowedTime )

@app.template_filter('dateformat')
def dateformat(value, format='%Y-%m-%d'):
	return value.strftime(format)

@app.template_filter('timeformat')
def timeformat(value, format='%H:%M'):
	return value.strftime(format)

@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
	return value.strftime(format)

@app.template_filter('durationformat')
def durationformat(value):
	return timedelta(seconds=value)

@app.template_filter('datetimeformat2')
def datetimeformat2(value, format='%Y-%m-%d %H:%M:%S'):
	return value.strftime(format)

##############################################################################################
#            APP - Routes
##############################################################################################

# Index route renders the main HTML page.

@app.route("/")
def index():
	zones = Zone.query.all()
	next_progam_run = GetNextProgamRun()
	return render_template('index.html', zones=zones, next_progam_run=next_progam_run, curent_page='Home')

@app.route("/programs")
def programs():
	programs = Program.query.all()
	# zones = Zone.query.filter_by(enabled=True)
	zones = Zone.query.all()
	next_progam_run = GetNextProgamRun()
	return render_template('programs.html', programs=programs, zones=zones, next_progam_run=next_progam_run, curent_page='Programs')

@app.route("/schedules")
def schedules():
	schedules = Schedule.query.all()
	programs = Program.query.filter_by(enabled=True)
	next_progam_run = GetNextProgamRun()
	return render_template('schedules.html', schedules=schedules, programs=programs, next_progam_run=next_progam_run, curent_page='Schedules')

@app.route("/adjustments")
def adjustments():
	adjustments = Adjustment.query.all()
	programs = Program.query.filter_by(enabled=True)
	next_progam_run = GetNextProgamRun()
	return render_template('adjustments.html', adjustments=adjustments, programs=programs, next_progam_run=next_progam_run, curent_page='Adjustments')

@app.route("/program_history")
def program_history():
	program_id = request.args.get('pid', 0, type=int)
	programs_history = db.session.query(Program_Zones_History)\
			.filter(Program_Zones_History.program_id == program_id) \
			.order_by(Program_Zones_History.zone_run_timestamp) \
			.all()
	return render_template('program_history.html', programs_history=programs_history)

@app.route("/program_zone_history")
def program_zone_history():
	program_id = request.args.get('pid', 0, type=int)
	zone_id = request.args.get('zone', 0, type=int)
	programs_history = db.session.query(Program_Zones_History)\
			.filter(Program_Zones_History.program_id == program_id, Program_Zones_History.zone_id == zone_id) \
			.order_by(Program_Zones_History.zone_run_timestamp) \
			.all()
	return render_template('program_history.html', programs_history=programs_history)


##############################################################################################
#            G L O B A L - Functions
##############################################################################################

@app.route("/restrictions")
def restrictions():
	restrictions = Restriction.query.all()
	programs = Program.query.filter_by(enabled=True)
	next_progam_run = GetNextProgamRun()
	return render_template('restrictions.html', restrictions=restrictions, programs=programs, next_progam_run=next_progam_run, curent_page='Restrictions')

def GetNextProgamRun():
	# get all scheduled program for a current period
	results = db.session.query(Program.program_id, Program.description, Schedule.start_date, Schedule.end_date, Schedule.end_date, Schedule.day_interval)\
				.join(Program_Schedule, Program_Schedule.program_id==Program.program_id)\
				.join(Schedule, Schedule.schedule_id==Program_Schedule.schedule_id)\
				.order_by(Schedule.start_date)\
				.filter(Schedule.end_date >= datetime.now() )\
				.all()

	# find the earliest time/program in the results
	find_datetime = None
	bResult = True
	start_time = None
	for result in results:
		start_date = result.start_date
		end_date = result.end_date
		day_interval = result.day_interval

		program_run = Program_Run.query.filter_by(program_id=result.program_id)\
					.order_by(Program_Run.start_time)\
					.first()
		if not program_run is None:
			start_time = program_run.start_time
			start_datetime = datetime.combine(datetime.date(start_date) , datetime.time(start_time) )
			prev_start_datetime = start_datetime
			while start_datetime < datetime.now():
				start_datetime = start_datetime + timedelta(days=day_interval)

				bResult = True
				if start_datetime >= datetime.now():
					# Check if there are any restriction that don't allow this time/date not to run
					restrictions = db.session.query(Restriction, Program_Restriction)\
								.join(Program_Restriction)\
								.filter(Program_Restriction.program_id == result.program_id )\
								.all()
					for restriction in restrictions:
						bResult = False
						while not bResult and start_datetime < end_date:
							if restriction.Restriction.restriction_type == 'Calendar':
								bResult = isAllowedDate(restriction.Restriction.start_date, restriction.Restriction.end_date, start_datetime, restriction.Restriction.allow_disallow_indicator)
							elif restriction.Restriction.restriction_type == 'Sensor':
								# TBD - external sensor trigger check
								bResult = True
							elif restriction.Restriction.restriction_type == 'Time':
								bResult = isAllowedTime(restriction.Restriction.start_date, restriction.Restriction.end_date, start_datetime, restriction.Restriction.allow_disallow_indicator)
							elif restriction.Restriction.restriction_type == 'Weekday':
								bResult = isAllowedWeekDay(restriction.Restriction.restriction_value, start_datetime, restriction.Restriction.allow_disallow_indicator)
							if not bResult and start_datetime < end_date:
								start_datetime = start_datetime + timedelta(days=day_interval)

			if find_datetime is None:
				if start_datetime <= end_date and bResult:
					find_datetime = start_datetime
					program_id = result.program_id
					program_desc = result.description
			else:
				if start_datetime < find_datetime and start_datetime <= end_date and bResult:
					find_datetime = start_datetime
					program_id = result.program_id
					program_desc = result.description

			# if we didn't find date, start from the first found date
			# so we can process possible other restrictions
			if not bResult or start_datetime >= end_date:
				start_datetime = prev_start_datetime

	if find_datetime is None:
		return dict( program_id=0, program='Programs Restricted', run_datetime=datetime.now(), start_time=start_time)
	else:
		return dict( program_id=program_id, program=program_desc, run_datetime=find_datetime, start_time=start_time)

##############################################################################################
#            SOCKETIO - Functions
##############################################################################################

def get_season(dtDate):
	# get the current day of the year
	doy = dtDate.timetuple().tm_yday

	# "day of year" ranges for the northern hemisphere
	spring = range(80, 172)
	summer = range(172, 264)
	fall = range(264, 355)
	# winter = everything else

	if doy in spring:
	  season = 'Spring'
	elif doy in summer:
	  season = 'Summer'
	elif doy in fall:
	  season = 'Fall'
	else:
	  season = 'Winter'
	return season

##############################################################################################
#            SOCKETIO - Functions
##############################################################################################

@socketio.on('set_zone_event')
def set_zone_event(json_data):
	data = json.loads(json_data)
	# Check if the zone state is 0 (off) or 1 (on) and set the LED accordingly.
	if data['value'] == 1:
		ws.set_interrupt(False)
	thr = Thread(target=ws.set_zone, args=[data['zone'], data['value'], data['duration']])
	thr.deamon = True # Don't let this thread block exiting.
	thr.start()
	return ('', 204)

@socketio.on('set_zone_enable')
def set_zone_enable(json_data):
	data = json.loads(json_data)
	zone = Zone.query.filter_by(zone_id=data['zone']).first()
	zone.enabled = data['value']
	db.session.commit()
	socketio.emit('change_event', "", broadcast=True )
	return ('', 204)

@socketio.on('set_zone_desc')
def set_zone_desc(json_data):
	data = json.loads(json_data)
	zone = Zone.query.filter_by(zone_id=data['zone']).first()
	zone.description = data['value']
	db.session.commit()
	socketio.emit('change_event', "", broadcast=True )
	return ('', 204)

@socketio.on('interrupt_zone_event')
def interrupt_zone_event():
	ws.set_interrupt(True)
	return ('', 204)

#####################################  Scheduler #########################################################

@socketio.on('run_schedule')
def run_schedule():
	global job_id
	if job_id != 0:
		scheduler.delete_job(job_id)
	next_progam_run = GetNextProgamRun()
	job = app.apscheduler.add_job(func=RunProgramSchedule, trigger='date', run_date=next_progam_run['run_datetime'], args=[int(next_progam_run['program_id']), next_progam_run['start_time'], next_progam_run['run_datetime']], id='1')
	job_id = job.id
	print("<---------------------------------------------------------->")
	print(job)
	print("<---------------------------------------------------------->")
	return ('', 204)

@socketio.on('stop_schedule')
def stop_schedule():
	global job_id
	if job_id != 0:
		scheduler.delete_job(job_id)
		job_id = 0
		socketio.emit('change_event', "", broadcast=True )
	return ('', 204)

def RunProgramSchedule(program_id, start_time, run_datetime):
	print("<---------------------------------------------------------->")
	print("Start Schedule for program: " + str(program_id) + ' ' + str(start_time) + ' ' + str(run_datetime) )
	print("<---------------------------------------------------------->")

	# first find out if there are adjustments for the program we are about to run
	adjustment = db.session.query(Program_Adjustment.program_id, Adjustment.adjustment_id, Adjustment.start_date, Adjustment.end_date, Adjustment.adjust_value, Adjustment.enabled)\
				.join(Adjustment, Program_Adjustment.adjustment_id==Adjustment.adjustment_id)\
				.filter(Program_Adjustment.program_id == program_id, Adjustment.start_date <= datetime.now(), Adjustment.end_date >= datetime.now() , Adjustment.enabled == True )\
				.first()
	adjustment_factor = 100
	if not adjustment is None:
		adjustment_factor = adjustment.adjust_value
	# get the scheduled program with runtimes
	results = db.session.query(Program_Zones.program_id, Program_Zones.run_time, Zone.zone_id, Zone.description, Zone.enabled)\
				.join(Zone, Program_Zones.zone_id==Zone.zone_id)\
				.order_by(Zone.zone_id)\
				.filter(Program_Zones.program_id == program_id, Zone.enabled == True )\
				.all()
	for result in results:
		run_time = result.run_time
		adjusted_run_time = int((adjustment_factor * run_time * 60) / 100)
		# Update program_zone_history, with completion = False
		run_timestamp = AddProgramZoneRunHistory(program_id, result.zone_id, adjusted_run_time)
		# Run the zone
		ws.set_zone(result.zone_id, 1, adjusted_run_time)
		# Update program_zone_history, with completion = True
		CompleteProgramZoneRunHistory(program_id, result.zone_id, run_timestamp)

	program_run = Program_Run.query.filter_by(program_id=program_id, start_time=start_time).first()
	program_run.last_run = run_datetime
	db.session.commit()

	# Schedule the next run
	next_progam_run = GetNextProgamRun()
	job = app.apscheduler.add_job(func=RunProgramSchedule, trigger='date', run_date=next_progam_run['run_datetime'], args=[int(next_progam_run['program_id']), next_progam_run['start_time'], next_progam_run['run_datetime']], id='1')
	job_id = job.id
	print("<---------------------------------------------------------->")
	print(job)
	print("<---------------------------------------------------------->")
	socketio.emit('change_event', "", broadcast=True )

def AddProgramZoneRunHistory(program_id, zone_id, adjusted_run_time):
	# Get the number of history records for a zone_id & program_id combination
	nCount = db.session.query(Program_Zones_History)\
			.filter(Program_Zones_History.zone_id == zone_id, Program_Zones_History.program_id == program_id) \
			.order_by(Program_Zones_History.zone_run_timestamp) \
			.count()
	# Only keep 10 records
	if nCount > 9:
		program_zone_history_old_one = db.session.query(Program_Zones_History) \
			.filter(Program_Zones_History.zone_id == zone_id, Program_Zones_History.program_id == program_id) \
			.order_by(Program_Zones_History.zone_run_timestamp) \
			.first()
		db.session.delete(program_zone_history_old_one)

	dtNow = datetime.now()
	program_zone_history = Program_Zones_History(zone_id=zone_id, program_id=program_id, zone_run_timestamp=dtNow, zone_run_duration=adjusted_run_time, completion=False)
	db.session.add(program_zone_history)
	db.session.commit()
	return dtNow

def CompleteProgramZoneRunHistory(program_id, zone_id, run_timestamp):
	program_zone_history = db.session.query(Program_Zones_History) \
		.filter(Program_Zones_History.zone_id == zone_id, Program_Zones_History.program_id == program_id, Program_Zones_History.zone_run_timestamp== run_timestamp) \
		.first()
	program_zone_history.completion = True
	db.session.commit()

#####################################  Program #########################################################

@socketio.on('add_program')
def add_program():
	data = ""
	program = Program(description='Program', enabled=True)
	db.session.add(program)
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_program_enable')
def set_program_enable(json_data):
	data = json.loads(json_data)
	program = Program.query.filter_by(program_id=data['program_id']).first()
	program.enabled = data['value']
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_program_desc')
def set_program_desc(json_data):
	data = json.loads(json_data)
	program = Program.query.filter_by(program_id=data['program_id']).first()
	program.description = data['value']
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('delete_program')
def delete_program(json_data):
	data = json.loads(json_data)
	program = Program.query.filter_by(program_id=data['program_id']).first()
	db.session.delete(program)
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('add_program_zone')
def add_program_zone(json_data):
	data = json.loads(json_data)
	program_zone = Program_Zones(program_id=data['program_id'], zone_id=data['zone_id'], run_time=1)
	db.session.add(program_zone)
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('change_program_zone_runtime')
def change_program_zone_runtime(json_data):
	data = json.loads(json_data)
	program_zone = Program_Zones.query.filter_by(program_id=data['program_id'], zone_id=data['zone_id']).first()
	program_zone.run_time = data['run_time']
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('remove_program_zone')
def remove_program_zone(json_data):
	data = json.loads(json_data)
	program_zone = Program_Zones.query.filter_by(program_id=data['program_id'], zone_id=data['zone_id']).first()
	db.session.delete(program_zone)
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('add_program_run_time')
def add_program_run_time(json_data):
	data = json.loads(json_data)
	datetime_object = datetime.strptime(data['start_time'], '%H:%M')
	program_run = Program_Run(program_id=data['program_id'], start_time=datetime_object)
	db.session.add(program_run)
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('remove_program_run_time')
def remove_program_run_time(json_data):
	data = json.loads(json_data)
	datetime_object = datetime.strptime(data['start_time'], '%H:%M')
	program_run = Program_Run.query.filter_by(program_id=data['program_id'], start_time=datetime_object).first()
	db.session.delete(program_run)
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_program_run_time')
def set_program_run_time(json_data):
	data = json.loads(json_data)
	datetime_object = datetime.strptime(data['old_time'], '%H:%M')
	program_run = Program_Run.query.filter_by(program_id=data['program_id'], start_time=datetime_object).first()
	datetime_object = datetime.strptime(data['start_time'], '%H:%M')
	program_run.start_time = datetime_object
	db.session.commit()
	socketio.emit('program_change', data, broadcast=True )
	return ('', 204)

###################################### Schedule ########################################################

@socketio.on('add_schedule')
def add_schedule(json_data):
	data = json.loads(json_data)
	datetime_start = datetime.strptime(data['start_date'], '%Y-%m-%d')
	datetime_end = datetime.combine(datetime.strptime(data['end_date'], '%Y-%m-%d'), tm.max)
	schedule = Schedule(day_interval=data['day_interval'], description='Schedule-' + str(data['day_interval']) + 'd', start_date=datetime_start, end_date=datetime_end, enabled=True)
	db.session.add(schedule)
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_schedule_enable')
def set_schedule_enable(json_data):
	data = json.loads(json_data)
	schedule = Schedule.query.filter_by(schedule_id=data['schedule_id']).first()
	schedule.enabled = data['value']
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_schedule_desc')
def set_schedule_desc(json_data):
	data = json.loads(json_data)
	schedule = Schedule.query.filter_by(schedule_id=data['schedule_id']).first()
	schedule.description = data['value']
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_schedule_value')
def set_schedule_value(json_data):
	data = json.loads(json_data)
	schedule = Schedule.query.filter_by(schedule_id=data['schedule_id']).first()
	schedule.day_interval = data['value']
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_schedule_start_date')
def set_schedule_start_date(json_data):
	data = json.loads(json_data)
	schedule = Schedule.query.filter_by(schedule_id=data['schedule_id']).first()
	datetime_object = datetime.strptime(data['value'], '%Y-%m-%d')
	schedule.start_date = datetime_object
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_schedule_end_date')
def set_schedule_end_date(json_data):
	data = json.loads(json_data)
	schedule = Schedule.query.filter_by(schedule_id=data['schedule_id']).first()
	datetime_object = datetime.combine(datetime.strptime(data['value'], '%Y-%m-%d'), tm.max)
	schedule.end_date = datetime_object
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

@socketio.on('delete_schedule')
def delete_schedule(json_data):
	data = json.loads(json_data)
	schedule = Schedule.query.filter_by(schedule_id=data['schedule_id']).first()
	db.session.delete(schedule)
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

@socketio.on('add_program_schedule')
def add_program_schedule(json_data):
	data = json.loads(json_data)
	program_schedule = Program_Schedule(program_id=data['program_id'], schedule_id=data['schedule_id'])
	db.session.add(program_schedule)
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

@socketio.on('remove_program_schedule')
def remove_program_schedule(json_data):
	data = json.loads(json_data)
	program_schedule = Program_Schedule.query.filter_by(program_id=data['program_id'], schedule_id=data['schedule_id']).first()
	db.session.delete(program_schedule)
	db.session.commit()
	socketio.emit('schedule_change', data, broadcast=True )
	return ('', 204)

####################################### Adjustment #######################################################

@socketio.on('add_adjustment')
def add_adjustment(json_data):
	data = json.loads(json_data)
	datetime_start = datetime.strptime(data['start_date'], '%Y-%m-%d')
	datetime_end = datetime.combine(datetime.strptime(data['end_date'], '%Y-%m-%d'), tm.max)
	season = get_season(datetime_start)
	adjustment = Adjustment(adjust_value=data['adjust_value'], description=season + '-' + data['adjust_value'] + '%', start_date=datetime_start, end_date=datetime_end, enabled=True)
	db.session.add(adjustment)
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_adjustment_enable')
def set_adjustment_enable(json_data):
	data = json.loads(json_data)
	adjustment = Adjustment.query.filter_by(adjustment_id=data['adjustment_id']).first()
	adjustment.enabled = data['value']
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_adjustment_desc')
def set_adjustment_desc(json_data):
	data = json.loads(json_data)
	adjustment = Adjustment.query.filter_by(adjustment_id=data['adjustment_id']).first()
	adjustment.description = data['value']
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_adjustment_value')
def set_adjustment_value(json_data):
	data = json.loads(json_data)
	adjustment = Adjustment.query.filter_by(adjustment_id=data['adjustment_id']).first()
	adjustment.adjust_value = data['value']
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_adjustment_start_date')
def set_adjustment_start_date(json_data):
	data = json.loads(json_data)
	adjustment = Adjustment.query.filter_by(adjustment_id=data['adjustment_id']).first()
	datetime_object = datetime.strptime(data['value'], '%Y-%m-%d')
	adjustment.start_date = datetime_object
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_adjustment_end_date')
def set_adjustment_end_date(json_data):
	data = json.loads(json_data)
	adjustment = Adjustment.query.filter_by(adjustment_id=data['adjustment_id']).first()
	datetime_object = datetime.combine(datetime.strptime(data['value'], '%Y-%m-%d'), tm.max)
	adjustment.end_date = datetime_object
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

@socketio.on('delete_adjustment')
def delete_adjustment(json_data):
	data = json.loads(json_data)
	adjustment = Adjustment.query.filter_by(adjustment_id=data['adjustment_id']).first()
	db.session.delete(adjustment)
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

@socketio.on('add_program_adjustment')
def add_program_adjustment(json_data):
	data = json.loads(json_data)
	program_adjustment = Program_Adjustment(program_id=data['program_id'], adjustment_id=data['adjustment_id'])
	db.session.add(program_adjustment)
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

@socketio.on('remove_program_adjustment')
def remove_program_adjustment(json_data):
	data = json.loads(json_data)
	program_adjustment = Program_Adjustment.query.filter_by(program_id=data['program_id'], adjustment_id=data['adjustment_id']).first()
	db.session.delete(program_adjustment)
	db.session.commit()
	socketio.emit('adjustment_change', data, broadcast=True )
	return ('', 204)

######################################## Restriction ######################################################

@socketio.on('add_restriction')
def add_restriction(json_data):
	data = json.loads(json_data)
	restriction_type = data['restriction_type']
	allow_disallow = data['allow_disallow']
	if restriction_type=="Calendar":
		datetime_start = datetime.strptime(data['start_date'], '%Y-%m-%d')
		datetime_end = datetime.combine(datetime.strptime(data['end_date'], '%Y-%m-%d'), tm.max)
		season = get_season(datetime_start)
		restriction = Restriction(description=season, restriction_type=restriction_type, start_date=datetime_start, end_date=datetime_end, allow_disallow_indicator=allow_disallow, enabled=True)
	elif restriction_type=="Sensor":
		restriction = Restriction(description="Sensor", restriction_type=restriction_type, start_range=data['start_range'], end_range=data['end_range'], allow_disallow_indicator=allow_disallow, enabled=True)
	elif restriction_type=="Time":
		time_start = datetime.strptime(data['start_time'], '%H:%M')
		time_end = datetime.strptime(data['end_time'], '%H:%M')
		restriction = Restriction(description="Time", restriction_type=restriction_type, start_date=time_start, end_date=time_end, allow_disallow_indicator=allow_disallow, enabled=True)
	elif restriction_type=="Weekday":
		restriction = Restriction(description="Weekday", restriction_type=restriction_type, restriction_value=data['restriction_value'], allow_disallow_indicator=allow_disallow, enabled=True)
	db.session.add(restriction)
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('delete_restriction')
def delete_restriction(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	db.session.delete(restriction)
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('add_program_restriction')
def add_program_restriction(json_data):
	data = json.loads(json_data)
	program_restriction = Program_Restriction(program_id=data['program_id'], restriction_id=data['restriction_id'])
	db.session.add(program_restriction)
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('remove_program_restriction')
def remove_program_restriction(json_data):
	data = json.loads(json_data)
	program_restriction = Program_Restriction.query.filter_by(program_id=data['program_id'], restriction_id=data['restriction_id']).first()
	db.session.delete(program_restriction)
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_enable')
def set_restriction_enable(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	restriction.enabled = data['value']
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_desc')
def set_restriction_desc(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	restriction.description = data['value']
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_start_date')
def set_restriction_start_date(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	datetime_object = datetime.strptime(data['value'], '%Y-%m-%d')
	restriction.start_date = datetime_object
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_end_date')
def set_restriction_end_date(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	datetime_object = datetime.combine(datetime.strptime(data['value'], '%Y-%m-%d'), tm.max)
	restriction.end_date = datetime_object
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_start_time')
def set_restriction_start_date(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	datetime_object = datetime.strptime(data['value'], '%H:%M')
	restriction.start_date = datetime_object
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_end_time')
def set_restriction_end_date(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	datetime_object = datetime.strptime(data['value'], '%H:%M')
	restriction.end_date = datetime_object
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_start_range')
def set_restriction_start_range(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	restriction.start_range = data['value']
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_end_range')
def set_restriction_end_range(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	restriction.end_range = data['value']
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_value')
def set_restriction_value(json_data):
	data = json.loads(json_data)
	print(data['value'])
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	restriction.restriction_value = data['value']
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

@socketio.on('set_restriction_allow_disallow')
def set_restriction_allow_disallow(json_data):
	data = json.loads(json_data)
	restriction = Restriction.query.filter_by(restriction_id=data['restriction_id']).first()
	restriction.allow_disallow_indicator = data['allow_disallow']
	db.session.commit()
	socketio.emit('restriction_change', data, broadcast=True )
	return ('', 204)

##############################################################################################
#            App - Main Functions
##############################################################################################

# Server-sent event endpoint that streams the switch state every second.
@app.route("/live_data")
def live_data():
	def get_data():
		global job_id
		while True:
			wifi_data = {
					'time':time.strftime("%H:%M:%S"),
					'job':job_id
				}
			yield 'data: {0}\n\n'.format(json.dumps(wifi_data))
			time.sleep(1.0)
	return Response(get_data(), mimetype='text/event-stream')

# Create a zone change callback and enable it
def zone_change(zone, progress, interrupt_zones):
	data = json.dumps({ 'zone': zone, 'progress': progress, 'interrupt_zones': interrupt_zones })
	socketio.emit('zone_change', data, broadcast=True )

# Start the flask debug server listening on the pi port 5000 by default.
if __name__ == "__main__":
	ws.set_zone_callback(zone_change)
	if job_id == 0:
		run_schedule()
	socketio.run(app,host='0.0.0.0', debug=True,port=5000)
