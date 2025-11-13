# Job Tracker Python API - Deployment Guide

## Quick Deploy to Render (5 minutes)

### Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `job-tracker-python-api`
3. Description: `Telegram Bot API for Job Tracker`
4. **Make it PUBLIC** (required for Render free tier)
5. **DO NOT** initialize with README
6. Click "Create repository"

### Step 2: Upload Code to GitHub

**Option A: Using GitHub Web Interface (Easiest)**

1. On the new repository page, click "uploading an existing file"
2. Drag and drop these files:
   - `app.py`
   - `requirements.txt`
   - `render.yaml`
   - `README.md`
   - `.gitignore`
3. Commit message: "Initial commit - Python API"
4. Click "Commit changes"

**Option B: Using Git Command Line**

```bash
cd job-tracker-render
git remote add origin https://github.com/rudybnb/job-tracker-python-api.git
git push -u origin main
```

### Step 3: Deploy to Render

1. Go to https://dashboard.render.com/web/new
2. Click "Git Provider" tab
3. Find and click on `rudybnb/job-tracker-python-api`
4. Render will auto-detect the `render.yaml` configuration
5. **IMPORTANT:** Add environment variables:
   - `PGHOST` = `ep-snowy-water-afz138f1.c-2.us-west-2.aws.neon.tech`
   - `PGUSER` = `neondb_owner`
   - `PGPASSWORD` = `npg_lFfhbM4LPhwd`
   - `PGDATABASE` = `neondb`
   - `PGPORT` = `5432`
6. Click "Create Web Service"
7. Wait 2-3 minutes for deployment

### Step 4: Get Your New API URL

After deployment completes, you'll get a URL like:
```
https://job-tracker-python-api.onrender.com
```

### Step 5: Update n8n Workflow

1. Open your n8n workflow
2. Find all HTTP Request nodes that call the Replit API
3. Replace the base URL from:
   ```
   https://3ea69149-eb50-4887-9984-6e6eaf9900ae-00-1za3f2ke5oajn.spock.replit.dev
   ```
   To your new Render URL:
   ```
   https://job-tracker-python-api.onrender.com
   ```
4. Test with: `/api/telegram/worker-type/7617462316`

## Environment Variables Reference

Copy these to Render's Environment Variables section:

```
PGHOST=ep-snowy-water-afz138f1.c-2.us-west-2.aws.neon.tech
PGUSER=neondb_owner
PGPASSWORD=npg_lFfhbM4LPhwd
PGDATABASE=neondb
PGPORT=5432
```

## Testing Your Deployment

Once deployed, test these endpoints:

```bash
# Test worker lookup
curl https://job-tracker-python-api.onrender.com/api/telegram/worker-type/7617462316

# Should return:
{
  "success": true,
  "user": {
    "name": "Rudy Diedericks",
    "worker_type": "sub-contractor",
    ...
  }
}
```

## Troubleshooting

### Deployment fails
- Check logs in Render dashboard
- Verify all environment variables are set
- Ensure Python version is 3.11

### Database connection fails
- Verify PGHOST, PGUSER, PGPASSWORD are correct
- Check Neon database is active
- Test connection from Replit first

### n8n bot not working
- Verify you updated ALL HTTP Request nodes
- Check the new URL is accessible
- Test endpoints manually with curl

## Important Notes

- **Free tier limitations:** Service spins down after 15 minutes of inactivity
- **First request after spin-down:** May take 30-60 seconds
- **For production:** Consider upgrading to paid tier ($7/month) for always-on
- **Database:** You're using Neon PostgreSQL (external), so no database migration needed

## Support

If you encounter issues:
1. Check Render logs: Dashboard → Service → Logs
2. Verify environment variables match exactly
3. Test API endpoints with curl before updating n8n
