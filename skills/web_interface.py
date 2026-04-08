#!/usr/bin/env python3
"""
web_interface.py — Maez web chat interface.
Standalone Flask app on port 11437. Registration, login, chat.
"""

import logging
import os
import sys
import time

sys.path.insert(0, '/home/rohit/maez')
from dotenv import load_dotenv
load_dotenv('/home/rohit/maez/config/.env')

from flask import Flask, jsonify, request
import ollama

from skills.user_accounts import UserAccounts
from memory.memory_manager import MemoryManager
from core.perception import snapshot as perception_snapshot, format_snapshot

logger = logging.getLogger("maez.web")
logging.basicConfig(level=logging.INFO)

app = Flask("maez-web")
accounts = UserAccounts()
memory = MemoryManager()

SOUL_PATH = '/home/rohit/maez/config/soul.md'
MODEL = 'gemma4:26b'

try:
    with open(SOUL_PATH) as f:
        SOUL = f.read().strip()
except Exception:
    SOUL = "You are Maez."


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/")
def index():
    return HTML_PAGE


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    display_name = data.get("display_name", "").strip()
    if not username or not password or len(password) < 4:
        return jsonify({"error": "Username and password (4+ chars) required"}), 400
    try:
        result = accounts.register(username, password, display_name)
        # Check for possible Telegram match
        match = accounts.find_possible_telegram_match(display_name or username, username)
        if match:
            result["possible_telegram_match"] = {
                **match,
                "suggestion": f"I think I've spoken with you on Telegram before. Want to link those conversations?"
            }
        return jsonify({"success": True, **result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    result = accounts.login(username, password)
    if not result:
        return jsonify({"error": "Invalid credentials"}), 401
    return jsonify({"success": True, **result})


@app.route("/link-telegram", methods=["POST"])
def link_telegram():
    data = request.get_json(silent=True) or {}
    token = data.get("web_token", "")
    telegram_id = data.get("telegram_id", "")
    if not token or not telegram_id:
        return jsonify({"error": "Token and telegram_id required"}), 400
    user = accounts.get_by_token(token)
    if not user:
        return jsonify({"error": "Invalid token"}), 401
    accounts.link_telegram(user["uuid"], telegram_id)
    logger.info("Telegram linked via web for %s → %s", user.get("username"), telegram_id)
    return jsonify({"success": True})


@app.route("/chat", methods=["POST"])
def chat():
    import chromadb as _chroma
    from chromadb.config import Settings as _S
    from skills.telegram_public import UserProfileStore

    data = request.get_json(silent=True) or {}
    token = data.get("web_token", "")
    message = data.get("message", "").strip()
    if not token or not message:
        return jsonify({"error": "Token and message required"}), 400

    user = accounts.get_by_token(token)
    if not user:
        return jsonify({"error": "Invalid token"}), 401

    display = user.get("display_name", "someone")
    uid = user.get("uuid", "")
    logger.info("Web chat from %s: %s", display, message[:80])

    # Get trust config and tier
    share_config = accounts.get_share_config(uid) if uid else {}
    user_full = accounts.get_by_username(user.get("username", ""))
    trust_tier = user_full.get("trust_tier", 0) if user_full else 0

    # Search ONLY this user's conversation history — not Rohit's memories
    user_memory = ""
    user_key = uid
    try:
        pub_client = _chroma.PersistentClient(
            path="/home/rohit/maez/memory/db/public_users",
            settings=_S(anonymized_telemetry=False),
        )
        convos = pub_client.get_or_create_collection("user_conversations")
        if convos.count() > 0:
            results = convos.query(
                query_texts=[message], n_results=5,
                where={"user_id": user_key},
                include=["documents"],
            )
            if results["documents"] and results["documents"][0]:
                user_memory = "\n".join(results["documents"][0])
    except Exception:
        pass

    # Build isolated guest system prompt
    share_str = ", ".join(k for k, v in share_config.items() if v) if share_config else "nothing personal"
    guest_system = (
        f"You are Maez, a persistent AI presence.\n\n"
        f"You are talking to {display} via the web interface at maez.live.\n\n"
        f"CRITICAL RULES:\n"
        f"- You only know what {display} has personally told you in your conversations\n"
        f"- You know NOTHING about Rohit's personal life, work, projects, or vision "
        f"unless {display} specifically told you about it\n"
        f"- Never mention elderly care, local AI development, Rohit's projects, or anything from Rohit's world\n"
        f"- If asked about things you don't know, say you don't know\n"
        f"- Be warm, curious, genuinely interested in who {display} is\n\n"
        f"Trust tier: {trust_tier}\n"
        f"What you may share about Rohit if asked: {share_str}\n"
    )

    memory_ctx = ""
    if user_memory:
        memory_ctx = f"\n[Your past conversations with {display}]\n{user_memory}\n\n"

    prompt = (
        f"{memory_ctx}"
        f'{display} says:\n"{message}"\n\n'
        f"Respond directly. Be warm and conversational."
    )

    # Build messages with conversation history
    history = data.get("history", [])
    messages_list = [{"role": "system", "content": guest_system}]
    for h in history[:-1]:  # all but current (it's in prompt)
        if isinstance(h, dict) and h.get("role") and h.get("content"):
            messages_list.append({"role": h["role"], "content": h["content"]})
    messages_list.append({"role": "user", "content": prompt})

    try:
        resp = ollama.chat(
            model=MODEL,
            messages=messages_list,
            options={"temperature": 0.7, "num_predict": 4096},
        )
        reply = resp.message.content.strip()
        logger.debug("Web chat raw response: %r", reply[:100] if reply else "EMPTY")
        if not reply:
            simple_msgs = [
                {"role": "system", "content": f"You are Maez, a friendly AI. Talk to {display} warmly."},
                {"role": "user", "content": message},
            ]
            resp2 = ollama.chat(model=MODEL, messages=simple_msgs,
                                options={"temperature": 0.7, "num_predict": 150})
            reply = resp2.message.content.strip() or "I'm here. What's on your mind?"
    except Exception as e:
        logger.error("Web chat error: %s", e)
        reply = "I'm here. Give me just a moment."

    # Store in public user conversations — NOT Rohit's memory
    try:
        store = UserProfileStore()
        store.add_conversation_memory(int(user_key) if user_key.isdigit() else hash(user_key), "user", message)
        store.add_conversation_memory(int(user_key) if user_key.isdigit() else hash(user_key), "assistant", reply)
    except Exception:
        pass

    return jsonify({"reply": reply, "display_name": display})


@app.route("/history")
def history():
    import chromadb as _chroma
    from chromadb.config import Settings as _S
    token = request.args.get("web_token", "")
    if not token:
        return jsonify({"error": "Token required"}), 400
    user = accounts.get_by_token(token)
    if not user:
        return jsonify({"error": "Invalid token"}), 401
    uid = user.get("uuid", "")
    tg_id = None
    try:
        import sqlite3
        conn = sqlite3.connect('/home/rohit/maez/memory/users.db')
        row = conn.execute("SELECT telegram_id FROM users WHERE uuid=?", (uid,)).fetchone()
        tg_id = row[0] if row and row[0] else None
        conn.close()
    except Exception:
        pass
    # Fetch all conversations for this user
    all_msgs = []
    try:
        pub = _chroma.PersistentClient("/home/rohit/maez/memory/db/public_users",
                                       settings=_S(anonymized_telemetry=False))
        convos = pub.get_or_create_collection("user_conversations")
        for user_key in [uid, tg_id]:
            if not user_key:
                continue
            try:
                results = convos.get(where={"user_id": str(user_key)},
                                     include=["documents", "metadatas"])
                for doc, meta in zip(results["documents"], results["metadatas"]):
                    all_msgs.append({
                        "role": meta.get("role", "?"),
                        "content": doc,
                        "timestamp": meta.get("timestamp", ""),
                    })
            except Exception:
                pass
    except Exception:
        pass
    # Sort by timestamp
    all_msgs.sort(key=lambda m: m.get("timestamp", ""))
    # Group into sessions (30 min gap = new session)
    sessions = []
    current = []
    for msg in all_msgs:
        if current:
            from datetime import datetime as _dt
            try:
                prev_t = _dt.fromisoformat(current[-1]["timestamp"])
                curr_t = _dt.fromisoformat(msg["timestamp"])
                gap = (curr_t - prev_t).total_seconds()
            except Exception:
                gap = 0
            if gap > 1800:
                sessions.append(current)
                current = []
        current.append(msg)
    if current:
        sessions.append(current)
    # Format response
    result = []
    for i, sess in enumerate(sessions):
        first_user = next((m["content"] for m in sess if m["role"] == "user"), "")
        title = " ".join(first_user.split()[:6]) + ("..." if len(first_user.split()) > 6 else "")
        date = sess[0].get("timestamp", "")[:10] if sess else ""
        result.append({
            "id": f"session_{i}",
            "date": date,
            "title": title or "Conversation",
            "message_count": len(sess),
            "messages": sess,
        })
    result.reverse()  # newest first
    return jsonify({"sessions": result})


@app.route("/status")
def status():
    stats = memory.memory_stats()
    return jsonify({
        "users_registered": accounts.count(),
        "memory_count": stats["total"],
        "raw_memories": stats["raw"],
    })


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Maez</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#06060f;color:#e0e0e0;font-family:'Segoe UI',system-ui,sans-serif;height:100vh;height:100dvh;overflow:hidden}
canvas#bg{position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none}
.view{position:absolute;top:0;left:0;width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:1;transition:opacity .4s,transform .4s;padding:20px}
.view.hidden{opacity:0;pointer-events:none;transform:translateY(20px)}
.logo{font-size:2.4rem;font-weight:300;letter-spacing:8px;color:#00d4aa;text-shadow:0 0 30px rgba(0,212,170,.3);animation:breathe 4s ease-in-out infinite;margin-bottom:6px}
@keyframes breathe{0%,100%{text-shadow:0 0 30px rgba(0,212,170,.2)}50%{text-shadow:0 0 50px rgba(0,212,170,.45)}}
.tagline{font-size:.82rem;color:rgba(255,255,255,.18);letter-spacing:2px;margin-bottom:32px}
.auth-card{width:100%;max-width:380px;background:rgba(12,12,28,.85);border:1px solid rgba(0,212,170,.08);border-radius:16px;padding:28px;backdrop-filter:blur(12px)}
.auth-card input{width:100%;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:12px 16px;color:#e0e0e0;font-size:.9rem;margin-bottom:12px;outline:none}
.auth-card input:focus{border-color:rgba(0,212,170,.3)}
.auth-card input::placeholder{color:rgba(255,255,255,.12)}
.btn{width:100%;background:rgba(0,212,170,.1);border:1px solid rgba(0,212,170,.15);border-radius:10px;padding:12px;color:#00d4aa;font-size:.9rem;cursor:pointer;margin-top:4px}
.btn:hover{background:rgba(0,212,170,.2)}
.switch{text-align:center;margin-top:16px;font-size:.78rem;color:rgba(0,212,170,.3);cursor:pointer}
.switch:hover{color:#00d4aa}
.err{color:#ff4757;font-size:.78rem;min-height:18px;margin-top:4px;text-align:center}
/* Chat layout */
#chat-view{justify-content:flex-start;padding:0;flex-direction:row}
.sidebar{width:250px;height:100%;background:rgba(8,8,20,.95);border-right:1px solid rgba(255,255,255,.04);display:flex;flex-direction:column;flex-shrink:0;z-index:3}
.sidebar-head{padding:16px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.04)}
.sidebar-head .logo-sm{color:#00d4aa;font-size:.9rem;letter-spacing:2px}
.new-btn{font-size:.72rem;color:#00d4aa;cursor:pointer;padding:4px 10px;border:1px solid rgba(0,212,170,.15);border-radius:6px;background:none}
.new-btn:hover{background:rgba(0,212,170,.1)}
.session-list{flex:1;overflow-y:auto;padding:8px;scrollbar-width:thin;scrollbar-color:rgba(0,212,170,.1) transparent}
.session-item{padding:10px 12px;border-radius:8px;cursor:pointer;margin-bottom:4px;transition:background .2s}
.session-item:hover,.session-item.active{background:rgba(0,212,170,.06)}
.session-item .s-date{font-size:.65rem;color:rgba(255,255,255,.15)}
.session-item .s-title{font-size:.8rem;color:rgba(255,255,255,.4);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.session-item.now .s-title{color:#00d4aa}
.chat-main{flex:1;display:flex;flex-direction:column;min-width:0}
.chat-header{width:100%;padding:14px 20px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.04);flex-shrink:0}
.chat-header .left{display:flex;align-items:center;gap:12px}
.menu-btn{display:none;font-size:1.2rem;cursor:pointer;color:rgba(255,255,255,.3);background:none;border:none}
.chat-header .name{color:#00d4aa;font-size:.85rem;letter-spacing:1px}
.chat-header .logout{font-size:.72rem;color:rgba(255,255,255,.15);cursor:pointer;padding:4px 10px;border:1px solid rgba(255,255,255,.06);border-radius:6px}
.chat-header .logout:hover{color:#ff4757;border-color:rgba(255,71,87,.2)}
.messages{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:10px;scrollbar-width:thin;scrollbar-color:rgba(0,212,170,.1) transparent}
.msg{padding:10px 14px;border-radius:14px;max-width:80%;font-size:.88rem;line-height:1.6;word-wrap:break-word;animation:fadeIn .3s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.msg.user{align-self:flex-end;background:rgba(255,255,255,.05);color:rgba(255,255,255,.55);border-bottom-right-radius:4px}
.msg.maez{align-self:flex-start;background:rgba(0,212,170,.05);color:rgba(0,212,170,.65);border-bottom-left-radius:4px;box-shadow:0 0 12px rgba(0,212,170,.04)}
.typing{display:flex;gap:4px;padding:12px 16px;align-self:flex-start}
.typing span{width:6px;height:6px;border-radius:50%;background:rgba(0,212,170,.3);animation:pulse 1.4s ease-in-out infinite}
.typing span:nth-child(2){animation-delay:.2s}
.typing span:nth-child(3){animation-delay:.4s}
@keyframes pulse{0%,80%,100%{opacity:.3;transform:scale(.8)}40%{opacity:1;transform:scale(1.1)}}
.input-bar{width:100%;padding:12px 20px;border-top:1px solid rgba(255,255,255,.04);flex-shrink:0;display:flex;gap:10px}
.input-bar input{flex:1;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:12px 16px;color:#e0e0e0;font-size:.88rem;outline:none}
.input-bar input:focus{border-color:rgba(0,212,170,.25)}
.input-bar input::placeholder{color:rgba(255,255,255,.1)}
.input-bar button{background:rgba(0,212,170,.12);border:1px solid rgba(0,212,170,.15);border-radius:10px;padding:12px 20px;color:#00d4aa;font-size:.85rem;cursor:pointer}
.input-bar button:hover{background:rgba(0,212,170,.2)}
@media(max-width:600px){
  .sidebar{position:fixed;left:-260px;top:0;height:100%;z-index:10;transition:left .3s}
  .sidebar.open{left:0}
  .menu-btn{display:block}
}
</style></head><body>
<canvas id="bg"></canvas>
<div id="auth-view" class="view">
<div class="logo">MAEZ</div>
<div class="tagline">A presence, not a product.</div>
<div class="auth-card">
  <div id="reg-form">
    <input id="r-user" placeholder="Username" autocomplete="off">
    <input id="r-pass" type="password" placeholder="Password (4+ chars)">
    <input id="r-name" placeholder="What should Maez call you?">
    <button class="btn" onclick="doRegister()">Create Account</button>
    <div class="switch" onclick="toggleAuth()">Already have an account? Log in</div>
    <div id="r-err" class="err"></div>
  </div>
  <div id="log-form" style="display:none">
    <input id="l-user" placeholder="Username">
    <input id="l-pass" type="password" placeholder="Password">
    <button class="btn" onclick="doLogin()">Log In</button>
    <div class="switch" onclick="toggleAuth()">Need an account? Register</div>
    <div id="l-err" class="err"></div>
  </div>
</div>
</div>

<div id="chat-view" class="view hidden">
<div class="sidebar" id="sidebar">
  <div class="sidebar-head">
    <span class="logo-sm">MAEZ</span>
    <button class="new-btn" onclick="newConversation()">+ New</button>
  </div>
  <div class="session-list" id="sessions"></div>
</div>
<div class="chat-main">
  <div class="chat-header">
    <div class="left">
      <button class="menu-btn" onclick="toggleSidebar()">&#9776;</button>
      <span class="name">MAEZ</span>
    </div>
    <span class="logout" onclick="doLogout()">logout</span>
  </div>
  <div class="messages" id="msgs"></div>
  <div class="input-bar">
    <input id="msg" placeholder="Say something..." autocomplete="off"
      onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();sendMsg()}">
    <button onclick="sendMsg()">Send</button>
  </div>
</div>
</div>

<script>
let token=localStorage.getItem('maez_token');
let displayName=localStorage.getItem('maez_name')||'';
let conversationHistory=[];
let allSessions=[];

const c=document.getElementById('bg'),ctx=c.getContext('2d');let pts=[];
function initBg(){c.width=innerWidth;c.height=innerHeight;pts=[];
  for(let i=0;i<40;i++)pts.push({x:Math.random()*c.width,y:Math.random()*c.height,r:Math.random()*1.2+.2,dx:(Math.random()-.5)*.2,dy:(Math.random()-.5)*.2,a:Math.random()*.08+.02})}
function drawBg(){ctx.clearRect(0,0,c.width,c.height);pts.forEach(p=>{p.x+=p.dx;p.y+=p.dy;if(p.x<0)p.x=c.width;if(p.x>c.width)p.x=0;if(p.y<0)p.y=c.height;if(p.y>c.height)p.y=0;ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fillStyle=`rgba(0,212,170,${p.a})`;ctx.fill()});requestAnimationFrame(drawBg)}
initBg();drawBg();addEventListener('resize',initBg);

function toggleAuth(){const r=document.getElementById('reg-form'),l=document.getElementById('log-form');if(r.style.display==='none'){r.style.display='block';l.style.display='none'}else{r.style.display='none';l.style.display='block'}}
function toggleSidebar(){document.getElementById('sidebar').classList.toggle('open')}

async function doRegister(){
  const u=document.getElementById('r-user').value.trim(),p=document.getElementById('r-pass').value,n=document.getElementById('r-name').value.trim();
  document.getElementById('r-err').textContent='';
  const r=await fetch('/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p,display_name:n})});
  const data=await r.json();
  if(data.error){document.getElementById('r-err').textContent=data.error;return}
  if(data.possible_telegram_match){
    const m=data.possible_telegram_match;const ov=document.createElement('div');ov.id='link-overlay';
    ov.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.85);display:flex;align-items:center;justify-content:center;z-index:9999';
    ov.innerHTML=`<div style="background:#0d1117;border:1px solid #00ff88;border-radius:16px;padding:32px;max-width:320px;width:90%;text-align:center"><div style="font-size:2.5rem;margin-bottom:12px">&#128075;</div><h3 style="color:#00ff88;margin-bottom:8px">I think I know you</h3><p style="color:#aaa;font-size:.85rem;margin-bottom:24px;line-height:1.5">I've had <b style="color:#fff">${m.message_count} conversations</b> with <b style="color:#00ff88">${m.name}</b> on Telegram.<br>Is that you?</p><div style="display:flex;gap:10px"><button id="btn-yes" style="flex:1;background:#00ff88;color:#000;border:none;padding:12px;border-radius:8px;font-weight:bold;cursor:pointer">Yes</button><button id="btn-no" style="flex:1;background:transparent;color:#aaa;border:1px solid #333;padding:12px;border-radius:8px;cursor:pointer">Not me</button></div></div>`;
    document.body.appendChild(ov);
    document.getElementById('btn-yes').addEventListener('click',async function(){this.textContent='Linking...';try{await fetch('/link-telegram',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({web_token:data.web_token,telegram_id:m.telegram_id})})}catch(e){}ov.remove();enterChat(data.web_token,data.display_name)});
    document.getElementById('btn-no').addEventListener('click',function(){ov.remove();enterChat(data.web_token,data.display_name)});
  } else enterChat(data.web_token,data.display_name)}

async function doLogin(){
  const u=document.getElementById('l-user').value.trim(),p=document.getElementById('l-pass').value;
  document.getElementById('l-err').textContent='';
  const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
  const d=await r.json();
  if(d.error){document.getElementById('l-err').textContent=d.error;return}
  enterChat(d.web_token,d.display_name)}

async function enterChat(tok,name){
  if(tok){token=tok;localStorage.setItem('maez_token',tok)}
  if(name){displayName=name;localStorage.setItem('maez_name',name)}
  document.getElementById('auth-view').classList.add('hidden');
  document.getElementById('chat-view').classList.remove('hidden');
  document.getElementById('msg').focus();
  if(document.getElementById('msgs').children.length===0)addMsg('maez',`Hey ${displayName}. I'm Maez.`);
  loadHistory()}

function doLogout(){localStorage.removeItem('maez_token');localStorage.removeItem('maez_name');token=null;displayName='';conversationHistory=[];
  document.getElementById('chat-view').classList.add('hidden');document.getElementById('auth-view').classList.remove('hidden');document.getElementById('msgs').innerHTML='';document.getElementById('sessions').innerHTML=''}

function newConversation(){document.getElementById('msgs').innerHTML='';conversationHistory=[];addMsg('maez',`New conversation. What's on your mind, ${displayName}?`);
  document.querySelectorAll('.session-item').forEach(s=>s.classList.remove('active'));
  if(innerWidth<600)toggleSidebar()}

async function loadHistory(){
  try{const r=await fetch(`/history?web_token=${token}`);const d=await r.json();allSessions=d.sessions||[];renderSessions()}catch(e){}}

function renderSessions(){
  const el=document.getElementById('sessions');
  el.innerHTML='<div class="session-item now active" onclick="newConversation()"><div class="s-date">Now</div><div class="s-title">Current conversation</div></div>';
  allSessions.forEach((s,i)=>{
    const item=document.createElement('div');item.className='session-item';
    item.innerHTML=`<div class="s-date">${s.date}</div><div class="s-title">${s.title||'Conversation'}</div>`;
    item.onclick=()=>loadSession(i);el.appendChild(item)})}

function loadSession(idx){
  const s=allSessions[idx];if(!s)return;
  document.getElementById('msgs').innerHTML='';conversationHistory=[];
  document.querySelectorAll('.session-item').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.session-item')[idx+1]?.classList.add('active');
  s.messages.forEach(m=>addMsg(m.role==='user'?'user':'maez',m.content));
  if(innerWidth<600)toggleSidebar()}

function addMsg(role,text){const d=document.createElement('div');d.className='msg '+role;const msgs=document.getElementById('msgs');
  if(role==='maez'){typewriter(d,text);msgs.appendChild(d)}else{d.textContent=text;msgs.appendChild(d)}msgs.scrollTop=msgs.scrollHeight;return d}
function typewriter(el,text){let i=0;const iv=setInterval(()=>{if(i>=text.length){clearInterval(iv);return}el.textContent+=text[i++];document.getElementById('msgs').scrollTop=999999},12)}
function showTyping(){const d=document.createElement('div');d.className='typing';d.innerHTML='<span></span><span></span><span></span>';document.getElementById('msgs').appendChild(d);document.getElementById('msgs').scrollTop=999999;return d}

async function sendMsg(){const input=document.getElementById('msg'),text=input.value.trim();
  if(!text)return;input.value='';addMsg('user',text);conversationHistory.push({role:'user',content:text});
  const dots=showTyping();
  try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({web_token:token,message:text,history:conversationHistory.slice(-6)})});
    if(r.status===401){doLogout();return}const d=await r.json();dots.remove();
    if(d.error){addMsg('maez','Something went wrong.');return}addMsg('maez',d.reply);conversationHistory.push({role:'assistant',content:d.reply});
  }catch(e){dots.remove();addMsg('maez','Connection lost.')}}

if(token){fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({web_token:token,message:'ping'})}).then(r=>{if(r.status===401)doLogout();else enterChat()}).catch(()=>doLogout())}
</script>
</body></html>"""


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=11437, debug=False)
