# -*- coding: utf-8 -*-
"""netkeiba からの取得。速さを抑え、途中で止まっても続きから再開できる。"""
import time, threading, random
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")


class Fetcher:
    """1秒あたりの件数を守りながら取ってくる。429/400 が出たら自動で減速して待つ。"""

    def __init__(self, cookie, rate=2.0, timeout=20):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA,
                               "Accept-Language": "ja,en;q=0.8"})
        if cookie:
            self.s.cookies.set("netkeiba", cookie, domain=".netkeiba.com")
        self.min_gap = 1.0 / float(rate)
        self.timeout = timeout
        self._last = 0.0
        self._lock = threading.Lock()
        self.blocked_until = 0.0

    def _wait(self):
        with self._lock:
            now = time.time()
            if now < self.blocked_until:
                time.sleep(self.blocked_until - now)
                now = time.time()
            gap = self.min_gap - (now - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.time()

    def get(self, url, encoding="euc-jp", tries=3):
        """本文を文字列で返す。取れなければ None。"""
        for a in range(tries):
            self._wait()
            try:
                r = self.s.get(url, timeout=self.timeout)
            except Exception:
                time.sleep(2 + 3 * a)
                continue
            if r.status_code == 200:
                b = r.content
                for enc in ([encoding, "utf-8"] if encoding != "utf-8"
                            else ["utf-8", "euc-jp"]):
                    try:
                        t = b.decode(enc)
                    except Exception:
                        continue
                    if "�" not in t[:4000]:
                        return t
                return b.decode(encoding, "replace")
            if r.status_code in (400, 403, 429, 503):
                # 止められた合図。間を大きく空け、以後の速さも落とす。
                wait = 60 * (a + 1) + random.uniform(0, 20)
                self.blocked_until = time.time() + wait
                self.min_gap = min(self.min_gap * 1.6, 5.0)
                time.sleep(1)
                continue
            return None
        return None

    def slow_down(self, factor=2.0):
        self.min_gap = min(self.min_gap * factor, 8.0)
