from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import hashlib, os, requests, json, re
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'deliverx_secret_2024')
APP_VERSION = '2.0.0'

# ── WAREHOUSES ────────────────────────────────────────────────────────────────
WAREHOUSES = [
    {"id":"HW-08-1","name":"Haridwar Warehouse","city":"Haridwar","state":"Uttarakhand","lat":29.9457,"lon":78.1642,"address":"Industrial Area, Haridwar, Uttarakhand"},
    {"id":"RW-14-3","name":"Rewari Central Hub","city":"Rewari","state":"Haryana","lat":28.1931,"lon":76.6196,"address":"NH-48, Rewari, Haryana"},
    {"id":"GG-22-5","name":"Gurgaon Logistics Park","city":"Gurgaon","state":"Haryana","lat":28.4595,"lon":77.0266,"address":"Sector 37, Gurugram, Haryana"},
    {"id":"ND-31-2","name":"Noida Fulfillment Centre","city":"Noida","state":"Uttar Pradesh","lat":28.5355,"lon":77.3910,"address":"Sector 63, Noida, UP"},
    {"id":"GN-09-7","name":"Greater Noida Hub","city":"Greater Noida","state":"Uttar Pradesh","lat":28.4744,"lon":77.5040,"address":"Knowledge Park III, Greater Noida, UP"},
    {"id":"GK-17-4","name":"Greater Kailash Depot","city":"Greater Kailash","state":"Delhi","lat":28.5494,"lon":77.2347,"address":"M Block Market, Greater Kailash, New Delhi"},
    {"id":"DE-05-9","name":"Delhi East Warehouse","city":"Delhi East","state":"Delhi","lat":28.6562,"lon":77.3410,"address":"Patparganj Industrial Area, Delhi"},
    {"id":"DS-11-6","name":"Delhi South Sorting Hub","city":"Delhi South","state":"Delhi","lat":28.5245,"lon":77.1855,"address":"Okhla Industrial Estate, New Delhi"},
    {"id":"KP-33-8","name":"Kanpur Distribution Centre","city":"Kanpur","state":"Uttar Pradesh","lat":26.4499,"lon":80.3319,"address":"Panki Industrial Area, Kanpur, UP"},
    {"id":"MU-44-2","name":"Mumbai Central Depot","city":"Mumbai","state":"Maharashtra","lat":18.9388,"lon":72.8354,"address":"BKC, Bandra East, Mumbai"},
    {"id":"BN-55-1","name":"Bengaluru Tech Hub","city":"Bengaluru","state":"Karnataka","lat":12.9716,"lon":77.5946,"address":"Electronic City, Bengaluru, Karnataka"},
    {"id":"HY-66-3","name":"Hyderabad Gateway","city":"Hyderabad","state":"Telangana","lat":17.3850,"lon":78.4867,"address":"HITEC City, Hyderabad, Telangana"},
    {"id":"CH-77-5","name":"Chennai South Port Hub","city":"Chennai","state":"Tamil Nadu","lat":13.0827,"lon":80.2707,"address":"Ambattur Industrial Estate, Chennai"},
    {"id":"PU-88-7","name":"Pune Express Centre","city":"Pune","state":"Maharashtra","lat":18.5204,"lon":73.8567,"address":"Hinjewadi Phase 2, Pune, Maharashtra"},
    {"id":"JA-99-4","name":"Jaipur Pink City Hub","city":"Jaipur","state":"Rajasthan","lat":26.9124,"lon":75.7873,"address":"Sitapura Industrial Area, Jaipur"},
    {"id":"SK-03-6","name":"Srikakulam District Hub","city":"Srikakulam","state":"Andhra Pradesh","lat":18.2949,"lon":83.8938,"address":"NH-16, Srikakulam, Andhra Pradesh"},
    {"id":"LK-12-9","name":"Lucknow Central Warehouse","city":"Lucknow","state":"Uttar Pradesh","lat":26.8467,"lon":80.9462,"address":"Amausi Industrial Area, Lucknow, UP"},
    {"id":"AH-21-3","name":"Ahmedabad West Hub","city":"Ahmedabad","state":"Gujarat","lat":23.0225,"lon":72.5714,"address":"Vatva GIDC, Ahmedabad, Gujarat"},
    {"id":"KO-34-8","name":"Kolkata East Depot","city":"Kolkata","state":"West Bengal","lat":22.5726,"lon":88.3639,"address":"Dankuni Industrial Area, Kolkata"},
    {"id":"IN-45-2","name":"Indore Freight Hub","city":"Indore","state":"Madhya Pradesh","lat":22.7196,"lon":75.8577,"address":"Pithampur SEZ, Indore, MP"},
]

