import os
from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
import traceback
from langsmith import traceable

def start_proactive_scheduler(db_manager, send_ntfy_push_func):
    """
    Initializes and starts the APScheduler to check the timetable every minute.
    """
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Asia/Karachi'))
    
    # We use a set to keep track of alerts we've already sent today so we don't spam
    # Keys will be something like: "pre-class:2026-08-23:08:00 AM" or "post-class:2026-08-23:09:30 AM"
    sent_alerts = set()

    @traceable(name="proactive_alerts.check_timetable_alerts")
    def check_timetable_alerts():
        try:
            # 1. Get current time in Pakistan
            tz = pytz.timezone('Asia/Karachi')
            now = datetime.now(tz)
            today_day = now.strftime("%A")
            date_str = now.strftime("%Y-%m-%d")

            # 2. Fetch the timetable
            # Note: we use force=False to avoid hammering the UCP portal. It will use the SQLite cache.
            timetable_data = db_manager.get_timetable(force=False)
            if not timetable_data or not timetable_data.schedule:
                return

            today_classes = timetable_data.schedule.get(today_day, [])
            
            for cls in today_classes:
                start_str = cls.start # e.g. "08:00 AM"
                end_str = cls.end     # e.g. "09:30 AM"
                if not start_str or not end_str:
                    continue
                
                # Parse times
                try:
                    try:
                        start_time = datetime.strptime(start_str, "%I:%M %p").time()
                    except ValueError:
                        start_time = datetime.strptime(start_str, "%H:%M").time()
                        
                    try:
                        end_time = datetime.strptime(end_str, "%I:%M %p").time()
                    except ValueError:
                        end_time = datetime.strptime(end_str, "%H:%M").time()
                    
                    # Create full datetime objects for today
                    class_start_dt = tz.localize(datetime.combine(now.date(), start_time))
                    class_end_dt = tz.localize(datetime.combine(now.date(), end_time))
                    
                    # 4. Check for Pre-class alert (10 mins before)
                    # We check if 'now' is within a 1-minute window of (start - 10 mins)
                    pre_class_target = class_start_dt - timedelta(minutes=10)
                    time_diff_pre = (now - pre_class_target).total_seconds()
                    
                    pre_alert_key = f"pre-{date_str}-{start_str}-{cls.subject}"
                    
                    if 0 <= time_diff_pre < 60 and pre_alert_key not in sent_alerts:
                        msg = f"🔔 Reminder: Your **{cls.subject}** class starts in 10 minutes (at {start_str}) in Room {cls.room}!"
                        send_ntfy_push_func(msg, title="Class Reminder")
                        sent_alerts.add(pre_alert_key)
                        print(f"[Proactive Alert] Sent pre-class alert for {cls.subject}")

                    # 5. Check for Post-class alert (Exactly when it ends)
                    time_diff_post = (now - class_end_dt).total_seconds()
                    post_alert_key = f"post-{date_str}-{end_str}-{cls.subject}"
                    
                    if 0 <= time_diff_post < 60 and post_alert_key not in sent_alerts:
                        msg = f"✅ Your **{cls.subject}** class in Room {cls.room} ({start_str} to {end_str}) just finished! How was it? What did you learn today?"
                        send_ntfy_push_func(msg, title="Class Finished")
                        sent_alerts.add(post_alert_key)
                        print(f"[Proactive Alert] Sent post-class alert for {cls.subject}")

                except ValueError:
                    # Ignore parsing errors for malformed time strings
                    pass
        except Exception as e:
            print(f"[Proactive Alert Error] Failed to check alerts: {e}")
            traceback.print_exc()

    # Run the check every 1 minute
    scheduler.add_job(check_timetable_alerts, 'interval', minutes=1, id='timetable_alert_job')
    scheduler.start()
    print("[Scheduler] Proactive background alerts initialized.")
    return scheduler
