# Vercel environment variables
# Set these in Vercel dashboard → Settings → Environment Variables

# Shared password for PWA lock screen
VITE_APP_PASSWORD=your-shared-password

# GitHub repo (used by PWA to fetch JSON data)
VITE_GITHUB_REPO=username/pricetracker
VITE_GITHUB_BRANCH=main

# GitHub Personal Access Token (server-side only — never prefix with VITE_)
GITHUB_PAT=ghp_xxxxxxxxxxxx
GITHUB_REPO=username/pricetracker
GITHUB_BRANCH=main

# Email alerts (GitHub Actions secrets)
RESEND_API_KEY=re_xxxxxxxxxxxx
ALERT_EMAIL=you@email.com
FROM_EMAIL=alerts@yourdomain.com
