import sqlite3
import json
import time
import re
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, field_validator
from ucp_scraper import UCPPortalScraper

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class CourseBrief(BaseModel):
    name: str
    url: str

class ProfileSummary(BaseModel):
    name: str = ""
    roll_no: str = ""
    department: str = ""
    cgpa: str = ""
    earned_cr: str = ""
    total_cr: str = ""
    inprogress_cr: str = ""
    scholarships: List[str] = []
    today_classes: List[str] = []

class DashboardData(BaseModel):
    profile: ProfileSummary
    courses: List[CourseBrief]

class DetailedProfileData(BaseModel):
    email: str = ""
    phone: str = ""
    career: str = ""
    program: str = ""
    current_semester: str = ""
    present_address: str = ""
    permanent_address: str = ""
    dob: str = ""
    gender: str = ""
    cnic: str = ""
    domicile: str = ""
    nationality: str = ""
    religion: str = ""
    blood_group: str = ""
    father_name: str = ""
    guardian_name: str = ""
    family_and_other_data: List[dict] = []

class TimetableClass(BaseModel):
    start: str = ""
    end: str = ""
    teacher: str = ""
    subject: str = ""
    course_code: str = ""
    room: str = ""

    @field_validator('room', mode='before')
    def clean_room_string(cls, v):
        if v: return re.sub(r'\s+', ' ', v).strip()
        return v

class TimetableData(BaseModel):
    schedule: Dict[str, List[TimetableClass]]

class PastCourseRecord(BaseModel):
    course: str = ""
    credit_hours: str = ""
    grade_pts: str = ""
    final_grade: str = ""

class AcademicTerm(BaseModel):
    term: str = ""
    grade_points: str = ""
    cumulative_gp: str = ""
    attempted_ch: str = ""
    earned_ch: str = ""
    cumulative_ch: str = ""
    sgpa: str = ""
    cgpa: str = ""
    courses: List[PastCourseRecord] = []

class AcademicHistoryData(BaseModel):
    history: List[AcademicTerm]

class InvoiceRecord(BaseModel):
    invoice_date: str = Field(alias="Invoice Date", default="")
    due_date: str = Field(alias="Due Date", default="")
    term: str = Field(alias="Term", default="")
    semester: str = Field(alias="Semester", default="")
    challan_type: str = Field(alias="Challan Type", default="")
    challan_id: str = Field(alias="Challan ID", default="")
    scholarship_percentage: str = Field(alias="Scholarship %", default="")
    payable_amount: str = Field(alias="Payable Amount", default="")
    status: str = Field(alias="Status", default="")
    paid_date: Optional[str] = Field(alias="Paid Date", default=None)
    invoice_date_download_url: Optional[str] = Field(alias="Invoice Date_download_url", default=None)
    class Config: populate_by_name = True

class InvoicesData(BaseModel):
    invoices: List[InvoiceRecord]

class NotificationRecord(BaseModel):
    message: str = ""

class NotificationsData(BaseModel):
    notifications: List[NotificationRecord]

class ExamRecord(BaseModel):
    serial_no: str = Field(alias="Sr#", default="")
    course_name: str = Field(alias="Class", default="")
    teacher: str = Field(alias="Teacher", default="")
    date: str = Field(alias="Date", default="")
    time: str = Field(alias="Time", default="")
    venue: str = Field(alias="Venue", default="")
    class Config: populate_by_name = True

class ExamDatesheetData(BaseModel):
    exams: List[ExamRecord]

class CourseInfo(BaseModel):
    full_code: str = ""
    subject_code: str = ""
    revision: str = ""
    program: str = ""
    department: str = ""
    semester: str = ""
    section: str = ""
    raw_text: str = ""

class AttendanceStats(BaseModel):
    course_code: str = Field(alias="Course Code", default="")
    course_name: str = Field(alias="Course", default="")
    conducted: str = Field(alias="Number of classes Conducted", default="")
    attended: str = Field(alias="Number of classes Attended", default="")
    term: str = Field(alias="Academic Term", default="")
    percentage: str = Field(alias="Attendance Percentage", default="")
    class Config: populate_by_name = True

class AttendanceRecord(BaseModel):
    serial: str = Field(alias="Sr. no", default="")
    date: str = Field(alias="Date", default="")
    status: str = Field(alias="Status", default="")
    fine: str = Field(alias="Fine", default="")
    class Config: populate_by_name = True

class CourseAttendance(BaseModel):
    stats: AttendanceStats
    records: List[AttendanceRecord]

class GradebookAssessment(BaseModel):
    assessment: str = Field(alias="Assessment", default="")
    max_mark: float = Field(alias="Max Mark", default=0.0)
    obtained_marks: float = Field(alias="Obtained Marks", default=0.0)
    class_average: float = Field(alias="Class Average", default=0.0)
    percentage: float = Field(alias="Percentage", default=0.0)
    class Config: populate_by_name = True

class CourseMaterial(BaseModel):
    filename: str = ""
    description: str = ""
    download_url: Optional[str] = None
    class Config: populate_by_name = True

class CourseOutline(BaseModel):
    text_books: List[Dict[str, str]] = []
    reference_books: List[Dict[str, str]] = []
    web_resources: List[Dict[str, str]] = []
    assessment_weights: List[Dict[str, str]] = []
    raw_text: str = ""

class DetailedCourseData(BaseModel):
    course_info: CourseInfo
    attendance: CourseAttendance
    gradebook_assessments: List[GradebookAssessment]
    materials: List[CourseMaterial] = []
    submissions: List[Dict[str, str]] = []
    assessments: List[Dict[str, str]] = []
    announcements: List[Dict[str, str]] = []
    outline: CourseOutline

