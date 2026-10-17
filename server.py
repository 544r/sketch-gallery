#!/usr/bin/env python3
"""写生画廊 · 登录与管理后台服务（nginx 反向代理到 127.0.0.1:8081）"""
import hmac, hashlib, json, os, re, time, secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qs

ROOT = os.environ.get('GALLERY_ROOT', '/opt/gallery')
WWW = f'{ROOT}/www'
STATE = f'{ROOT}/state'
VIEW_PW = os.environ['GALLERY_PASSWORD']
DEFAULT_ADMIN_PW = os.environ['ADMIN_PASSWORD']  # 首次登录后台后可在后台修改，之后以哈希存储
SECRET = os.environ['GALLERY_SECRET'].encode()
MAX_AGE = 7 * 24 * 3600
ID_RE = re.compile(r'^[a-z0-9]{1,24}$')
fails = {}
os.makedirs(STATE, exist_ok=True)

def admin_pw_ok(pw):
    f = f'{STATE}/admin.json'
    if os.path.exists(f):
        d = json.load(open(f))
        h = hashlib.sha256((d['salt'] + pw).encode()).hexdigest()
        return hmac.compare_digest(h, d['hash'])
    return hmac.compare_digest(pw.encode(), DEFAULT_ADMIN_PW.encode())

def set_admin_pw(pw):
    salt = secrets.token_hex(8)
    json.dump({'salt': salt, 'hash': hashlib.sha256((salt + pw).encode()).hexdigest()}, open(f'{STATE}/admin.json', 'w'))

def sign(role, exp):
    msg = f'{role}.{exp}'
    return f"{msg}.{hmac.new(SECRET, msg.encode(), hashlib.sha256).hexdigest()}"

def valid(tok, role):
    try:
        r, exp, _ = tok.split('.')
        return r == role and int(exp) > time.time() and hmac.compare_digest(sign(r, int(exp)), tok)
    except Exception:
        return False

def write_json(path, obj):
    data = json.dumps(obj, ensure_ascii=False)
    with open(path, 'w') as f: f.write(data)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def cookies(self):
        return SimpleCookie(self.headers.get('Cookie', ''))
    def has(self, name, role):
        c = self.cookies()
        return name in c and valid(c[name].value, role)
    def reply(self, code, headers=(), body=b''):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        for k, v in headers: self.send_header(k, v)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def body(self, limit=12 * 1024 * 1024):
        n = int(self.headers.get('Content-Length', 0) or 0)
        if n > limit: raise ValueError('too big')
        return self.rfile.read(n)
    def throttled(self):
        ip = self.headers.get('X-Real-IP', '?'); n, t = fails.get(ip, (0, 0))
        return ip, n, (n >= 10 and time.time() - t < 600)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == '/_auth': return self.reply(204 if self.has('gal', 'view') or self.has('adm', 'admin') else 401)
        if p == '/_authadm': return self.reply(204 if self.has('adm', 'admin') else 401)
        if p == '/api/logout':
            return self.reply(302, [('Set-Cookie', 'gal=; Path=/; Max-Age=0'), ('Location', '/public/login.html')])
        if p == '/api/admin/logout':
            return self.reply(302, [('Set-Cookie', 'adm=; Path=/; Max-Age=0'), ('Location', '/public/admin-login.html')])
        self.reply(404)

    def do_POST(self):
        u = urlparse(self.path); p = u.path
        try:
            if p in ('/api/login', '/api/admin/login'):
                ip, n, blocked = self.throttled()
                if blocked: return self.reply(429)
                pw = str(json.loads(self.body(4096) or b'{}').get('pw', ''))
                admin = p == '/api/admin/login'
                ok = admin_pw_ok(pw) if admin else hmac.compare_digest(pw.encode(), VIEW_PW.encode())
                if not ok:
                    fails[ip] = (n + 1, time.time()); return self.reply(401, body={'ok': False})
                fails.pop(ip, None)
                name, role = ('adm', 'admin') if admin else ('gal', 'view')
                tok = sign(role, int(time.time()) + MAX_AGE)
                return self.reply(200, [('Set-Cookie', f'{name}={tok}; Path=/; Max-Age={MAX_AGE}; HttpOnly; SameSite=Lax')], {'ok': True})

            if not p.startswith('/api/admin/'): return self.reply(404)
            if not self.has('adm', 'admin'): return self.reply(401)

            if p == '/api/admin/upload':
                q = parse_qs(u.query); fid = q.get('id', [''])[0]; kind = q.get('kind', [''])[0]
                if not ID_RE.match(fid) or kind not in ('img', 'thumb'): return self.reply(400)
                data = self.body()
                if not data.startswith(b'\xff\xd8'): return self.reply(400, body={'error': 'not jpeg'})
                with open(f'{WWW}/{kind}/{fid}.jpg', 'wb') as f: f.write(data)
                return self.reply(200, body={'ok': True})

            if p == '/api/admin/save':
                d = json.loads(self.body(2 * 1024 * 1024))
                items = [it for it in d.get('items', []) if ID_RE.match(str(it.get('id', '')))]
                clean = [{'id': it['id'], 'title': str(it.get('title', ''))[:60], 'author': str(it.get('author', ''))[:30],
                          'w': int(it.get('w', 640)), 'h': int(it.get('h', 480))} for it in items]
                write_json(f'{WWW}/data.json', clean)
                if isinstance(d.get('settings'), dict): write_json(f'{WWW}/settings.json', d['settings'])
                keep = {it['id'] for it in clean}
                for kind in ('img', 'thumb'):
                    for fn in os.listdir(f'{WWW}/{kind}'):
                        if fn.endswith('.jpg') and fn[:-4] not in keep: os.remove(f'{WWW}/{kind}/{fn}')
                return self.reply(200, body={'ok': True, 'count': len(clean)})

            if p == '/api/admin/password':
                d = json.loads(self.body(4096))
                if not admin_pw_ok(str(d.get('old', ''))): return self.reply(403, body={'error': '原密码不对'})
                new = str(d.get('new', ''))
                if len(new) < 4: return self.reply(400, body={'error': '新密码至少4位'})
                set_admin_pw(new); return self.reply(200, body={'ok': True})
        except Exception as e:
            return self.reply(400, body={'error': str(e)[:100]})
        self.reply(404)

ThreadingHTTPServer(('127.0.0.1', 8081), H).serve_forever()
