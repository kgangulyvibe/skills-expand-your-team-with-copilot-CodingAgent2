"""
In-memory database configuration and setup for Mergington High School API
Optimized for performance by eliminating external database dependencies
"""

import hashlib
from typing import Dict, List, Any, Optional
from copy import deepcopy

# In-memory storage with performance optimizations
activities_data: Dict[str, Dict[str, Any]] = {}
teachers_data: Dict[str, Dict[str, Any]] = {}

# Create indexed lookups for performance
_day_index: Dict[str, List[str]] = {}  # day -> list of activity names
_time_index: Dict[str, List[str]] = {}  # time_range -> list of activity names

def hash_password(password: str) -> str:
    """Hash password using SHA-256 for consistency and performance"""
    return hashlib.sha256(password.encode()).hexdigest()

def _build_indexes():
    """Build performance indexes for faster filtering"""
    global _day_index, _time_index
    _day_index.clear()
    _time_index.clear()
    
    for activity_name, activity in activities_data.items():
        # Index by days
        for day in activity.get("schedule_details", {}).get("days", []):
            if day not in _day_index:
                _day_index[day] = []
            _day_index[day].append(activity_name)
        
        # Index by time ranges for faster filtering
        start_time = activity.get("schedule_details", {}).get("start_time", "")
        end_time = activity.get("schedule_details", {}).get("end_time", "")
        if start_time and end_time:
            time_key = f"{start_time}-{end_time}"
            if time_key not in _time_index:
                _time_index[time_key] = []
            _time_index[time_key].append(activity_name)

def init_database():
    """Initialize in-memory database if empty - optimized for performance"""
    global activities_data, teachers_data
    
    # Initialize activities if empty
    if not activities_data:
        activities_data = deepcopy(initial_activities)
        
    # Initialize teacher accounts if empty  
    if not teachers_data:
        for teacher in initial_teachers:
            teachers_data[teacher["username"]] = teacher.copy()
    
    # Build performance indexes
    _build_indexes()

