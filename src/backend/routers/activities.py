"""
Endpoints for the High School Management System API
Performance optimized with caching and efficient filtering
"""

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, List
import hashlib
import json

from ..database import activities_collection, teachers_collection

router = APIRouter(
    prefix="/activities",
    tags=["activities"]
)

# Simple in-memory cache for performance
_cache: Dict[str, Dict[str, Any]] = {}

def _generate_cache_key(day: Optional[str], start_time: Optional[str], end_time: Optional[str], 
                       page: int = 1, page_size: int = 50) -> str:
    """Generate cache key for query parameters"""
    params = f"day={day or ''}&start_time={start_time or ''}&end_time={end_time or ''}&page={page}&page_size={page_size}"
    return hashlib.md5(params.encode()).hexdigest()

def _invalidate_cache():
    """Invalidate cache when data changes"""
    global _cache
    _cache.clear()

@router.get("/", response_model=Dict[str, Any])
def get_activities(
    response: Response,
    day: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    page: int = Query(1, ge=1, description="Page number (starting from 1)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)")
) -> Dict[str, Any]:
    """
    Get all activities with their details, with optional filtering by day and time
    Performance optimized with caching and efficient filtering
    
    - day: Filter activities occurring on this day (e.g., 'Monday', 'Tuesday')
    - start_time: Filter activities starting at or after this time (24-hour format, e.g., '14:30')
    - end_time: Filter activities ending at or before this time (24-hour format, e.g., '17:00')
    - page: Page number for pagination (default: 1)
    - page_size: Number of items per page (default: 50, max: 100)
    """
    # Generate cache key including pagination
    cache_key = _generate_cache_key(day, start_time, end_time, page, page_size)
    
    # Check cache first for performance
    if cache_key in _cache:
        # Add cache headers for client-side caching
        response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
        response.headers["ETag"] = cache_key
        return _cache[cache_key]
    
    # Build the query based on provided filters
    query = {}
    
    if day:
        query["schedule_details.days"] = {"$in": [day]}
    
    if start_time:
        query["schedule_details.start_time"] = {"$gte": start_time}
    
    if end_time:
        query["schedule_details.end_time"] = {"$lte": end_time}
    
    # Query the database with optimized collection
    all_activities = []
    for activity in activities_collection.find(query):
        name = activity.pop('_id')
        all_activities.append((name, activity))
    
    # Apply pagination
    total_count = len(all_activities)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_activities = all_activities[start_idx:end_idx]
    
    # Convert to response format
    activities = {}
    for name, activity in paginated_activities:
        activities[name] = activity
    
    # Prepare response with pagination metadata
    result = {
        "activities": activities,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": (total_count + page_size - 1) // page_size,
            "has_next": end_idx < total_count,
            "has_previous": page > 1
        }
    }
    
    # For backward compatibility, return just activities if no pagination requested
    if page == 1 and page_size >= total_count:
        result = activities
    
    # Cache the result for future requests
    _cache[cache_key] = result
    
    # Add cache headers
    response.headers["Cache-Control"] = "public, max-age=300"  # 5 minutes
    response.headers["ETag"] = cache_key
    
    return result

@router.get("/days", response_model=List[str])
def get_available_days() -> List[str]:
    """Get a list of all days that have activities scheduled - optimized"""
    # Use aggregation pipeline for efficient processing
    days = []
    for day_doc in activities_collection.aggregate([]):
        days.append(day_doc["_id"])
    
    return sorted(days)  # Sort for consistent output

@router.post("/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, teacher_username: Optional[str] = Query(None)):
    """Sign up a student for an activity - requires teacher authentication"""
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required for this action")
    
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Get the activity
    activity = activities_collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400, detail="Already signed up for this activity")

    # Add student to participants
    result = activities_collection.update_one(
        {"_id": activity_name},
        {"$push": {"participants": email}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update activity")
    
    # Invalidate cache since data changed
    _invalidate_cache()
    
    return {"message": f"Signed up {email} for {activity_name}"}

@router.post("/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, teacher_username: Optional[str] = Query(None)):
    """Remove a student from an activity - requires teacher authentication"""
    # Check teacher authentication
    if not teacher_username:
        raise HTTPException(status_code=401, detail="Authentication required for this action")
    
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")
    
    # Get the activity
    activity = activities_collection.find_one({"_id": activity_name})
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400, detail="Not registered for this activity")

    # Remove student from participants
    result = activities_collection.update_one(
        {"_id": activity_name},
        {"$pull": {"participants": email}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update activity")
    
    # Invalidate cache since data changed
    _invalidate_cache()
    
    return {"message": f"Unregistered {email} from {activity_name}"}