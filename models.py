from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import JSON

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class Course(db.Model):
    __tablename__ = "courses"
    __table_args__ = (db.Index("ix_courses_user_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    club = db.Column(db.String(255))
    name = db.Column(db.String(255), nullable=False)
    pars = db.Column(JSON)
    tee_boxes = db.relationship("TeeBox", backref="course", cascade="all, delete-orphan")


class TeeBox(db.Model):
    __tablename__ = "tee_boxes"
    __table_args__ = (db.Index("ix_tee_boxes_course_id", "course_id"),)
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    color = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Float)
    slope = db.Column(db.Integer)
    handicap = db.Column(db.Float)
    yardages = db.Column(JSON)


class Round(db.Model):
    __tablename__ = "rounds"
    __table_args__ = (db.Index("ix_rounds_user_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_name = db.Column(db.String(255))
    tee_color = db.Column(db.String(50))
    date = db.Column(db.String(50))
    total_score = db.Column(db.Integer)
    par = db.Column(db.Integer)
    tee_rating = db.Column(db.Float)
    tee_slope = db.Column(db.Integer)
    target_score = db.Column(db.Integer)
    holes_played = db.Column(db.Integer)
    holes_choice = db.Column(db.String(50))
    round_type = db.Column(db.String(50))
    is_serious = db.Column(db.Boolean)
    is_sim = db.Column(db.Boolean)
    notes = db.Column(db.Text)
    scores = db.Column(JSON)
    detailed_stats = db.Column(JSON)


class Club(db.Model):
    __tablename__ = "clubs"
    __table_args__ = (db.Index("ix_clubs_user_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    distance = db.Column(db.Integer)
    notes = db.Column(db.Text)
    partials = db.Column(JSON)


class TrainingSession(db.Model):
    __tablename__ = "training_sessions"
    __table_args__ = (db.Index("ix_training_user_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.String(50))
    drills = db.Column(JSON)
    notes = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer)


class UserPrefs(db.Model):
    __tablename__ = "user_prefs"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    entry_mode = db.Column(db.String(50), default="quick")
    preferred_tee = db.Column(db.String(50))


class StatsCache(db.Model):
    __tablename__ = "stats_cache"
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), primary_key=True)
    valid = db.Column(db.Boolean, default=False)
    version = db.Column(db.Integer, default=0)
    data = db.Column(JSON)
