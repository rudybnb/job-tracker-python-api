import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import asyncpg
from typing import Optional, Dict, Any, List

# Environment variables
# Python API now uses the same Neon PostgreSQL database as Node.js app
# Construct connection string from Replit's database environment variables
PGHOST = os.getenv("PGHOST", "")
PGUSER = os.getenv("PGUSER", "")
PGPASSWORD = os.getenv("PGPASSWORD", "")
PGDATABASE = os.getenv("PGDATABASE", "")
PGPORT = os.getenv("PGPORT", "5432")

# Build connection string for Neon database (same as Node.js app)
if PGHOST and PGUSER and PGPASSWORD and PGDATABASE:
    DATABASE_URL = f"postgresql://{PGUSER}:{PGPASSWORD}@{PGHOST}:{PGPORT}/{PGDATABASE}"
    print(f"🔗 Connecting to Neon PostgreSQL: {PGDATABASE}@{PGHOST}")
else:
    DATABASE_URL = ""
    print("⚠️ Database credentials not found in environment")

# Database connection pool
db_pool: Optional[asyncpg.Pool] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - startup and shutdown"""
    global db_pool
    # Startup
    if DATABASE_URL:
        try:
            db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
            print("✅ Database connection pool created")
        except Exception as e:
            print(f"❌ Failed to create database pool: {e}")
    else:
        print("⚠️ DATABASE_URL not set")
    
    yield
    
    # Shutdown
    if db_pool:
        await db_pool.close()
        print("✅ Database connection pool closed")

# FastAPI app with lifespan
app = FastAPI(title="Telegram Workforce Bot API", lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_db():
    """Get database connection from pool"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database connection not available")
    return db_pool

# ============ PYDANTIC MODELS ============

class ConversationMessage(BaseModel):
    telegram_id: int
    role: str  # 'user' or 'assistant'
    message: str

# ============ TELEGRAM BOT API ENDPOINTS ============

