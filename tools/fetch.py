"""tools/sources/ 底下各主題的來源腳本共用（目前是 ai-agents.py）：抓網頁、轉純文字、逐篇跑並記 status。

- 抓一次就存進 tools/.cache/<主題>/<ID>.txt，已存在的跳過。
- 429 就整批停下（exit 2），晚點再跑；403／CAPTCHA 標記 blocked，之後全部跑時跳過（指定 ID 才重抓）。都不重試、不繞過。
"""
import json, re, ssl, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser

UA = "tech-notes-prep/0.1 (personal study notes; kylelin2000 on GitHub)"
SPACING = 1.0  # 秒；各來源腳本依來源調整

# 仍驗證憑證鏈；只關掉 Python 3.13+ 的 X509 strict（部分 .gov.tw 憑證缺 SKI 會被擋）
SSL = ssl.create_default_context()
SSL.verify_flags &= ~ssl.VERIFY_X509_STRICT
# 只給憑證鏈不完整的公開政府頁（標 insecure）；只讀公開內容，不送任何資料
NOVERIFY = ssl._create_unverified_context()

# 只認挑戰頁的標記；正常頁面可能內嵌 reCAPTCHA 表單或在內文提到 captcha，單獨這個字只在很短的頁面才算
CHALLENGE = re.compile(rb"cf-challenge|are you a robot|<title>\s*just a moment", re.I)


class RateLimited(Exception):
    pass


class Blocked(Exception):
    pass


def get(url, insecure=False):
    """回傳 (轉址後的網址, 內容)。"""
    time.sleep(SPACING)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60, context=NOVERIFY if insecure else SSL) as r:
            final, html, body = r.geturl(), r.headers.get_content_type() == "text/html", r.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimited(url)
        if e.code == 403:
            raise Blocked(f"403 {url}")
        raise
    if html and (CHALLENGE.search(body[:20000]) or (len(body) < 10000 and re.search(rb"captcha", body, re.I))):
        raise Blocked(f"captcha {url}")
    return final, body


class Text(HTMLParser):
    skip = {"script", "style", "nav", "header", "footer", "noscript", "svg"}

    def __init__(self, base=None):
        super().__init__()
        self.out, self.depth, self.base = [], 0, base

    def handle_starttag(self, tag, a):
        if tag in self.skip:
            self.depth += 1
        elif tag in ("p", "li", "h1", "h2", "h3", "h4", "tr", "br", "div", "pre"):
            self.out.append("\n")
        if tag == "a" and self.base and not self.depth:  # 保留連結，方便追到 PDF 或新網址
            href = urllib.parse.urljoin(self.base, dict(a).get("href") or "")
            if href.startswith("http") and href.split("#")[0] != self.base:
                self.out.append(f" <{href}> ")

    def handle_endtag(self, tag):
        if tag in self.skip and self.depth:
            self.depth -= 1

    def handle_data(self, d):
        if not self.depth:
            self.out.append(d)


def html_text(raw, base=None):
    """給 base 就把連結（相對路徑轉成絕對網址）一起留下。"""
    p = Text(base)
    p.feed(raw.decode("utf-8", "replace"))
    return re.sub(r"\n\s*\n+", "\n\n", "".join(p.out)).strip()


assert html_text(b'<a href="/download/1/">PDF</a><a href="#top">t</a>', "https://x.org/a/") == "<https://x.org/download/1/> PDFt"


def pdf_text(raw):
    """-layout 保留版面；\\f 分頁，可標頁碼。轉檔失敗或抽不到字就丟例外，不把空檔寫進快取。"""
    r = subprocess.run(["pdftotext", "-layout", "-", "-"], input=raw, capture_output=True)
    text = r.stdout.decode("utf-8", "replace")
    if r.returncode or not text.strip():
        raise RuntimeError(f"pdftotext：{r.stderr.decode('utf-8', 'replace').strip() or '抽不到文字'}")
    return text


def main(sources, run, cache):
    """run(sid, spec) 抓好就寫 cache/<sid>.txt，回傳要記進 status.json 的字串。"""
    unknown = [s for s in sys.argv[1:] if s not in sources]
    if unknown:
        sys.exit(f"不認得的 ID：{' '.join(unknown)}（見 SOURCES）")
    cache.mkdir(parents=True, exist_ok=True)
    sf = cache / "status.json"
    status = json.loads(sf.read_text(encoding="utf-8")) if sf.exists() else {}
    ids = sys.argv[1:] or [s for s in sources if not status.get(s, "").startswith("blocked")]
    for sid in ids:
        if (cache / f"{sid}.txt").exists():
            continue
        try:
            status[sid] = run(sid, sources[sid])
        except RateLimited as e:
            print(f"429 {e}：整批停下，晚點再跑。", file=sys.stderr)
            sys.exit(2)
        except Blocked as e:  # 登入牆／CAPTCHA：標記後跳過，不繞過
            status[sid] = f"blocked: {e}"
        except Exception as e:  # 單篇失敗不影響其他篇
            status[sid] = f"error: {e}"
        sf.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")  # 每篇存一次，中斷也不會丟
        print(sid, status[sid], flush=True)
