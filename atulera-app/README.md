# ATULÉRA Website — Full Stack (Flask)

## Ye kya hai
- Public website (Home, About, Services, Solutions, Process, Why Us, Vision/Mission, FAQ, Contact)
- Har service ka apna **detail page** (`/services/<slug>`) — Benefits, "Who is this for", step-by-step process, aur ek "Request this service" form
- Services database se aate hain — admin panel se naye service/feature add/edit/delete kar sakte ho, **koi code change nahi chahiye**
- **Service Requests** — jab koi visitor kisi service page se "Request this service" bharta hai, wo alag se admin panel me dikhta hai with status tracking (New → Contacted → In Progress → Completed → Cancelled)
- General **Contact Form** (homepage) alag se admin panel me "Contact Form Responses" me dikhta hai
- On-site assistant (bottom-right chat icon) — visitor kuch type kare (jaise "website", "tax", "GST") to matching service ke seedhe detail page ka link deta hai
- FAQ section bhi admin se manage hoti hai, aur assistant usi data ko search karta hai

## Local pe chalane ka tarika

```bash
cd atulera-app
pip install -r requirements.txt
python app.py
```

Browser me kholo: **http://localhost:5000**

Pehli baar chalane par `atulera.db` (SQLite database) apne aap ban jaayega, saath me starting services aur FAQs bhi.

## Admin Panel

URL: **http://localhost:5000/admin/login**

Default login:
- Username: `admin`
- Password: `atulera123`

⚠️ **Live karne se pehle password zaroor badal do** — admin dashboard ke sabse neeche "Change Admin Password" section se.

Admin panel se ye sab ho sakta hai:
1. **Services & Features** — naya service add karo (title, description, benefits, "kis ke liye hai", step-by-step process — sab kuch), purana edit/delete karo, order badlo, on/off karo. Har service ka apna live detail page turant ban jaata hai, koi code nahi likhna padta.
2. **Service Requests** — koi bhi specific service ke liye request bharta hai to yahan dikhta hai, status dropdown se track karo (New/Contacted/In Progress/Completed/Cancelled)
3. **Contact Form Responses** — homepage ke general contact form ke messages, "Mark responded" dabakar note ke saath close karo
4. **FAQs** — naye sawaal-jawab add/delete karo (ye assistant widget me bhi use hote hain)
5. **Password** — apna admin password change karo

## Live/Host kaise karo

Ye ek real Flask app hai (static HTML file nahi), isliye isko host karne ke liye Python server chahiye. Aasan options:

### Option A — Render.com (free tier available, sabse easy)
1. Is poore `atulera-app` folder ko GitHub repo me daalo
2. Render.com pe naya "Web Service" banao, apna GitHub repo connect karo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app` (isके liye requirements.txt me `gunicorn` add karna hoga — neeche note dekho)
5. Deploy dabao — kuch minute me live URL mil jaayega

### Option B — PythonAnywhere (beginner-friendly, free tier)
1. Files upload karo (ya GitHub se clone)
2. "Web" tab me naya Flask app configure karo, pointing to `app.py`
3. Reload dabao — live ho jaayega apne `<username>.pythonanywhere.com` domain par

### Custom domain jodna
Dono platforms pe "Custom Domain" setting milti hai — apna domain (jaise atulera.in) DNS me CNAME/A record add karke jod sakte ho. Domain kisi bhi registrar se (GoDaddy, Hostinger, Namecheap) le sakte ho.

### Production ke liye zaroori badlaav
1. `app.py` me `app.secret_key` ko ek random secure string se replace karo
2. Admin password change karo (upar dekha gaya)
3. `requirements.txt` me `gunicorn` add karo aur `app.run(debug=True, ...)` ko production me `debug=False` rakho
4. Passwords abhi plain text me DB me store hote hain (simple rakhne ke liye) — agar zyada security chahiye to bcrypt hashing add karwa sakte ho

## Naye service/feature add karne ka sabse aasan tarika (client ke liye)
1. `/admin/login` pe login karo
2. "Services & Features" section me "+ Add a new service / feature" click karo
3. Group (Financial/Digital), Title, Description bharo, "Add service" dabao
4. Website turant update ho jaayegi — koi code change nahi chahiye
