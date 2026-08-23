import os
import re
import json
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

class UCPPortalScraper:
    BASE_URL = "https://horizon.ucp.edu.pk"
    STATE_FILE = Path("portal_session.json")
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.session = requests.Session()
        self._initialize_session()

    def _login_and_save_session(self):
        print("[Auth] Logging in via Playwright Microsoft SSO...")
        ucp_email = os.environ.get("UCP_EMAIL")
        ucp_password = os.environ.get("UCP_PASSWORD")
        if not ucp_email or not ucp_password:
            raise ValueError("[Auth Error] Missing required credentials. UCP_EMAIL and UCP_PASSWORD must be defined in your .env file.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()

            page.goto(self.BASE_URL)
            page.wait_for_load_state('networkidle')
            
            page.locator('text="login With Microsoft"').click()
            page.fill('input[type="email"]', ucp_email, timeout=60000)
            page.click('input[type="submit"]')
            
            page.fill('input[type="password"]', ucp_password, timeout=60000)
            page.click('input[type="submit"]')
            
            try:
                page.locator('text="No"').click(timeout=3000)
            except Exception:
                pass
                
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            context.storage_state(path=str(self.STATE_FILE))
            print("[Auth] Successfully logged in and saved session.")
            browser.close()

    def _initialize_session(self):
        if not self.STATE_FILE.exists():
            self._login_and_save_session()
            if not self.STATE_FILE.exists():
                raise Exception("Critical: Failed to generate session state file.")

        with open(self.STATE_FILE, 'r') as f:
            state = json.load(f)

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        for cookie in state.get('cookies', []):
            self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

    def _request(self, endpoint: str, stream: bool = False, _is_retry: bool = False) -> requests.Response:
        url = f"{self.BASE_URL}{endpoint}" if endpoint.startswith('/') else endpoint
        response = self.session.get(url, stream=stream)
        
        if "login" in response.url.lower():
            if _is_retry:
                raise Exception(f"Authentication loop detected. Failed to access {url}")
                
            print(f"[Auth] Session expired while accessing {endpoint}. Re-authenticating...")
            if self.STATE_FILE.exists():
                self.STATE_FILE.unlink()
                
            self._initialize_session()
            return self._request(endpoint, stream=stream, _is_retry=True)
            
        return response

    def get_dashboard(self) -> dict:
        print("[API] Fetching Dashboard...")
        response = self._request("/student/dashboard")
        soup = BeautifulSoup(response.text, 'html.parser')
        raw = soup.get_text(separator='\n', strip=True)
        
        profile = {}
        
        name_match = re.search(r'([A-Z][a-z]+(?: [A-Z][a-z]+){1,4})\s*\n\s*(L\d[A-Z]\d{2}[A-Z]+\d+)', raw)
        if name_match:
            profile["name"]    = name_match.group(1).strip()
            profile["roll_no"] = name_match.group(2).strip()

        dept_match = re.search(r'(Faculty of [A-Za-z ]+(?:and [A-Za-z ]+)?)', raw)
        if dept_match:
            profile["department"] = dept_match.group(1).strip()

        cgpa_match = re.search(r'CGPA\s*[:\-]?\s*([\d.]+)', raw)
        if cgpa_match: profile["cgpa"] = cgpa_match.group(1)

        earned_match     = re.search(r'Earned Cr\s*[:\-]?\s*([\d.]+)', raw)
        total_match      = re.search(r'Total Cr\s*[:\-]?\s*([\d.]+)', raw)
        inprogress_match = re.search(r'Inprogress Cr\s*[:\-]?\s*([\d.]+)', raw)
        
        if earned_match:     profile["earned_cr"]     = earned_match.group(1)
        if total_match:      profile["total_cr"]      = total_match.group(1)
        if inprogress_match: profile["inprogress_cr"] = inprogress_match.group(1)

        badges = []
        for badge in soup.select('.uk-badge, .uk-label, .badge, .label, span.label-success, span.label-info, span.bg-success'):
            text = badge.get_text(strip=True)
            if text and 2 < len(text) < 40 and not text.isdigit():
                badges.append(text)
        profile["scholarships"] = list(set(badges))

        today_classes = []
        today_section = re.search(r"Today Classes\s*:(.*?)(?:\n\n|\Z)", raw, re.DOTALL)
        if today_section:
            today_raw = today_section.group(1).strip()
            if "No class" not in today_raw and today_raw:
                today_classes = [line.strip() for line in today_raw.splitlines() if line.strip()]
        profile["today_classes"] = today_classes

        courses = []
        for link in soup.select('a[href^="/student/course/info/"]'):
            name_span = link.select_one('.card-header span')
            if name_span:
                courses.append({
                    "name": name_span.get_text(strip=True),
                    "url": f"{self.BASE_URL}{link.get('href')}"
                })

        return {"profile": profile, "courses": courses}

    def get_profile(self) -> dict:
        print("[API] Fetching Detailed Profile...")
        response = self._request("/student/profile")
        soup = BeautifulSoup(response.text, 'html.parser')
        p_raw = soup.get_text(separator='\n', strip=True)
        
        profile = {}
        email_match = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', p_raw)
        if email_match: profile["email"] = email_match.group(1)
        phone_match = re.search(r'\b(03\d{9})\b', p_raw)
        if phone_match: profile["phone"] = phone_match.group(1)

        lines = [line.strip() for line in p_raw.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if i == 0: continue
            val = lines[i-1]
            if "Career" in line: profile["career"] = val
            elif "Program" in line and len(line) < 15: profile["program"] = val
            elif "Current Semester" in line: profile["current_semester"] = val

        for content in soup.find_all('div', class_='md-list-content'):
            label_span = content.find('span', class_='uk-text-muted')
            if not label_span: continue
                
            raw_label = label_span.get_text(separator=' ', strip=True)
            label = ' '.join(raw_label.split()).lower()
            
            label_span.extract()
            for inp in content.find_all('input'):
                inp.extract()
                
            value = content.get_text(separator=', ', strip=True).strip(', ')
            if not value or value == '-': 
                continue
                
            if "email" in label: profile["email"] = value
            elif "phone" in label: profile["phone"] = value
            elif "emergency contact" in label: profile["emergency_contact"] = value
            elif "present address" in label: profile["present_address"] = value
            elif "permanent address" in label: profile["permanent_address"] = value
            elif "date of birth" in label: profile["dob"] = value
            elif "gender" in label: profile["gender"] = value
            elif "cnic" in label and "father" not in label and "guardian" not in label: 
                if "cnic" not in profile: profile["cnic"] = value
            elif "domicile" in label: profile["domicile"] = value
            elif "nationlity" in label or "nationality" in label: profile["nationality"] = value
            elif "religion" in label: profile["religion"] = value
            elif "blood group" in label: profile["blood_group"] = value
            elif "father name" in label: profile["father_name"] = value
            elif "father cnic" in label: profile["father_cnic"] = value
            elif "guardian name" in label: profile["guardian_name"] = value
            elif "guardian cnic" in label: profile["guardian_cnic"] = value
            elif "marital status" in label: profile["marital_status"] = value

        profile["family_and_other_data"] = []
        for table in soup.find_all('table'):
            parsed_table = self._parse_table(table)
            if parsed_table:
                profile["family_and_other_data"].extend(parsed_table)

        return profile

    def get_grades(self) -> list:
        print("[API] Fetching Grades...")
        response = self._request("/student/results")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        current_term = None
        
        for row in soup.select('tr.table-parent-row, tr.table-child-row'):
            row_classes = row.get('class', [])
            cells = row.find_all('td')
            
            if 'table-parent-row' in row_classes and len(cells) >= 8:
                current_term = {
                    "term": cells[0].get_text(strip=True),
                    "grade_points": cells[1].get_text(strip=True),
                    "cumulative_gp": cells[2].get_text(strip=True),
                    "attempted_ch": cells[3].get_text(strip=True),
                    "earned_ch": cells[4].get_text(strip=True),
                    "cumulative_ch": cells[5].get_text(strip=True),
                    "sgpa": cells[6].get_text(strip=True),
                    "cgpa": cells[7].get_text(strip=True),
                    "courses": [],
                }
                results.append(current_term)
            elif 'table-child-row' in row_classes and current_term is not None and len(cells) >= 4:
                current_term["courses"].append({
                    "course": cells[0].get_text(strip=True),
                    "credit_hours": cells[1].get_text(strip=True),
                    "grade_pts": cells[2].get_text(strip=True),
                    "final_grade": cells[3].get_text(strip=True),
                })
                
        return results

    def get_timetable(self) -> dict:
        print("[API] Fetching Timetable...")
        response = self._request("/student/class/schedule")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        schedule = {}
        for group in soup.select('li.cd-schedule__group'):
            day_span = group.select_one('.cd-schedule__top-info span')
            if not day_span: continue
            day_name = day_span.get_text(strip=True)
            
            day_classes = []
            for event in group.select('li.cd-schedule__event'):
                link = event.select_one('a')
                if not link: continue
                    
                spans = [s.get_text(strip=True) for s in link.select('span')]
                em_tag = link.select_one('em')
                
                day_classes.append({
                    "start": link.get('data-start', ''),
                    "end": link.get('data-end', ''),
                    "teacher": em_tag.get_text(strip=True) if em_tag else "",
                    "subject": spans[0] if len(spans) > 0 else "",
                    "course_code": spans[1] if len(spans) > 1 else "",
                    "room": spans[2] if len(spans) > 2 else "",
                })
            schedule[day_name] = day_classes
            
        return schedule

    def get_notifications(self) -> list:
        print("[API] Fetching Notifications...")
        response = self._request("/student/notifications")
        soup = BeautifulSoup(response.text, 'html.parser')
        
        notifications = []
        alerts = soup.select('.alert, .notification, .md-list-item, ul.md-list > li')
        if alerts:
            for alert in alerts:
                text = alert.get_text(separator=' ', strip=True)
                if text and "No notifications" not in text:
                    notifications.append({"message": text})
            return notifications
            
        content = soup.select_one('#page_content_inner')
        if content:
            text = content.get_text(separator=' ', strip=True)
            if "No notifications" in text:
                return []
            if text:
                return [{"message": text}]
                
        return notifications

    def get_invoices(self) -> list:
        print("[API] Fetching Invoices...")
        response = self._request("/student/invoices")
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.select_one('table')
        if table:
            return self._parse_table(table)
        return []

    def get_datesheet(self) -> list:
        print("[API] Fetching Exam Datesheet...")
        response = self._request("/student/exam/datesheet")
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.select_one('table')
        if table:
            return self._parse_table(table)
        return []

    def _parse_table(self, table_soup) -> list:
        if not table_soup: return []
        headers = [th.get_text(strip=True) for th in table_soup.select('thead th')]
        rows = []
        for tr in table_soup.select('tbody tr'):
            cells = tr.find_all('td')
            if not cells or 'No ' in tr.get_text(strip=True) or len(cells) == 1:
                continue
            row = {}
            for i, header in enumerate(headers):
                if i < len(cells):
                    a_tag = cells[i].find('a', href=True)
                    if a_tag and '/download/' in a_tag.get('href', ''):
                        row[f"{header}_download_url"] = f"{self.BASE_URL}{a_tag['href']}"
                    row[header] = cells[i].get_text(strip=True)
            rows.append(row)
        return rows

    def get_course_details(self, course_url: str) -> dict:
        course_id = course_url.rstrip('/').split('/')[-1]
        print(f"[API] Fetching Course Details for ID: {course_id}")
        
        result = {}
        
        soup = BeautifulSoup(self._request(f"/student/course/attendance/{course_id}").text, 'html.parser')
        content = soup.select_one('#page_content_inner')
        attendance = {"stats": {}, "records": self._parse_table(soup.select_one('table'))}
        
        if content:
            raw = content.get_text(separator='\n', strip=True)
            code_match = re.search(r'([A-Z]{2,6}\d{2,4}(?:-[A-Z0-9]+){3,5})', raw)
            if code_match: attendance["stats"]["Course Code"] = code_match.group(1)
            
            patterns = {
                "Course": r'Course\s*:\s*\n\s*(.+)',
                "Number of classes Conducted": r'Number of classes Conducted\s*:\s*\n\s*(\d+)',
                "Number of classes Attended": r'Number of classes Attended\s*:\s*\n\s*(\d+)',
                "Academic Term": r'Academic Term\s*:\s*\n\s*(.+)',
                "Attendance Percentage": r'Attendance Percentage\s*[:\s]*\n\s*([\d.]+)',
            }
            for key, pattern in patterns.items():
                m = re.search(pattern, raw)
                if m: attendance["stats"][key] = m.group(1).strip()
                
        result["attendance"] = attendance

        raw_code = attendance.get("stats", {}).get("Course Code", "")
        if raw_code:
            parts = raw_code.strip().split('-')
            info = {"full_code": raw_code}
            if len(parts) >= 1: info["subject_code"] = parts[0]
            if len(parts) >= 2: info["revision"] = parts[1]
            if len(parts) >= 3: info["program"] = parts[2]
            if len(parts) >= 4: info["department"] = parts[3]
            if len(parts) >= 5: info["semester"] = parts[4]
            if len(parts) >= 6: info["section"] = parts[5]
            info["raw_text"] = raw
            result["course_info"] = info
        else:
            result["course_info"] = {}

        tabs = {
            "announcements": f"/student/course/info/{course_id}",
            "assessments": f"/student/course/assessment/{course_id}",
            "submissions": f"/student/course/submission/{course_id}",
        }
        for key, ep in tabs.items():
            soup = BeautifulSoup(self._request(ep).text, 'html.parser')
            result[key] = self._parse_table(soup.select_one('table'))

        soup = BeautifulSoup(self._request(f"/student/course/gradebook/{course_id}").text, 'html.parser')
        assessments = []
        for tr in soup.select('tbody tr'):
            cells = tr.find_all(['td', 'th'])
            if len(cells) == 5:
                col1 = cells[0].get_text(strip=True)
                
                if "Assessment" in col1 or not col1:
                    continue
                    
                try:
                    max_m = float(cells[1].get_text(strip=True))
                    obt_m = float(cells[2].get_text(strip=True))
                    avg_m = float(cells[3].get_text(strip=True))
                    perc = float(cells[4].get_text(strip=True))
                    
                    assessments.append({
                        "Assessment": col1,
                        "Max Mark": max_m,
                        "Obtained Marks": obt_m,
                        "Class Average": avg_m,
                        "Percentage": perc
                    })
                except ValueError:
                    continue
                    
        result["gradebook_assessments"] = assessments

        soup = BeautifulSoup(self._request(f"/student/course/material/{course_id}").text, 'html.parser')
        materials = []
        for tr in soup.select('tbody tr.table-child-row'):
            cells = tr.find_all('td')
            a_tag = tr.find('a', href=lambda h: h and '/download/' in h)
            if len(cells) >= 2:
                materials.append({
                    "filename": cells[1].get_text(strip=True),
                    "description": cells[2].get_text(strip=True) if len(cells) > 2 else "",
                    "download_url": f"{self.BASE_URL}{a_tag['href']}" if a_tag else None,
                })
        result["materials"] = materials

        soup = BeautifulSoup(self._request(f"/student/course/outline/{course_id}").text, 'html.parser')
        content = soup.select_one('#page_content_inner')
        outline = {"text_books": [], "reference_books": [], "web_resources": [], "assessment_weights": [], "raw_text": ""}
        if content:
            tables = content.select('table')
            if len(tables) >= 1: outline["text_books"] = self._parse_table(tables[0])
            if len(tables) >= 2: outline["reference_books"] = self._parse_table(tables[1])
            if len(tables) >= 3: outline["web_resources"] = self._parse_table(tables[2])
            if len(tables) >= 4: outline["assessment_weights"] = self._parse_table(tables[3])
            outline["raw_text"] = content.get_text(separator='\n', strip=True)
        result["outline"] = outline

        return result

    def download_specific_file(self, download_url: str, filename: str, download_dir: str = "downloads") -> str:
        os.makedirs(download_dir, exist_ok=True)
        safe_filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_')
        filepath = os.path.abspath(os.path.join(download_dir, safe_filename))
        
        # Cache check: if it's already downloaded, return immediately!
        if os.path.exists(filepath):
            print(f"[Download] File already exists locally, skipping portal download: {safe_filename}")
            return filepath
            
        print(f"[Download] Fetching specific file: {safe_filename}")
        file_res = self._request(download_url, stream=True)
        
        if file_res.status_code == 200:
            try:
                with open(filepath, 'wb') as f:
                    for chunk in file_res.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"[Download] Saved: {filepath}")
                return filepath
            except Exception as e:
                print(f"[Download] Error writing '{safe_filename}': {e}")
                return None
        else:
            print(f"[Download] Failed to fetch (HTTP {file_res.status_code})")
            return None
