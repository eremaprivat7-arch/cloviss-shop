import os
import uuid
import asyncio
import sqlite3
import requests
import time
import json
from flask import Flask, render_template_string, request, jsonify, session, redirect
from dotenv import load_dotenv
import aiohttp
from bala_client import BalaClient

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "cloviss-super-secret-key")

BALA_BASE_URL = os.getenv("BALA_BASE_URL", "https://158.247.231.14/api/v1")
BALA_API_KEY = os.getenv("BALA_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 8846879409
DB = "shop.db"
CACHE_FILE = "catalog_cache.json"

CACHE_DATA = None
LAST_FETCH_TIME = 0
CACHE_TTL = 300

# --- БАЗА ДАННЫХ ---
def init_db():
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tg_id INTEGER UNIQUE,
        username TEXT,
        role TEXT DEFAULT 'buyer',
        balance REAL DEFAULT 0,
        login TEXT UNIQUE,
        password_hash TEXT,
        is_superadmin INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS superadmin_balance (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS balance_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id INTEGER,
        target_id INTEGER,
        amount REAL,
        reason TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    """)
    con.commit()
    con.close()

init_db()

def get_setting(key, default=None):
    con = sqlite3.connect(DB)
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row[0] if row else default

def set_setting(key, value):
    con = sqlite3.connect(DB)
    con.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
    con.commit()
    con.close()

def is_superadmin(user_id):
    con = sqlite3.connect(DB)
    row = con.execute("SELECT is_superadmin FROM users WHERE id=?", (user_id,)).fetchone()
    con.close()
    return bool(row and row[0])

def send_tg(text):
    if not BOT_TOKEN: return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}, timeout=5)
    except: pass

def calc_price(base_price, role="buyer"):
    rate = float(get_setting("rate_kzt", 6.25))
    markup = float(get_setting("buyer_markup" if role == "buyer" else "seller_markup", 30))
    return round(float(base_price) * rate * (1 + markup / 100), 2)

# --- API BALA ---
async def _fetch_catalog():
    async with aiohttp.ClientSession() as s:
        c = BalaClient(s)
        return await c.catalog()

async def _create_order(order_id, customer_ref, product_id, max_price):
    async with aiohttp.ClientSession() as s:
        c = BalaClient(s)
        return await c.create_order(order_id, customer_ref, product_id, max_price)

async def _fetch_account_info():
    async with aiohttp.ClientSession() as s:
        c = BalaClient(s)
        # Пытаемся получить инфу об аккаунте (баланс)
        try:
            url = f"{BALA_BASE_URL}/account"
            async with s.get(url, headers=c.headers, timeout=10, ssl=False) as r:
                if r.status == 200:
                    return await r.json()
                return None
        except Exception as e:
            print("Account API Error:", e)
            return None

def get_cached_catalog():
    global CACHE_DATA, LAST_FETCH_TIME
    now = time.time()
    if CACHE_DATA and (now - LAST_FETCH_TIME < CACHE_TTL): return CACHE_DATA
    try:
        data = asyncio.run(_fetch_catalog())
        CACHE_DATA = data
        LAST_FETCH_TIME = now
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return CACHE_DATA
    except Exception as e:
        print("API Error:", e)
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                CACHE_DATA = json.load(f)
            LAST_FETCH_TIME = now
            return CACHE_DATA
        return {"products": [], "groups": []}

# --- ШАБЛОН ---
HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>CLOVISS SHOP | Premium</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#0a0a0a;--card:#171717;--text:#ffffff;--muted:#a3a3a3;--accent:#f97316;--glow:rgba(249,115,22,.3)}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Inter',sans-serif}
body{background:var(--bg);color:var(--text);min-height:100vh;display:flex;justify-content:center;padding:20px;
background-image:radial-gradient(circle at 50% -20%,#1f2937 0%,var(--bg) 60%)}
.container{width:100%;max-width:1200px;margin-top:2vh;animation: fadeIn 0.8s ease-out;}

@keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

header{display:flex;justify-content:space-between;align-items:center;padding:15px 25px;background:var(--card);border-radius:20px;border:1px solid #262626;margin-bottom:40px}
.logo{font-size:24px;font-weight:800;color:#fff;cursor:pointer}
.logo span{color:var(--accent)}
.nav{display:flex;gap:20px;align-items:center}
.nav a{color:var(--muted);text-decoration:none;font-weight:600;transition:.2s}
.nav a:hover{color:#fff}
.btn-tg{background:#3b82f6;color:#fff;padding:10px 20px;border-radius:10px;text-decoration:none;font-weight:700;transition:.2s}
.btn-tg:hover{background:#2563eb;box-shadow:0 0 15px rgba(59,130,246,0.5)}

.filters{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-bottom:40px}
.filter-btn{background:var(--card);border:1px solid #262626;color:var(--muted);padding:12px 24px;
border-radius:12px;cursor:pointer;font-weight:600;transition:.3s;font-size:14px;display:flex;align-items:center;gap:8px}
.filter-btn:hover{border-color:#555;color:#fff;transform:translateY(-2px)}
.filter-btn.active{background:var(--accent);color:#000;border-color:var(--accent);box-shadow:0 0 15px var(--glow)}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}
.card{background:var(--card);border-radius:16px;padding:20px;display:flex;flex-direction:column;
justify-content:space-between;border:1px solid #262626;transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); animation: cardFadeIn 0.5s ease-out backwards;}
@keyframes cardFadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
.card:hover{transform:translateY(-8px);box-shadow:0 15px 35px -10px var(--glow);border-color:var(--accent)}
.card-title{font-size:18px;font-weight:700;margin-bottom:8px}
.os-badges{display:flex;gap:5px;margin-bottom:15px;flex-wrap:wrap}
.os-badge{display:inline-block;padding:3px 8px;border-radius:6px;font-size:11px;font-weight:700;background:#262626;color:#fff}
.os-badge.root{background:#ef4444;color:#fff;}
.os-badge.nonroot{background:#10b981;color:#000;}
.os-badge.ios{background:#333;color:#fff;border:1px solid #555;}
.os-badge.pc{background:#3b82f6;color:#fff;}
.card-bottom{display:flex;justify-content:space-between;align-items:center;margin-top:auto}
.price{font-size:22px;font-weight:800;color:var(--accent);text-shadow:0 0 10px var(--glow)}
.btn{background:var(--accent);color:#000;font-weight:700;padding:12px 24px;border-radius:10px;
border:none;cursor:pointer;font-size:14px;text-decoration:none;display:inline-block;transition:.2s}
.btn:hover{background:#fb923c;transform:scale(1.05);box-shadow:0 0 15px var(--glow)}
.btn:active{transform:scale(0.95)}

.form-box{background:var(--card);padding:35px;border-radius:20px;max-width:500px;margin:0 auto;border:1px solid #262626;box-shadow:0 20px 40px -10px rgba(0,0,0,.8)}
.input-group{margin-bottom:20px}
.input-group label{display:block;margin-bottom:8px;font-size:13px;color:var(--muted);font-weight:600}
.input-group input{width:100%;padding:14px;border-radius:10px;border:1px solid #333;
background:#0a0a0a;color:#fff;font-size:16px;transition:.2s}
.input-group input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 2px var(--glow)}
.error{color:#ef4444;text-align:center;margin-top:15px;font-size:14px;font-weight:600}
.success{color:#10b981;text-align:center;margin-top:15px;font-size:14px;font-weight:600}

.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);backdrop-filter:blur(8px);display:none;justify-content:center;align-items:center;z-index:100;opacity:0;transition: opacity 0.3s}
.modal-overlay.active{display:flex;opacity:1}
.modal-content{transform: scale(0.9); transition: transform 0.3s}
.modal-overlay.active .modal-content{transform: scale(1)}

.tariff-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px}
.tariff-btn{background:#0a0a0a;border:1px solid #333;padding:15px;border-radius:12px;cursor:pointer;transition:.2s;text-align:center}
.tariff-btn:hover{border-color:var(--accent);transform: translateY(-2px)}
.tariff-btn.active{border-color:var(--accent);background:rgba(249,115,22,.1);box-shadow: 0 0 15px var(--glow)}
.tariff-btn h4{color:#fff;font-size:14px;margin-bottom:5px}
.tariff-btn p{color:var(--accent);font-size:16px;font-weight:800}
</style>
</head>
<body>
<div class="container">
{% if page == 'login' %}
  <header>
    <div class="logo">CLOVISS <span>SHOP</span></div>
    <div class="nav">
      <a href="#">Главная</a>
      <a href="#">Магазин</a>
      <a href="#">Статус модов</a>
      <a href="#" class="btn-tg">Войти через Telegram</a>
    </div>
  </header>
  <div style="text-align:center;margin-top:10vh">
    <h1 style="font-size:48px;font-weight:800;margin-bottom:15px">CLOVISS <span>SHOP</span></h1>
    <p style="color:var(--muted);font-size:18px;margin-bottom:30px">Кто вы?</p>
    <div style="display:flex;gap:20px;justify-content:center;margin-top:30px">
      <a href="/buyer" class="btn" style="padding:15px 30px;font-size:16px">Покупатель</a>
      <a href="/seller/login" class="btn" style="padding:15px 30px;font-size:16px;background:#3b82f6;color:#fff">Продавец</a>
    </div>
  </div>

{% elif page == 'catalog' %}
  <header>
    <div class="logo" onclick="window.location.href='/'">CLOVISS <span>SHOP</span></div>
    <div class="nav">
      <a href="/">Главная</a>
      <a href="/buyer" style="color:#fff">Магазин</a>
      <a href="#">Статус модов</a>
      <a href="#" class="btn-tg">Войти через Telegram</a>
    </div>
  </header>
  
  <div class="filters">
    <button class="filter-btn active" onclick="filterProducts('all', this)">Все</button>
    <button class="filter-btn" onclick="filterProducts('android_root', this)">Android Root</button>
    <button class="filter-btn" onclick="filterProducts('android_nonroot', this)">Android Non Root</button>
    <button class="filter-btn" onclick="filterProducts('ios', this)">iPhone</button>
    <button class="filter-btn" onclick="filterProducts('pc', this)">ПК / Windows</button>
  </div>

  {% if error %}
    <div class="form-box" style="border-color:#ef4444;text-align:center">
      <h3 style="color:#ef4444;margin-bottom:10px">Ошибка API</h3>
      <p style="font-size:14px;color:var(--muted)">{{ error }}</p>
    </div>
  {% elif not grouped_products %}
    <div class="form-box" style="text-align:center">
      <h3 style="color:var(--muted);margin-bottom:10px">Товаров пока нет</h3>
    </div>
  {% else %}
    <div class="grid" id="products-grid">
    {% for group in grouped_products %}
      <div class="card" data-category="{{ group.category_key }}">
        <div>
          <div class="card-title">{{ group.name }}</div>
          <div class="os-badges">
            {% for badge in group.badges %}
              <span class="os-badge {{ badge.class }}">{{ badge.text }}</span>
            {% endfor %}
          </div>
        </div>
        <div class="card-bottom">
          <div>
            <div style="font-size:12px;color:var(--muted)">от</div>
            <span class="price">{{ group.min_price }} ₸</span>
          </div>
          <button class="btn" onclick="openModal('{{ group.id }}')">Купить</button>
        </div>
      </div>
    {% endfor %}
    </div>
  {% endif %}

{% elif page == 'success' %}
  <div style="text-align:center;margin-top:10vh;animation: fadeIn 0.5s">
    <div style="font-size:60px;margin-bottom:20px">✅</div>
    <h2 style="font-size:28px;margin-bottom:10px">Покупка успешна!</h2>
    <p style="color:var(--muted);margin-bottom:20px">Ваш ключ готов</p>
    <div class="form-box">
      <div style="background:#0a0a0a;padding:20px;border-radius:12px;font-family:monospace;
      font-size:20px;color:#fbbf24;word-break:break-all;border:1px dashed #fbbf24;cursor:pointer"
      onclick="navigator.clipboard.writeText(this.innerText.trim());document.getElementById('copy-hint').innerText='Скопировано! ✅'">
        {{ key }}
      </div>
      <div id="copy-hint" style="color:var(--muted);margin-top:15px;font-size:13px">Нажмите для копирования</div>
      <div style="margin-top:30px"><a href="/buyer" class="btn">Вернуться в магазин</a></div>
    </div>
  </div>

{% elif page == 'seller_login' %}
  <header>
    <div class="logo">CLOVISS <span>SHOP</span></div>
    <div class="nav">
      <a href="/">Главная</a>
    </div>
  </header>
  <div style="text-align:center;margin-top:10vh">
    <h2 style="font-size:32px;margin-bottom:20px">Вход для продавцов</h2>
    <div class="form-box">
      <form method="POST" action="/seller/login">
        <div class="input-group">
          <label>Логин:</label>
          <input type="text" name="login" placeholder="admin" required>
        </div>
        <div class="input-group">
          <label>Пароль:</label>
          <input type="password" name="password" placeholder="admin" required>
        </div>
        <button type="submit" class="btn" style="width:100%">Войти</button>
      </form>
      {% if error %}
        <div class="error">{{ error }}</div>
      {% endif %}
    </div>
  </div>

{% elif page == 'admin' %}
  <header>
    <div class="logo">CLOVISS <span>ADMIN</span></div>
    <div class="nav">
      <a href="/">На главную</a>
      <a href="/logout">Выйти</a>
    </div>
  </header>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:40px">
    <!-- БАЛАНС -->
    <div class="form-box" style="margin:0;max-width:100%">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:15px">
        <h3>Мой баланс (SuperAdmin)</h3>
        <button onclick="syncBalance()" class="btn" style="padding:8px 15px;font-size:12px;background:#3b82f6;color:#fff">🔄 Синхронизировать с API</button>
      </div>
      <div id="balance-display" style="font-size:48px;font-weight:800;color:var(--accent);margin-bottom:20px">{{ balance }} ₸</div>
      
      <h4 style="margin-bottom:15px">Пополнить пользователю</h4>
      <form id="topup-form" onsubmit="topUp(event)">
        <div class="input-group">
          <label>ID или Telegram (@username):</label>
          <input type="text" id="target_user" placeholder="@username" required>
        </div>
        <div class="input-group">
          <label>Сумма (₸):</label>
          <input type="number" id="amount" placeholder="1000" required>
        </div>
        <button type="submit" class="btn" style="width:100%">Пополнить</button>
      </form>
      <div id="topup-msg" style="margin-top:15px;text-align:center"></div>
    </div>

    <!-- НАСТРОЙКИ НАЦЕНКИ -->
    <div class="form-box" style="margin:0;max-width:100%">
      <h3 style="margin-bottom:15px">Настройки наценки</h3>
      <form id="markup-form" onsubmit="saveMarkup(event)">
        <div class="input-group">
          <label>Наценка для Покупателей (%):</label>
          <input type="number" id="buyer_markup" value="{{ buyer_markup }}" required>
        </div>
        <div class="input-group">
          <label>Наценка для Продавцов (%):</label>
          <input type="number" id="seller_markup" value="{{ seller_markup }}" required>
        </div>
        <div class="input-group">
          <label>Курс (1 pcoin в тенге):</label>
          <input type="number" step="0.01" id="rate_kzt" value="{{ rate_kzt }}" required>
        </div>
        <button type="submit" class="btn" style="width:100%">Сохранить</button>
      </form>
      <div id="markup-msg" style="margin-top:15px;text-align:center"></div>
    </div>
  </div>
{% endif %}
</div>

{% if page == 'catalog' and grouped_products %}
<div class="modal-overlay" id="modal">
  <div class="form-box modal-content" style="margin:0;width:90%">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <h2 style="font-size:20px">Выбери тариф</h2>
      <button onclick="closeModal()" style="background:none;border:none;color:#fff;font-size:24px;cursor:pointer">&times;</button>
    </div>
    
    <p style="color:var(--muted);font-size:14px;margin-bottom:15px">Выберите тариф:</p>
    <div class="tariff-grid" id="tariff-container"></div>

    <div class="input-group" style="margin-top:20px">
      <label>Ваш Telegram (для связи):</label>
      <input type="text" id="m-nick" placeholder="@username" required>
    </div>
    
    <button class="btn" style="width:100%;padding:15px" onclick="submitOrder()" id="pay-btn">
      <span id="btn-text">Купить</span>
    </button>
    <div class="error" id="m-error"></div>
  </div>
</div>

<script>
const groupsData = {{ grouped_products|tojson|safe }};
let selectedProductId = null;

function filterProducts(cat, btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('#products-grid .card').forEach(card => {
    if (cat === 'all' || card.getAttribute('data-category') === cat) {
      card.style.display = 'flex';
      card.style.animation = 'none';
      card.offsetHeight; /* trigger reflow */
      card.style.animation = 'cardFadeIn 0.4s ease-out forwards';
    } else {
      card.style.display = 'none';
    }
  });
}

function openModal(groupId) {
  const group = groupsData.find(g => g.id === groupId);
  if (!group) return;
  
  const container = document.getElementById('tariff-container');
  container.innerHTML = '';
  
  const sortedTariffs = group.tariffs.sort((a, b) => a.price - b.price);
  
  sortedTariffs.forEach((t, index) => {
    const div = document.createElement('div');
    div.className = `tariff-btn ${index === 0 ? 'active' : ''}`;
    if (index === 0) selectedProductId = t.id;
    
    div.innerHTML = `<h4>${t.name}</h4><p>${t.price} ₸</p>`;
    div.onclick = () => {
      document.querySelectorAll('.tariff-btn').forEach(b => b.classList.remove('active'));
      div.classList.add('active');
      selectedProductId = t.id;
    };
    container.appendChild(div);
  });

  document.getElementById('m-nick').value = '';
  document.getElementById('modal').classList.add('active');
  document.getElementById('m-error').innerText = '';
  document.getElementById('btn-text').innerText = 'Купить';
  document.getElementById('pay-btn').disabled = false;
}

function closeModal(){document.getElementById('modal').classList.remove('active');}

async function submitOrder(){
  const nick = document.getElementById('m-nick').value.trim();
  if(!nick){document.getElementById('m-error').innerText='Введите ваш Telegram!';return;}
  if(!selectedProductId){document.getElementById('m-error').innerText='Выберите тариф!';return;}
  
  const btn=document.getElementById('pay-btn'), t=document.getElementById('btn-text');
  btn.disabled=true; t.innerText='Обработка...';
  document.getElementById('m-error').innerText='';
  
  try{
    const r=await fetch('/api/buy',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({product_id:selectedProductId,customer_ref:nick})});
    const d=await r.json();
    if(r.ok){window.location.href='/success?key='+encodeURIComponent(d.key);}
    else{document.getElementById('m-error').innerText=d.error||'Ошибка';btn.disabled=false;t.innerText='Повторить';}
  }catch(e){document.getElementById('m-error').innerText='Сетевая ошибка';btn.disabled=false;t.innerText='Повторить';}
}
</script>
{% endif %}

{% if page == 'admin' %}
<script>
async function syncBalance() {
  const msg = document.getElementById('topup-msg');
  msg.className = 'success'; msg.innerText = 'Синхронизация...';
  
  try {
    const r = await fetch('/api/admin/sync_balance', { method: 'POST' });
    const d = await r.json();
    if (r.ok) {
      msg.className = 'success'; msg.innerText = 'Баланс обновлен!';
      document.getElementById('balance-display').innerText = d.balance + ' ₸';
    } else {
      msg.className = 'error'; msg.innerText = d.error || 'Ошибка синхронизации';
    }
  } catch(e) { msg.className = 'error'; msg.innerText = 'Сетевая ошибка'; }
}

async function topUp(e) {
  e.preventDefault();
  const target = document.getElementById('target_user').value;
  const amount = document.getElementById('amount').value;
  const msg = document.getElementById('topup-msg');
  
  msg.className = 'success'; msg.innerText = 'Обработка...';
  
  try {
    const r = await fetch('/api/admin/topup', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({target, amount: parseFloat(amount)})
    });
    const d = await r.json();
    if (r.ok) {
      msg.className = 'success'; msg.innerText = 'Успешно! Баланс пополнен.';
      document.getElementById('balance-display').innerText = (parseFloat(document.getElementById('balance-display').innerText) - amount) + ' ₸';
    } else {
      msg.className = 'error'; msg.innerText = d.error || 'Ошибка';
    }
  } catch(e) { msg.className = 'error'; msg.innerText = 'Сетевая ошибка'; }
}

async function saveMarkup(e) {
  e.preventDefault();
  const buyer = document.getElementById('buyer_markup').value;
  const seller = document.getElementById('seller_markup').value;
  const rate = document.getElementById('rate_kzt').value;
  const msg = document.getElementById('markup-msg');
  
  msg.className = 'success'; msg.innerText = 'Сохранение...';
  
  try {
    const r = await fetch('/api/admin/settings', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({buyer_markup: buyer, seller_markup: seller, rate_kzt: rate})
    });
    const d = await r.json();
    if (r.ok) {
      msg.className = 'success'; msg.innerText = 'Настройки сохранены!';
    } else {
      msg.className = 'error'; msg.innerText = d.error || 'Ошибка';
    }
  } catch(e) { msg.className = 'error'; msg.innerText = 'Сетевая ошибка'; }
}
</script>
{% endif %}
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML, page="login")

@app.route("/buyer")
def buyer():
    try:
        data = get_cached_catalog()
        products_raw = data.get("products", [])
        groups_raw = data.get("groups", [])
    except Exception as e:
        return render_template_string(HTML, page="catalog", grouped_products=[], error=str(e))
    
    grouped_dict = {}
    for p in products_raw:
        if not p.get("available", True): continue
        group_id = p.get("group_id", "other")
        group_name = "Другое"
        category_name = "other"
        for g in groups_raw:
            if g["id"] == group_id:
                group_name = g["name"]
                category_name = g.get("category_name", "other").lower()
                break
                
        category_key = "other"
        badges = []
        name_lower = group_name.lower() + " " + p.get("name", "").lower()
        
        if "android" in category_name or "android" in group_id:
            if "root" in name_lower and "non root" not in name_lower and "nonroot" not in name_lower:
                category_key = "android_root"; badges.append({"text": "Root", "class": "root"})
            else:
                category_key = "android_nonroot"; badges.append({"text": "Non Root", "class": "nonroot"})
        elif "ios" in category_name or "ios" in group_id:
            category_key = "ios"; badges.append({"text": "iOS", "class": "ios"})
        elif "pc" in category_name or "pc" in group_id:
            category_key = "pc"; badges.append({"text": "PC", "class": "pc"})
        if not badges: badges.append({"text": "Multi", "class": "nonroot"})

        if group_id not in grouped_dict:
            grouped_dict[group_id] = {"id": group_id, "name": group_name, "category_key": category_key, "badges": badges, "tariffs": []}
            
        grouped_dict[group_id]["tariffs"].append({
            "id": p["id"], "name": p.get("name"), "price": calc_price(p.get("price_pcoins", 0), role="buyer")
        })
        
    grouped_products = []
    for gid, gdata in grouped_dict.items():
        gdata["min_price"] = min(t["price"] for t in gdata["tariffs"])
        grouped_products.append(gdata)
    grouped_products.sort(key=lambda x: x["name"])
    return render_template_string(HTML, page="catalog", grouped_products=grouped_products)

@app.route("/success")
def success():
    return render_template_string(HTML, page="success", key=request.args.get("key", "—"))

# --- SELLER / ADMIN ROUTES ---
@app.route("/seller/login", methods=["GET", "POST"])
def seller_login():
    if request.method == "POST":
        login = request.form.get("login")
        password = request.form.get("password")
        if login == "admin" and password == "admin":
            session["user_id"] = 1 
            session["role"] = "admin"
            return redirect("/admin")
        return render_template_string(HTML, page="seller_login", error="Неверный логин или пароль")
    return render_template_string(HTML, page="seller_login")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/admin")
def admin():
    uid = session.get("user_id")
    if not uid or not is_superadmin(uid):
        return redirect("/seller/login")
    
    con = sqlite3.connect(DB)
    bal_row = con.execute("SELECT balance FROM superadmin_balance WHERE user_id=?", (uid,)).fetchone()
    balance = bal_row[0] if bal_row else 0
    con.close()
    
    return render_template_string(HTML, page="admin", 
        balance=balance, 
        buyer_markup=get_setting("buyer_markup", 30),
        seller_markup=get_setting("seller_markup", 10),
        rate_kzt=get_setting("rate_kzt", 6.25)
    )

@app.route("/api/admin/sync_balance", methods=["POST"])
def api_admin_sync_balance():
    uid = session.get("user_id")
    if not uid or not is_superadmin(uid): return jsonify({"error": "Доступ запрещен"}), 403
    
    # Пытаемся получить реальный баланс из API
    try:
        account_info = asyncio.run(_fetch_account_info())
        
        # Если API вернул JSON, ищем поле с балансом
        real_balance = 0.0
        if account_info:
            # Ищем баланс по разным возможным ключам
            real_balance = (
                account_info.get("balance") or 
                account_info.get("pcoins") or 
                account_info.get("amount") or 
                0.0
            )
        
        # Обновляем баланс в БД
        con = sqlite3.connect(DB)
        con.execute("UPDATE superadmin_balance SET balance=? WHERE user_id=?", (real_balance, uid))
        con.commit()
        con.close()
        
        return jsonify({"success": True, "balance": real_balance})
    except Exception as e:
        print("Sync Error:", e)
        # Если не удалось, возвращаем текущий баланс из БД
        con = sqlite3.connect(DB)
        bal_row = con.execute("SELECT balance FROM superadmin_balance WHERE user_id=?", (uid,)).fetchone()
        current_balance = bal_row[0] if bal_row else 0
        con.close()
        return jsonify({"success": True, "balance": current_balance, "note": "API недоступен, показан текущий баланс"})

@app.route("/api/admin/topup", methods=["POST"])
def api_admin_topup():
    uid = session.get("user_id")
    if not uid or not is_superadmin(uid):
        return jsonify({"error": "Доступ запрещен"}), 403
        
    data = request.json
    target = data.get("target", "").strip()
    amount = float(data.get("amount", 0))
    
    if amount <= 0:
        return jsonify({"error": "Сумма должна быть больше нуля"}), 400

    con = sqlite3.connect(DB)
    target_clean = target.replace("@", "")
    user = con.execute("SELECT id FROM users WHERE tg_id=? OR username=?", (target, target_clean)).fetchone()
    if not user:
        con.close()
        return jsonify({"error": "Пользователь не найден"}), 404
        
    target_id = user[0]
    
    bal_row = con.execute("SELECT balance FROM superadmin_balance WHERE user_id=?", (uid,)).fetchone()
    current_bal = bal_row[0] if bal_row else 0
    
    if current_bal < amount:
        con.close()
        return jsonify({"error": "Недостаточно средств на вашем балансе"}), 400
        
    con.execute("UPDATE superadmin_balance SET balance=balance-? WHERE user_id=?", (amount, uid))
    con.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, target_id))
    con.execute("INSERT INTO balance_log(actor_id, target_id, amount, reason) VALUES(?,?,?,?)",
                (uid, target_id, amount, "admin_topup"))
    con.commit()
    con.close()
    
    return jsonify({"success": True})

@app.route("/api/admin/settings", methods=["POST"])
def api_admin_settings():
    uid = session.get("user_id")
    if not uid or not is_superadmin(uid):
        return jsonify({"error": "Доступ запрещен"}), 403
        
    data = request.json
    try:
        set_setting("buyer_markup", data["buyer_markup"])
        set_setting("seller_markup", data["seller_markup"])
        set_setting("rate_kzt", data["rate_kzt"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/buy", methods=["POST"])
def api_buy():
    data = request.json or {}
    product_id = data.get("product_id")
    customer_ref = data.get("customer_ref", "").strip()
    if not product_id or not customer_ref:
        return jsonify({"error": "Не хватает данных"}), 400
    
    try:
        catalog = get_cached_catalog()
        products = {p["id"]: p for p in catalog.get("products", [])}
    except Exception as e:
        return jsonify({"error": f"Каталог недоступен: {e}"}), 500
        
    if product_id not in products:
        return jsonify({"error": "Товар не найден"}), 404
        
    base_price = products[product_id]["price_pcoins"]
    final_price = calc_price(base_price, role="buyer")
    order_id = "order_" + uuid.uuid4().hex[:12]
    
    try:
        resp, status = asyncio.run(_create_order(order_id, customer_ref, product_id, base_price))
    except Exception as e:
        return jsonify({"error": f"Ошибка API: {e}"}), 500
        
    if status not in (200, 201):
        return jsonify({"error": resp.get("error", "Ошибка BALA")}), 400
        
    key = resp.get("key") or resp.get("license_key") or "—"
    send_tg(f"💰 <b>Новая продажа!</b>\\nКлиент: {customer_ref}\\nТовар: {products[product_id]['display_name']}\\nЦена: {final_price} ₸\\nКлюч: <code>{key}</code>")
    return jsonify({"success": True, "key": key})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)