# ==========================================
# DATABASE MANAGER
# ==========================================

class UniDatabaseManager:
    DB_PATH = "uni_data.db"
    
    TTL_INFINITE = 9999999999
    TTL_30_DAYS = 30 * 24 * 60 * 60
    TTL_4_HOURS = 4 * 60 * 60

    def __init__(self, headless=True):
        self.scraper = UCPPortalScraper(headless=headless)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS uni_data (
                    key_name TEXT PRIMARY KEY,
                    json_data TEXT,
                    last_updated REAL
                )
            ''')

    def _get_from_db(self, key_name: str, ttl_seconds: float) -> Optional[Any]:
        with sqlite3.connect(self.DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT json_data, last_updated FROM uni_data WHERE key_name = ?", (key_name,))
            row = cursor.fetchone()
            if row:
                json_data, last_updated = row
                if (time.time() - last_updated) < ttl_seconds:
                    return json.loads(json_data)
        return None

    def _save_to_db(self, key_name: str, pydantic_obj: BaseModel):
        with sqlite3.connect(self.DB_PATH) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO uni_data (key_name, json_data, last_updated)
                VALUES (?, ?, ?)
            ''', (key_name, pydantic_obj.model_dump_json(), time.time()))

    def force_refresh(self, endpoint: str, course_name: Optional[str] = None):
        if endpoint == "dashboard": self.get_dashboard(force=True)
        elif endpoint == "timetable": self.get_timetable(force=True)
        elif endpoint == "grades": self.get_academic_history(force=True)
        elif endpoint == "invoices": self.get_invoices(force=True)
        elif endpoint == "notifications": self.get_notifications(force=True)
        elif endpoint == "datesheet": self.get_datesheet(force=True)
        elif endpoint == "course" and course_name: self.get_course_details(course_name, force=True)

    # --- DATA FETCHERS ---

    def get_dashboard(self, force=False) -> DashboardData:
        cached = self._get_from_db("dashboard", self.TTL_4_HOURS)
        if cached and not force: return DashboardData(**cached)
        
        raw = self.scraper.get_dashboard()
        data = DashboardData(**raw)
        self._save_to_db("dashboard", data)
        return data

    def get_profile(self, force=False) -> DetailedProfileData:
        cached = self._get_from_db("profile", self.TTL_30_DAYS)
        if cached and not force: return DetailedProfileData(**cached)
        
        raw = self.scraper.get_profile()
        data = DetailedProfileData(**raw)
        self._save_to_db("profile", data)
        return data

    def get_timetable(self, force=False) -> TimetableData:
        cached = self._get_from_db("timetable", self.TTL_30_DAYS)
        if cached and not force: return TimetableData(**cached)
        
        raw = self.scraper.get_timetable()
        data = TimetableData(schedule=raw)
        self._save_to_db("timetable", data)
        return data

    def get_academic_history(self, force=False) -> AcademicHistoryData:
        cached = self._get_from_db("grades", self.TTL_INFINITE)
        if cached and not force: return AcademicHistoryData(**cached)
        
        raw = self.scraper.get_grades()
        data = AcademicHistoryData(history=raw)
        self._save_to_db("grades", data)
        return data

    def get_invoices(self, force=False) -> InvoicesData:
        cached = self._get_from_db("invoices", self.TTL_30_DAYS)
        if cached and not force: return InvoicesData(**cached)
        
        raw = self.scraper.get_invoices()
        data = InvoicesData(invoices=raw)
        self._save_to_db("invoices", data)
        return data

    def get_notifications(self, force=False) -> NotificationsData:
        cached = self._get_from_db("notifications", self.TTL_4_HOURS)
        if cached and not force: return NotificationsData(**cached)
        
        raw = self.scraper.get_notifications()
        data = NotificationsData(notifications=raw)
        self._save_to_db("notifications", data)
        return data

    def get_datesheet(self, force=False) -> ExamDatesheetData:
        cached = self._get_from_db("datesheet", self.TTL_30_DAYS)
        if cached and not force: return ExamDatesheetData(**cached)
        
        raw = self.scraper.get_datesheet()
        data = ExamDatesheetData(exams=raw)
        self._save_to_db("datesheet", data)
        return data

    def _resolve_course_url(self, course_name: str) -> Optional[str]:
        dash = self.get_dashboard()
        for c in dash.courses:
            if course_name.lower() in c.name.lower():
                return c.url
        return None

    def get_course_details(self, course_name: str, force=False) -> Optional[DetailedCourseData]:
        key = f"course_{course_name.lower().replace(' ', '_')}"
        cached = self._get_from_db(key, self.TTL_4_HOURS)
        if cached and not force: return DetailedCourseData(**cached)
        
        url = self._resolve_course_url(course_name)
        if not url: return None
        
        raw = self.scraper.get_course_details(url)
        data = DetailedCourseData(
            course_info=raw.get("course_info", {}),
            attendance={
                "stats": raw.get("attendance", {}).get("stats", {}),
                "records": raw.get("attendance", {}).get("records", [])
            },
            gradebook_assessments=raw.get("gradebook_assessments", []),
            materials=raw.get("materials", []),
            submissions=raw.get("submissions", []),
            assessments=raw.get("assessments", []),
            announcements=raw.get("announcements", []),
            outline=raw.get("outline", {})
        )
        self._save_to_db(key, data)
        return data
