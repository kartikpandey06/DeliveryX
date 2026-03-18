# DeliverX V2 — Deploy Guide
## Firebase + Railway + PWABuilder APK

---

## STEP 1 — Firebase Setup (5 mins)

1. Go to console.firebase.google.com
2. Click "Add project" → name it "deliverx" → Create
3. Left sidebar → "Firestore Database" → Create database → Start in test mode → Enable
4. Left sidebar → Project Settings (gear icon) → "Service accounts" tab
5. Click "Generate new private key" → Download JSON file
6. Rename it to: serviceAccountKey.json
7. Put it in your project folder (for local testing only — never upload to GitHub!)

---

## STEP 2 — Test Locally First

```bash
pip install flask requests firebase-admin gunicorn
python app.py
```
Open http://localhost:5000 — test signup, add stops, check map.

---

## STEP 3 — Push to GitHub

1. Go to github.com → New repository → "deliverx-app" → Create
2. Upload ALL files EXCEPT serviceAccountKey.json (the .gitignore blocks it)
3. Commit

Files to upload:
- app.py
- requirements.txt
- Procfile
- runtime.txt
- .gitignore
- templates/ folder (all 6 HTML files)
- static/ folder (icon.png)

---

## STEP 4 — Deploy on Railway

1. Go to railway.app → Login with GitHub
2. New Project → Deploy from GitHub repo → select "deliverx-app"
3. Wait for first deploy (2-3 mins)
4. Go to Settings → Networking → Generate Domain
   You get: https://deliverx-app.up.railway.app

### Add Firebase credentials on Railway:
1. Open your serviceAccountKey.json in a text editor
2. Copy the ENTIRE content (Ctrl+A, Ctrl+C)
3. Railway dashboard → Variables tab → Add variable:
   - Name:  FIREBASE_CREDENTIALS
   - Value: paste the entire JSON content
4. Also add:
   - Name:  SECRET_KEY
   - Value: any random string like "myapp_secret_xyz_2024"
5. Railway auto-redeploys → your app is live!

---

## STEP 5 — Get Clean APK (2 mins, no coding)

1. Go to pwabuilder.com
2. Paste your Railway URL: https://deliverx-app.up.railway.app
3. Click "Start" → wait for analysis
4. Click "Android" → "Download Package"
5. You get a clean APK — install on any Android phone!

### OR use GoNative (even cleaner):
1. Go to gonative.io
2. Enter your Railway URL
3. Download APK → done

---

## GEOCODING IMPROVEMENTS

The new smart geocoder tries 4 fallbacks:
1. Full address as typed
2. Address without house numbers
3. Last 2 parts (street, city)
4. Just the city name

So "42/B MG Road, Bangalore" will always find Bangalore even if the exact street isn't in the map database.

---

## MAP FEATURES (New)

Tap any stop marker → bottom sheet shows:
- Full address
- Remark field (optional note)
- ✅ Delivered button
- ❌ Failed button → reason chips (Customer absent, Wrong address etc.)
- Already completed stops show their status when tapped

---

## FIRESTORE DATA STRUCTURE

collections/
├── users/
│   └── {uid}: { name, email, phone, password, created_at }
├── rides/
│   └── {ride_id}: { user_id, warehouse_location, warehouse_lat, warehouse_lon, status, total_points, total_payment }
└── stops/
    └── {stop_id}: { ride_id, location_name, display_name, full_address, lat, lon, status, reason, remark, sequence }

