from datetime import datetime

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import PrimaryKeyConstraint
# from sqlalchemy.orm import relationship

app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////root/WifiApp/wifi_data.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wifi_data.db'
db = SQLAlchemy(app)

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
	start_time = db.Column(db.DateTime, unique=False, primary_key=True, default=datetime.utcnow)
	last_run = db.Column(db.DateTime, unique=False)

class Schedule(db.Model):
	__tablename__ = 'Schedule'

	schedule_id = db.Column(db.Integer, primary_key=True)
	day_interval = db.Column(db.Integer, unique=False)
	description = db.Column(db.String(120), unique=False, nullable=False)
	start_date = db.Column(db.DateTime, unique=False, default=datetime.utcnow)
	end_date = db.Column(db.DateTime, unique=False, default=datetime.utcnow)
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
	start_date = db.Column(db.DateTime, unique=False, nullable=True, default=datetime.utcnow)
	end_date = db.Column(db.DateTime, unique=False, nullable=True, default=datetime.utcnow)
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
	start_date = db.Column(db.DateTime, unique=False, default=datetime.utcnow)
	end_date = db.Column(db.DateTime, unique=False, default=datetime.utcnow)
	enabled = db.Column(db.Boolean)
	program_adjustment = db.relationship('Program_Adjustment', backref='adjustment', cascade="all, delete-orphan")

class Program_Adjustment(db.Model):
	__tablename__ = 'Program_Adjustment'
	__table_args__ = (
		PrimaryKeyConstraint('program_id', 'adjustment_id'),
	)	

	program_id = db.Column(db.Integer, db.ForeignKey("Program.program_id"), primary_key=True)
	adjustment_id = db.Column(db.Integer, db.ForeignKey("Adjustment.adjustment_id"), primary_key=True)

db.create_all()