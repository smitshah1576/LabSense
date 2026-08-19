from datetime import datetime, time as dt_time, date as dt_date
from typing import List, Dict, Set
from ..models.enums import LabState

def compute_lab_state(operating_start: dt_time, operating_end: dt_time,
                      current_time: datetime, timetable_rows: List[Dict],
                      cancelled_timetable_ids: Set[int]) -> LabState:
    """Compute lab state: Closed > Occupied > Open.
    
    Priority:
    1. CLOSED if current time outside operating hours
    2. OCCUPIED if within hours AND a timetable row matches current day/time AND no cancellation for today
    3. OPEN otherwise
    """
    current_t = current_time.time()
    
    if not (operating_start <= current_t <= operating_end):
        return LabState.CLOSED
        
    current_day = current_time.isoweekday() # 1-7, Mon=1
    
    for row in timetable_rows:
        if row["day_of_week"] == current_day:
            if row["start_time"] <= current_t <= row["end_time"]:
                if row["timetable_id"] not in cancelled_timetable_ids:
                    return LabState.OCCUPIED
                    
    return LabState.OPEN