# ── FIREBASE INIT ─────────────────────────────────────────────────────────────
def init_firebase():
    if firebase_admin._apps:
        return firestore.client()
    try:
        cred_json = os.environ.get('FIREBASE_CREDENTIALS')
        if cred_json:
            import tempfile
            cred_dict = json.loads(cred_json)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(cred_dict, f)
                tmp = f.name
            cred = credentials.Certificate(tmp)
        else:
            possible_paths = [
                '/etc/secrets/serviceAccountKey.json',
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'serviceAccountKey.json'),
                'serviceAccountKey.json',
            ]
            key_path = next((p for p in possible_paths if os.path.exists(p)), None)
            if not key_path:
                raise FileNotFoundError(
                    'No Firebase credentials found! '
                    'On Render: add FIREBASE_CREDENTIALS as environment variable.'
                )
            print(f"Found credentials at: {key_path}")
            cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"Firebase Error: {e}")
        raise

db = init_firebase()
def hash_pw(p): return hashlib.sha256(p.encode()).hexdigest()

# ── SMART GEOCODING ───────────────────────────────────────────────────────────
def smart_geocode(address):
    headers = {'User-Agent': 'DeliverX/2.0 deliverx@app.in'}
    original = address.strip()

    # Extract landmark keywords (near X, opp X, beside X, behind X)
    landmark_match = re.search(r'(?:near|opp|opposite|beside|behind|next to|adj)\s+([^,]+)', original, re.IGNORECASE)
    landmark = landmark_match.group(1).strip() if landmark_match else None

    # Build attempt list — smart prioritization
    attempts = []
    parts = [p.strip() for p in re.split(r'[,\n]', original) if p.strip()]

    attempts.append(original)  # 1. full address

    # 2. landmark + last 2 parts (city/state)
    if landmark and len(parts) >= 2:
        attempts.append(f"{landmark}, {', '.join(parts[-2:])}")

    # 3. strip house/flat/plot numbers, keep rest
    stripped = re.sub(r'\b(?:H\.?No\.?|Plot\.?|Flat\.?|Door\.?|#)?\s*\d+[\/\-A-Za-z]*\b', '', original, flags=re.IGNORECASE).strip(' ,')
    if stripped and stripped != original:
        attempts.append(stripped)

    # 4. landmark + city
    if landmark and parts:
        attempts.append(f"{landmark}, {parts[-1]}")

    # 5. last 3 parts
    if len(parts) >= 3:
        attempts.append(', '.join(parts[-3:]))

    # 6. last 2 parts
    if len(parts) >= 2:
        attempts.append(', '.join(parts[-2:]))

    # 7. just city/last part
    if parts:
        attempts.append(parts[-1])

    seen = set()
    for attempt in attempts:
        attempt = attempt.strip(' ,')
        if not attempt or attempt in seen:
            continue
        seen.add(attempt)
        try:
            r = requests.get('https://nominatim.openstreetmap.org/search',
                params={'q': attempt, 'format': 'json', 'limit': 1,
                        'addressdetails': 1, 'countrycodes': 'in'},
                headers=headers, timeout=8)
            results = r.json()
            if results:
                res = results[0]
                addr = res.get('address', {})
                # Build short display name
                short_parts = []
                for key in ['road','neighbourhood','suburb','village','town','city','county','state_district','state']:
                    if addr.get(key) and addr[key] not in short_parts:
                        short_parts.append(addr[key])
                display = ', '.join(short_parts[:3]) if short_parts else res['display_name'].split(',')[0]
                full = res['display_name']
                return {
                    'success': True,
                    'lat': float(res['lat']),
                    'lon': float(res['lon']),
                    'display': display,
                    'full_display': full,
                    'original_input': original,
                    'matched_on': attempt
                }
        except Exception:
            continue

    return {'success': False,
            'message': f'Could not locate "{original}". Try: "Dharuhera Chowk, Rewari, Haryana"'}

# ── AUTH ──────────────────────────────────────────────────────────────────────
@app.route('/')
def splash():
    return render_template('splash.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email','').lower().strip()
        password = hash_pw(data.get('password',''))
        users = db.collection('users').where('email','==',email).where('password','==',password).limit(1).get()
        if users:
            u = users[0]
            session['uid'] = u.id
            session['name'] = u.to_dict()['name']
            return jsonify({'success': True, 'name': u.to_dict()['name']})
        return jsonify({'success': False, 'message': 'Wrong email or password'})
    return render_template('login.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email','').lower().strip()
        existing = db.collection('users').where('email','==',email).limit(1).get()
        if existing:
            return jsonify({'success': False, 'message': 'Email already registered'})
        ref = db.collection('users').add({
            'name': data.get('name',''), 'email': email,
            'phone': data.get('phone',''), 'password': hash_pw(data.get('password','')),
            'created_at': datetime.utcnow().isoformat(),
            'lifetime_earnings': 0
        })
        session['uid'] = ref[1].id
        session['name'] = data.get('name','')
        return jsonify({'success': True})
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── WAREHOUSES ENDPOINT ───────────────────────────────────────────────────────
@app.route('/warehouses')
def get_warehouses():
    q = request.args.get('q','').lower()
    if q:
        filtered = [w for w in WAREHOUSES if q in w['city'].lower() or q in w['name'].lower() or q in w['state'].lower()]
    else:
        filtered = WAREHOUSES
    return jsonify(filtered[:10])