@app.get("/api/telegram/worker-type/{chat_id}")
async def get_worker_type(chat_id: str):
    """Get worker type for a Telegram user"""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            # Query contractor_applications table
            user = await conn.fetchrow(
                """
                SELECT id, first_name, last_name, email, username, 
                       CASE 
                           WHEN username IN ('dalwayne', 'marius', 'mohamed', 'said.tiss', 'hamza') THEN 'day-rate'
                           ELSE 'sub-contractor'
                       END as worker_type
                FROM contractor_applications 
                WHERE telegram_id = $1 AND status = 'approved'
                LIMIT 1
                """,
                chat_id
            )
            
            if not user:
                return {
                    "success": False,
                    "error": "User not found or not approved",
                    "chat_id": chat_id
                }
            
            return {
                "success": True,
                "user": {
                    "id": user["id"],
                    "name": f"{user['first_name'] or ''} {user['last_name'] or ''}".strip(),
                    "email": user["email"],
                    "username": user["username"],
                    "worker_type": user["worker_type"]
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/telegram/hours/{chat_id}")
async def get_hours_summary(chat_id: str, period: str = "week"):
    """Get hours summary for day-rate workers"""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            # First get the contractor info from chat_id
            contractor = await conn.fetchrow(
                """
                SELECT first_name, last_name, admin_pay_rate, is_cis_registered
                FROM contractor_applications 
                WHERE telegram_id = $1 AND status = 'approved'
                LIMIT 1
                """,
                chat_id
            )
            
            if not contractor:
                return {"success": False, "error": "User not found"}
            
            contractor_name = f"{contractor['first_name'] or ''} {contractor['last_name'] or ''}".strip()
            
            # Get hourly rate for calculations
            hourly_rate = float(contractor.get("admin_pay_rate") or 9.0)
            
            # Get work sessions
            if period == "today":
                query = """
                    SELECT id, contractor_name, start_time, end_time, total_hours, 
                           job_site_location
                    FROM work_sessions
                    WHERE contractor_name = $1 
                    AND DATE(start_time) = CURRENT_DATE
                    ORDER BY start_time DESC
                """
            else:  # week
                query = """
                    SELECT id, contractor_name, start_time, end_time, total_hours,
                           job_site_location
                    FROM work_sessions
                    WHERE contractor_name = $1 
                    AND start_time >= CURRENT_DATE - INTERVAL '7 days'
                    ORDER BY start_time DESC
                """
            
            sessions = await conn.fetch(query, contractor_name)
            
            # Calculate totals with actual hourly rate
            total_hours = 0
            for s in sessions:
                if s["total_hours"]:
                    time_parts = s["total_hours"].split(":")
                    hours = float(time_parts[0]) + float(time_parts[1])/60
                    total_hours += hours
            
            total_gross = total_hours * hourly_rate
            total_net = total_gross * 0.8  # Assume 20% CIS deduction
            
            return {
                "success": True,
                "period": period,
                "contractor_name": contractor_name,
                "summary": {
                    "total_hours": round(total_hours, 2),
                    "total_sessions": len(sessions),
                    "total_gross_pay": round(total_gross, 2),
                    "total_net_pay": round(total_net, 2)
                },
                "sessions": [
                    {
                        "id": s["id"],
                        "date": s["start_time"].strftime("%Y-%m-%d"),
                        "start_time": s["start_time"].strftime("%H:%M"),
                        "end_time": s["end_time"].strftime("%H:%M") if s["end_time"] else "Active",
                        "hours": s["total_hours"] or "0:00",
                        "location": s["job_site_location"]
                    }
                    for s in sessions
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/telegram/payments/{chat_id}")
async def get_payment_status(chat_id: str):
    """Get payment status for day-rate workers"""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            # Get contractor info
            contractor = await conn.fetchrow(
                """
                SELECT first_name, last_name, admin_pay_rate, is_cis_registered
                FROM contractor_applications 
                WHERE telegram_id = $1 AND status = 'approved'
                LIMIT 1
                """,
                chat_id
            )
            
            if not contractor:
                return {"success": False, "error": "User not found"}
            
            contractor_name = f"{contractor['first_name'] or ''} {contractor['last_name'] or ''}".strip()
            
            # Get this week's hours
            week_sessions = await conn.fetch(
                """
                SELECT total_hours
                FROM work_sessions
                WHERE contractor_name = $1 
                AND start_time >= CURRENT_DATE - INTERVAL '7 days'
                """,
                contractor_name
            )
            
            # Calculate earnings based on hours and pay rate
            total_week_hours = 0
            for s in week_sessions:
                if s["total_hours"]:
                    time_parts = s["total_hours"].split(":")
                    hours = float(time_parts[0]) + float(time_parts[1])/60
                    total_week_hours += hours
            
            hourly_rate = float(contractor["admin_pay_rate"] or 9.0)
            is_cis_registered = contractor["is_cis_registered"] == "true"
            cis_rate = 20 if is_cis_registered else 30
            
            week_gross = total_week_hours * hourly_rate
            week_net = week_gross * (1 - cis_rate/100)
            
            return {
                "success": True,
                "contractor_name": contractor_name,
                "payment_info": {
                    "hourly_rate": float(contractor["admin_pay_rate"] or 0),
                    "cis_registered": contractor["is_cis_registered"] == "true",
                    "cis_rate": 20 if contractor["is_cis_registered"] == "true" else 30,
                    "this_week_gross": round(week_gross, 2),
                    "this_week_net": round(week_net, 2),
                    "cis_deduction": round(week_gross - week_net, 2)
                }
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/telegram/subcontractor/quotes/{chat_id}")
async def get_subcontractor_quotes(chat_id: str):
    """Get quotes for sub-contractors"""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            # Get contractor info
            contractor = await conn.fetchrow(
                """
                SELECT id, first_name, last_name 
                FROM contractor_applications 
                WHERE telegram_id = $1 AND status = 'approved'
                LIMIT 1
                """,
                chat_id
            )
            
            if not contractor:
                return {"success": False, "error": "User not found"}
            
            contractor_name = f"{contractor['first_name'] or ''} {contractor['last_name'] or ''}".strip()
            
            # Get jobs assigned to this contractor
            jobs = await conn.fetch(
                """
                SELECT id, title, location, description, status
                FROM jobs
                WHERE contractor_name = $1
                ORDER BY id DESC
                """,
                contractor_name
            )
            
            return {
                "success": True,
                "contractor_name": contractor_name,
                "data": [
                    {
                        "id": j["id"],
                        "title": j["title"],
                        "location": j["location"],
                        "description": j["description"],
                        "status": j["status"]
                    }
                    for j in jobs
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/telegram/subcontractor/milestones/{chat_id}")
async def get_subcontractor_milestones(chat_id: str):
    """Get milestones for sub-contractors"""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            # Get contractor info
            contractor = await conn.fetchrow(
                """
                SELECT id, first_name, last_name 
                FROM contractor_applications 
                WHERE telegram_id = $1 AND status = 'approved'
                LIMIT 1
                """,
                chat_id
            )
            
            if not contractor:
                return {"success": False, "error": "User not found"}
            
            contractor_name = f"{contractor['first_name'] or ''} {contractor['last_name'] or ''}".strip()
            
            # Get jobs and their progress
            jobs = await conn.fetch(
                """
                SELECT id, title, location, status, due_date, phases
                FROM jobs
                WHERE contractor_name = $1
                ORDER BY id DESC
                """,
                contractor_name
            )
            
            return {
                "success": True,
                "contractor_name": contractor_name,
                "data": [
                    {
                        "job_id": j["id"],
                        "title": j["title"],
                        "location": j["location"],
                        "status": j["status"],
                        "due_date": j["due_date"],
                        "phases": j["phases"]
                    }
                    for j in jobs
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/telegram/subcontractor/payment-status/{chat_id}")
async def get_subcontractor_payment_status(chat_id: str):
    """Get payment status for sub-contractors"""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            # Get contractor info
            contractor = await conn.fetchrow(
                """
                SELECT id, first_name, last_name 
                FROM contractor_applications 
                WHERE telegram_id = $1 AND status = 'approved'
                LIMIT 1
                """,
                chat_id
            )
            
            if not contractor:
                return {"success": False, "error": "User not found"}
            
            contractor_name = f"{contractor['first_name'] or ''} {contractor['last_name'] or ''}".strip()
            
            # Get jobs assigned to this contractor
            jobs = await conn.fetch(
                """
                SELECT id, title, status, due_date
                FROM jobs
                WHERE contractor_name = $1
                """,
                contractor_name
            )
            
            # Count jobs by status
            completed_jobs = [j for j in jobs if j["status"] == "completed"]
            in_progress_jobs = [j for j in jobs if j["status"] in ("assigned", "pending")]
            
            return {
                "success": True,
                "contractor_name": contractor_name,
                "data": [
                    {
                        "id": j["id"],
                        "title": j["title"],
                        "status": j["status"],
                        "due_date": j["due_date"]
                    }
                    for j in jobs
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/api/telegram/conversation-history/{telegram_id}")
async def get_conversation_history(telegram_id: int, limit: int = Query(default=10, ge=1, le=100)):
    """Get conversation history for a Telegram user"""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            # Get last N messages in chronological order (oldest first)
            messages = await conn.fetch(
                """
                SELECT role, message, created_at
                FROM conversation_history
                WHERE telegram_id = $1
                ORDER BY id DESC
                LIMIT $2
                """,
                telegram_id,
                limit
            )
            
            # Reverse to get chronological order (oldest first)
            messages = list(reversed(messages))
            
            return {
                "success": True,
                "messages": [
                    {
                        "role": m["role"],
                        "content": m["message"]
                    }
                    for m in messages
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/api/telegram/conversation-history")
async def save_conversation_message(data: ConversationMessage):
    """Save a conversation message"""
    try:
        pool = await get_db()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_history (telegram_id, role, message)
                VALUES ($1, $2, $3)
                """,
                data.telegram_id,
                data.role,
                data.message
            )
            
            return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# ============ LEGACY TWILIO TEST ENDPOINT ============

@app.post("/twiml/test")
async def twiml_test():
    """Test endpoint for Twilio TwiML"""
    xml = """
<Response>
  <Say>Twilio test path is working.</Say>
  <Hangup/>
</Response>"""
    return Response(xml.strip(), media_type="application/xml")

# ============ HEALTH CHECK ============

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "online",
        "service": "Telegram Workforce Bot API",
        "database": "connected" if db_pool else "disconnected"
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    db_status = "connected"
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
        except Exception as e:
            db_status = f"error: {str(e)}"
    else:
        db_status = "not configured"
    
    return {
        "status": "healthy",
        "database": db_status,
        "endpoints": [
            "/api/telegram/worker-type/{chat_id}",
            "/api/telegram/hours/{chat_id}",
            "/api/telegram/payments/{chat_id}",
            "/api/telegram/subcontractor/quotes/{chat_id}",
            "/api/telegram/subcontractor/milestones/{chat_id}",
            "/api/telegram/subcontractor/payment-status/{chat_id}",
            "/api/telegram/conversation-history/{telegram_id}",
            "POST /api/telegram/conversation-history"
        ]
    }
