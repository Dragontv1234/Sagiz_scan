import argparse, requests, urllib.parse, concurrent.futures, subprocess, json, sys
from datetime import datetime

results = []

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

def scan_payload(url, param, payload, mode, proxy):
    target_url = build_url(url, param, payload)
    r = request(target_url, proxy)
    if not r: return
    result = {"mode": mode, "url": target_url, "payload": payload, "vulnerable": False}

    if mode == "sql" and any(e in r.text.lower() for e in ["mysql", "syntax", "odbc", "sql error"]):
        print(f"[SQLi] {target_url}")
        result["vulnerable"] = True
    elif mode == "xss" and payload.strip('<>"') in r.text:
        print(f"[XSS] {target_url}")
        result["vulnerable"] = True

    if result["vulnerable"]:
        results.append(result)

def csrf_check(url, proxy):
    r = request(url, proxy)
    if r and "<form" in r.text and "csrf" not in r.text.lower():
        print(f"[CSRF] No CSRF token found: {url}")
        results.append({"mode": "csrf", "url": url, "vulnerable": True})

def nuclei_scan(url):
    try:
        print(f"[NUCLEI] Scanning {url}...")
        subprocess.run(["nuclei", "-u", url], check=True)
    except Exception as e:
        print(f"[!] Nuclei error: {e}")

def run_mode(mode, url, payloads, threads, proxy, fuzz_all):
    params = parse_params(url)
    targets = params if fuzz_all else ["vuln"]

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

def save_results(path):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        print(f"[+] Results saved to: {path}")
    except Exception as e:
        print(f"[!] Failed to save results: {e}")

def main():
    parser = argparse.ArgumentParser(description="  VulnScanner Framework")
    parser.add_argument("-u", "--url", required=True, help="Target URL")
    parser.add_argument("-m", "--mode", required=True, help="sql, xss, csrf, nuclei, fullscan")
    parser.add_argument("-payload", help="Payload file path")
    parser.add_argument("-thread", type=int, default=5, help="Thread count")
    parser.add_argument("-proxy", help="Proxy (http://127.0.0.1:8080)")
    parser.add_argument("--fuzz-params", action="store_true", help="Fuzz all parameters")
    parser.add_argument("--output", help="Save results to JSON file")

    args = parser.parse_args()
    run_scan(args)
    if args.output:
        save_results(args.output)

if __name__ == "__main__":
    main()