# ── GEOCODE ───────────────────────────────────────────────────────────────────
@app.route('/geocode', methods=['POST'])
def geocode():
    data = request.get_json()
    return jsonify(smart_geocode(data.get('address','')))

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'uid' not in session: return redirect(url_for('login'))
    ride, stops = get_active_ride_and_stops()
    # Lifetime earnings
    user_doc = db.collection('users').document(session['uid']).get()
    lifetime = user_doc.to_dict().get('lifetime_earnings', 0) if user_doc.exists else 0
    return render_template('dashboard.html', name=session['name'],
                           ride=ride, stops=stops, lifetime=lifetime)

def get_active_ride_and_stops():
    rides = db.collection('rides').where('user_id','==',session['uid'])\
              .where('status','==','active').limit(1).get()
    if not rides: return None, []
    ride = {'id': rides[0].id, **rides[0].to_dict()}
    stops_raw = db.collection('stops').where('ride_id','==',ride['id']).get()
    stops = sorted([{'id':s.id,**s.to_dict()} for s in stops_raw], key=lambda x:x.get('sequence',0))
    return ride, stops

# ── RIDE MANAGEMENT ───────────────────────────────────────────────────────────
@app.route('/create_ride', methods=['POST'])
def create_ride():
    if 'uid' not in session: return jsonify({'success': False})
    data = request.get_json()
    old = db.collection('rides').where('user_id','==',session['uid']).where('status','==','active').get()
    for r in old: r.reference.update({'status':'completed'})
    ref = db.collection('rides').add({
        'user_id': session['uid'],
        'warehouse_id': data.get('warehouse_id',''),
        'warehouse_location': data['warehouse'],
        'warehouse_display': data.get('display', data['warehouse']),
        'warehouse_lat': data['lat'], 'warehouse_lon': data['lon'],
        'vehicle_number': data.get('vehicle_number',''),
        'vehicle_type': data.get('vehicle_type',''),
        'total_points': 0, 'total_payment': 0,
        'status': 'active',
        'created_at': datetime.utcnow().isoformat()
    })
    return jsonify({'success': True, 'ride_id': ref[1].id})

@app.route('/add_stop', methods=['POST'])
def add_stop():
    if 'uid' not in session: return jsonify({'success': False})
    data = request.get_json()
    rides = db.collection('rides').where('user_id','==',session['uid']).where('status','==','active').limit(1).get()
    if not rides: return jsonify({'success': False, 'message': 'Set warehouse first!'})
    ride_id = rides[0].id
    existing = db.collection('stops').where('ride_id','==',ride_id).get()
    db.collection('stops').add({
        'ride_id': ride_id,
        'location_name': data['name'],
        'display_name': data.get('display', data['name']),
        'full_address': data.get('full_address', data['name']),
        'original_input': data.get('original_input', data['name']),
        'latitude': data['lat'], 'longitude': data['lon'],
        'status': 'pending', 'reason': '', 'remark': '',
        'sequence': len(existing),
        'created_at': datetime.utcnow().isoformat()
    })
    return jsonify({'success': True, 'count': len(existing)+1})

@app.route('/remove_stop/<stop_id>', methods=['DELETE'])
def remove_stop(stop_id):
    db.collection('stops').document(stop_id).delete()
    return jsonify({'success': True})

# ── ROUTE OPTIMIZATION ────────────────────────────────────────────────────────
@app.route('/optimize_route', methods=['POST'])
def optimize_route():
    if 'uid' not in session: return jsonify({'success': False})
    rides = db.collection('rides').where('user_id','==',session['uid']).where('status','==','active').limit(1).get()
    if not rides: return jsonify({'success': False})
    ride = {'id':rides[0].id,**rides[0].to_dict()}
    stops = [{'id':s.id,**s.to_dict()} for s in db.collection('stops').where('ride_id','==',ride['id']).get()]
    warehouse = (ride['warehouse_lat'], ride['warehouse_lon'])
    unvisited, route, current = list(stops), [], warehouse
    while unvisited:
        nearest = min(unvisited, key=lambda s:(s['latitude']-current[0])**2+(s['longitude']-current[1])**2)
        route.append(nearest); current=(nearest['latitude'],nearest['longitude']); unvisited.remove(nearest)
    for i,s in enumerate(route): db.collection('stops').document(s['id']).update({'sequence':i})
    return jsonify({'success':True,'route':route,
        'warehouse':{'lat':ride['warehouse_lat'],'lon':ride['warehouse_lon'],
                     'name':ride.get('warehouse_display',ride['warehouse_location'])}})

