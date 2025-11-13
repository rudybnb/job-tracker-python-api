# Job Tracker API - Render Deployment

This is the Job Tracker Telegram Bot API migrated from Replit to Render.

## Features

- FastAPI-based REST API
- PostgreSQL database integration (Neon)
- Telegram bot endpoints for contractors
- Supports both day-rate and sub-contractor workflows

## API Endpoints

### Worker Information
- `GET /api/telegram/worker-type/{chat_id}` - Get worker type and info

### Day-Rate Contractors
- `GET /api/telegram/hours/{chat_id}` - Get hours summary
- `GET /api/telegram/payments/{chat_id}` - Get payment status

### Sub-Contractors
- `GET /api/telegram/subcontractor/quotes/{chat_id}` - Get quotes
- `GET /api/telegram/subcontractor/payment-status/{chat_id}` - Get payment status
- `GET /api/telegram/subcontractor/milestones/{chat_id}` - Get milestones

## Deployment to Render

### Prerequisites
1. Render account (free tier available)
2. PostgreSQL database (Neon or Render PostgreSQL)
3. GitHub repository (optional but recommended)

### Method 1: Deploy via GitHub (Recommended)

1. **Create GitHub Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **Connect to Render**
   - Go to https://dashboard.render.com
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Render will auto-detect the `render.yaml` configuration

3. **Set Environment Variables**
   In Render dashboard, add these environment variables:
   - `PGHOST` - Your PostgreSQL host (from Neon)
   - `PGUSER` - Your PostgreSQL username
   - `PGPASSWORD` - Your PostgreSQL password
   - `PGDATABASE` - Your database name (usually `neondb`)
   - `PGPORT` - PostgreSQL port (5432)

4. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy

### Method 2: Manual Deploy

1. **Go to Render Dashboard**
   - https://dashboard.render.com

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Choose "Build and deploy from a Git repository"
   - Or upload this directory as a ZIP

3. **Configure Service**
   - Name: `job-tracker-api`
   - Runtime: `Python 3`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

4. **Add Environment Variables** (same as above)

5. **Deploy**

## Database Setup

You're already using Neon PostgreSQL. The connection details are:
- Host: `ep-snowy-water-afz138f1.c-2.us-west-2.aws.neon.tech`
- Database: `neondb`
- Port: `5432`
- User: `neondb_owner`

Just copy these values to Render's environment variables.

## Testing

Once deployed, your API will be available at:
```
https://job-tracker-api.onrender.com
```

Test endpoints:
```bash
curl https://job-tracker-api.onrender.com/api/telegram/worker-type/7617462316
```

## Updating n8n Workflow

After deployment, update your n8n workflow:

1. Find all HTTP Request nodes that call the Replit API
2. Replace the base URL from:
   ```
   https://3ea69149-eb50-4887-9984-6e6eaf9900ae-00-1za3f2ke5oajn.spock.replit.dev
   ```
   To:
   ```
   https://job-tracker-api.onrender.com
   ```

## Notes

- Render free tier may spin down after 15 minutes of inactivity
- First request after spin-down may take 30-60 seconds
- For production, consider upgrading to paid tier for always-on service
- Database credentials are the same (Neon PostgreSQL)

## Support

For issues, check:
- Render logs: Dashboard → Service → Logs
- Database connection: Verify environment variables
- n8n workflow: Update all API URLs