class InMemoryCollection:
    """High-performance in-memory collection that mimics MongoDB interface"""
    
    def __init__(self, data_store: Dict[str, Dict[str, Any]]):
        self.data = data_store
    
    def find(self, query: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Optimized find with indexing support"""
        if not query:
            return [{"_id": k, **v} for k, v in self.data.items()]
        
        # Optimize day-based queries using index
        if "schedule_details.days" in query:
            day_filter = query["schedule_details.days"]
            if isinstance(day_filter, dict) and "$in" in day_filter:
                day = day_filter["$in"][0]
                if day in _day_index:
                    matching_names = _day_index[day]
                    results = []
                    for name in matching_names:
                        activity = self.data.get(name)
                        if activity and self._matches_query({"_id": name, **activity}, query):
                            results.append({"_id": name, **activity})
                    return results
        
        # Fallback to full scan with optimized matching
        results = []
        for k, v in self.data.items():
            doc = {"_id": k, **v}
            if self._matches_query(doc, query):
                results.append(doc)
        return results
    
    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Optimized single document lookup"""
        # Direct ID lookup for performance
        if "_id" in query and len(query) == 1:
            doc_id = query["_id"]
            if doc_id in self.data:
                return {"_id": doc_id, **self.data[doc_id]}
            return None
        
        # Use find and return first result
        results = self.find(query)
        return results[0] if results else None
    
    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]) -> 'UpdateResult':
        """Optimized single document update"""
        doc = self.find_one(query)
        if not doc:
            return UpdateResult(0)
        
        doc_id = doc["_id"]
        
        if "$push" in update:
            for field, value in update["$push"].items():
                if field not in self.data[doc_id]:
                    self.data[doc_id][field] = []
                self.data[doc_id][field].append(value)
        
        if "$pull" in update:
            for field, value in update["$pull"].items():
                if field in self.data[doc_id] and isinstance(self.data[doc_id][field], list):
                    while value in self.data[doc_id][field]:
                        self.data[doc_id][field].remove(value)
        
        return UpdateResult(1)
    
    def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimized aggregation for day lookup"""
        results = []
        unique_days = set()
        
        for activity in self.data.values():
            days = activity.get("schedule_details", {}).get("days", [])
            for day in days:
                unique_days.add(day)
        
        return [{"_id": day} for day in sorted(unique_days)]
    
    def _matches_query(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        """Optimized query matching"""
        for key, value in query.items():
            if "." in key:
                # Handle nested keys efficiently
                keys = key.split(".")
                current = doc
                for k in keys:
                    if isinstance(current, dict) and k in current:
                        current = current[k]
                    else:
                        return False
                
                if isinstance(value, dict):
                    if "$in" in value:
                        if not isinstance(current, list) or not any(item in current for item in value["$in"]):
                            return False
                    elif "$gte" in value:
                        if current < value["$gte"]:
                            return False
                    elif "$lte" in value:
                        if current > value["$lte"]:
                            return False
                elif current != value:
                    return False
            else:
                if key not in doc or doc[key] != value:
                    return False
        return True

class UpdateResult:
    """Simple update result class"""
    def __init__(self, modified_count: int):
        self.modified_count = modified_count

# Create optimized collection instances
activities_collection = InMemoryCollection(activities_data)
teachers_collection = InMemoryCollection(teachers_data)

# Initial database if empty
initial_activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Mondays and Fridays, 3:15 PM - 4:45 PM",
        "schedule_details": {
            "days": ["Monday", "Friday"],
            "start_time": "15:15",
            "end_time": "16:45"
        },
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 7:00 AM - 8:00 AM",
        "schedule_details": {
            "days": ["Tuesday", "Thursday"],
            "start_time": "07:00",
            "end_time": "08:00"
        },
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Morning Fitness": {
        "description": "Early morning physical training and exercises",
        "schedule": "Mondays, Wednesdays, Fridays, 6:30 AM - 7:45 AM",
        "schedule_details": {
            "days": ["Monday", "Wednesday", "Friday"],
            "start_time": "06:30",
            "end_time": "07:45"
        },
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Tuesday", "Thursday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and compete in basketball tournaments",
        "schedule": "Wednesdays and Fridays, 3:15 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Wednesday", "Friday"],
            "start_time": "15:15",
            "end_time": "17:00"
        },
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore various art techniques and create masterpieces",
        "schedule": "Thursdays, 3:15 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Thursday"],
            "start_time": "15:15",
            "end_time": "17:00"
        },
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Monday", "Wednesday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and prepare for math competitions",
        "schedule": "Tuesdays, 7:15 AM - 8:00 AM",
        "schedule_details": {
            "days": ["Tuesday"],
            "start_time": "07:15",
            "end_time": "08:00"
        },
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 3:30 PM - 5:30 PM",
        "schedule_details": {
            "days": ["Friday"],
            "start_time": "15:30",
            "end_time": "17:30"
        },
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "amelia@mergington.edu"]
    },
    "Weekend Robotics Workshop": {
        "description": "Build and program robots in our state-of-the-art workshop",
        "schedule": "Saturdays, 10:00 AM - 2:00 PM",
        "schedule_details": {
            "days": ["Saturday"],
            "start_time": "10:00",
            "end_time": "14:00"
        },
        "max_participants": 15,
        "participants": ["ethan@mergington.edu", "oliver@mergington.edu"]
    },
    "Science Olympiad": {
        "description": "Weekend science competition preparation for regional and state events",
        "schedule": "Saturdays, 1:00 PM - 4:00 PM",
        "schedule_details": {
            "days": ["Saturday"],
            "start_time": "13:00",
            "end_time": "16:00"
        },
        "max_participants": 18,
        "participants": ["isabella@mergington.edu", "lucas@mergington.edu"]
    },
    "Sunday Chess Tournament": {
        "description": "Weekly tournament for serious chess players with rankings",
        "schedule": "Sundays, 2:00 PM - 5:00 PM",
        "schedule_details": {
            "days": ["Sunday"],
            "start_time": "14:00",
            "end_time": "17:00"
        },
        "max_participants": 16,
        "participants": ["william@mergington.edu", "jacob@mergington.edu"]
    }
}

initial_teachers = [
    {
        "username": "mrodriguez",
        "display_name": "Ms. Rodriguez",
        "password": hash_password("art123"),
        "role": "teacher"
     },
    {
        "username": "mchen",
        "display_name": "Mr. Chen",
        "password": hash_password("chess456"),
        "role": "teacher"
    },
    {
        "username": "principal",
        "display_name": "Principal Martinez",
        "password": hash_password("admin789"),
        "role": "admin"
    }
]