# ── MAP ───────────────────────────────────────────────────────────────────────
@app.route('/map')
def map_page():
    if 'uid' not in session: return redirect(url_for('login'))
    return render_template('map.html', name=session['name'])

@app.route('/map_data')
def map_data():
    if 'uid' not in session: return jsonify({'success': False})
    rides = db.collection('rides').where('user_id','==',session['uid']).where('status','==','active').limit(1).get()
    if not rides: return jsonify({'success': False, 'message': 'No active ride'})
    ride = {'id':rides[0].id,**rides[0].to_dict()}
    stops_raw = db.collection('stops').where('ride_id','==',ride['id']).get()
    stops = sorted([{'id':s.id,**s.to_dict()} for s in stops_raw], key=lambda x:x.get('sequence',0))
    return jsonify({'success':True,'ride':ride,'stops':stops})

# ── COMPLETE STOP ─────────────────────────────────────────────────────────────
@app.route('/complete_stop', methods=['POST'])
def complete_stop():
    if 'uid' not in session: return jsonify({'success': False})
    data = request.get_json()
    db.collection('stops').document(data['stop_id']).update({
        'status': data['status'], 'reason': data.get('reason',''),
        'remark': data.get('remark',''), 'completed_at': datetime.utcnow().isoformat()
    })
    if data['status'] == 'completed':
        rides = db.collection('rides').where('user_id','==',session['uid']).where('status','==','active').limit(1).get()
        if rides:
            r = rides[0].to_dict()
            rides[0].reference.update({
                'total_points': r.get('total_points',0)+1,
                'total_payment': r.get('total_payment',0)+20
            })
    return jsonify({'success': True})

# ── REWARDS ───────────────────────────────────────────────────────────────────
@app.route('/reward')
def reward():
    if 'uid' not in session: return redirect(url_for('login'))
    ride, stops = get_active_ride_and_stops()
    total = len(stops)
    completed = sum(1 for s in stops if s['status']=='completed')
    failed = sum(1 for s in stops if s['status']=='failed')
    pending = sum(1 for s in stops if s['status']=='pending')
    return render_template('reward.html', name=session['name'],
        total=total, completed=completed, failed=failed, pending=pending,
        payment=completed*20, points=completed, ride=ride, stops=stops)

# ── SETTINGS / RECORDS ────────────────────────────────────────────────────────
@app.route('/settings')
def settings():
    if 'uid' not in session: return redirect(url_for('login'))
    user_doc = db.collection('users').document(session['uid']).get()
    lifetime = user_doc.to_dict().get('lifetime_earnings', 0) if user_doc.exists else 0
    return render_template('settings.html', name=session['name'],
                           lifetime=lifetime, version=APP_VERSION)

@app.route('/records')
def records():
    if 'uid' not in session: return jsonify({'success': False})
    past_rides = db.collection('rides')\
        .where('user_id','==',session['uid'])\
        .where('status','==','completed').get()
    rides_data = []
    for r in past_rides:
        rd = {'id':r.id,**r.to_dict()}
        stops_raw = db.collection('stops').where('ride_id','==',r.id).get()
        rd['stops_count'] = len(stops_raw)
        rd['completed_count'] = sum(1 for s in stops_raw if s.to_dict().get('status')=='completed')
        rides_data.append(rd)
    rides_data.sort(key=lambda x: x.get('created_at',''), reverse=True)
    return jsonify({'success':True,'rides':rides_data})

@app.route('/clear_ride', methods=['POST'])
def clear_ride():
    if 'uid' not in session: return jsonify({'success': False})
    rides = db.collection('rides').where('user_id','==',session['uid']).where('status','==','active').limit(1).get()
    for r in rides:
        for s in db.collection('stops').where('ride_id','==',r.id).get(): s.reference.delete()
        r.reference.delete()
    return jsonify({'success': True})

@app.route('/finish_ride', methods=['POST'])
def finish_ride():
    if 'uid' not in session: return jsonify({'success': False})
    rides = db.collection('rides').where('user_id','==',session['uid']).where('status','==','active').limit(1).get()
    for r in rides:
        rd = r.to_dict()
        earned = rd.get('total_payment', 0)
        r.reference.update({'status':'completed','finished_at':datetime.utcnow().isoformat()})
        # Add to lifetime earnings
        user_ref = db.collection('users').document(session['uid'])
        user_data = user_ref.get().to_dict()
        user_ref.update({'lifetime_earnings': user_data.get('lifetime_earnings',0) + earned})
    return jsonify({'success': True})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
