import os
import sys, os, threading, http.server, socketserver, re, json, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "research"))
import shutil, subprocess, tempfile
if not shutil.which("ffmpeg"):
    print("SKIP store_bench tests: ffmpeg not installed"); raise SystemExit(0)
WWW = os.path.join(tempfile.mkdtemp(), "www"); os.makedirs(WWW)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-filter_complex",
                "testsrc=d=2:s=320x180:r=25[a];smptebars=d=1.5:s=320x180:r=25[b];rgbtestsrc=d=4.5:s=320x180:r=25[c];color=c=white:d=4:s=320x180:r=25[d];[a][b][c][d]concat=n=4:v=1:a=0[v]",
                "-map", "[v]", "-pix_fmt", "yuv420p", os.path.join(WWW, "moov_end.mp4")], check=True)           # moov box at the end
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(WWW, "moov_end.mp4"), "-c", "copy", "-movflags", "+faststart",
                os.path.join(WWW, "moov_front.mp4")], check=True)                                              # moov box first
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=WWW, **k)
    def log_message(self, *a): pass
    def do_GET(self):
        rng = self.headers.get("Range"); path = self.translate_path(self.path)
        if not rng: return super().do_GET()
        m = re.match(r"bytes=(\d+)-(\d+)?", rng); size = os.path.getsize(path); s = int(m.group(1)); e = min(int(m.group(2) or size - 1), size - 1)
        data = open(path, "rb").read()[s:e + 1]
        self.send_response(206); self.send_header("Content-Range", f"bytes {s}-{e}/{size}"); self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Type", "video/mp4"); self.end_headers(); self.wfile.write(data)
class NoRange(H):
    def do_GET(self): return http.server.SimpleHTTPRequestHandler.do_GET(self)
def serve(handler):
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv, srv.server_address[1]
import common; common.set_rate(0)
import store_bench as sb
srv, port = serve(H)
for f in ("moov_end.mp4", "moov_front.mp4"):
    d = sb.mp4_duration(f"http://127.0.0.1:{port}/{f}"); assert d and abs(d - 12.0) < 0.15, (f, d); print("mp4_duration", f, d)
srv2, port2 = serve(NoRange)
assert sb.mp4_duration(f"http://127.0.0.1:{port2}/moov_end.mp4") is None; print("server without Range support -> None (no wrong guess)")
src = os.path.join(WWW, "moov_end.mp4"); cuts = sb.scene_cuts(src)
print("cuts", cuts); assert cuts and any(abs(c - 2.0) < .2 for c in cuts) and any(abs(c - 3.5) < .2 for c in cuts) and any(abs(c - 8.0) < .2 for c in cuts)
p = sb.pacing(cuts); print("pacing", p); assert abs(p["time_to_first_cut_s"] - 2.0) < .2 and p["cuts_first_5s"] == 2
fr = sb.save_frames(src, os.path.join(WWW, "frames"), 7, times=(0, 5, 11)); assert len(fr) == 3 and all(os.path.getsize(x) > 500 for x in fr); print("frames", [os.path.basename(x) for x in fr])
o = dict(appid=1, _movie=f"http://127.0.0.1:{port}/moov_front.mp4"); sb.trailer_features(o, None); print("trailer_features", {k: o[k] for k in ("trailer_s", "time_to_first_cut_s", "cuts_first_5s", "ffmpeg")})
h = '<h2 class="bb_tag">A</h2><p>Hello <b>world</b> &amp; co</p><img class="bb_img" src="https://x/a.gif?t=1"><img src="b.png"><video src="c.webm"></video><ul class="bb_ul"><li>x</li><li>y</li></ul>'
a = sb.analyze_html(h); assert (a["gifs"], a["images"], a["looping_videos"], a["headings"], a["bullets"]) == (1, 2, 1, 1, 2), a; assert sb.strip_tags(h).startswith("A Hello world & co"); print("analyze_html", a)
assert str(sb.parse_release("Jul 21, 2022")) == "2022-07-21" and str(sb.parse_release("21 Jul, 2022")) == "2022-07-21" and sb.parse_release("Coming soon") is None
assert sb.spearman([1, 2, 3, 4, 5], [10, 20, 30, 40, 50]) == 1.0 and sb.spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == -1.0 and sb.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None
assert sb.ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]
rows = [dict(name=f"G{i}", reviews_per_year=100 * 2 ** i, pct_positive=80 + (i % 5), short_desc_chars=100 + 10 * i, gifs=i % 3, trailer_s=60 + i, reviews_total=500 * i + 100) for i in range(12)]
res = sb.analyze(rows); f = {x["feature"]: x for x in res["features"]}
assert f["short_desc_chars"]["rho_reviews_per_year"] == 1.0 and f["short_desc_chars"]["median_top"] > f["short_desc_chars"]["median_rest"] and res["top_group"]["size"] == 4
assert "gifs" in f and "time_to_first_cut_s" not in f
txt = sb.md(res, rows, "2026-10-06"); assert "forte" in txt and "Spearman" in txt; print("analyze ok: short_desc rho", f["short_desc_chars"]["rho_reviews_per_year"], f["short_desc_chars"]["strength_reviews"])
# ---- Steam no longer serves MP4 trailers: adaptive streams only (HLS .m3u8 / DASH .mpd)
os.makedirs(os.path.join(WWW, "hls")); os.makedirs(os.path.join(WWW, "dash"))
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(WWW, "moov_end.mp4"), "-c", "copy", "-f", "hls", "-hls_time", "3", "-hls_playlist_type", "vod", os.path.join(WWW, "hls", "index.m3u8")], check=True)
shutil.copy(os.path.join(WWW, "hls", "index.m3u8"), os.path.join(WWW, "hls", "index_hi.m3u8"))
open(os.path.join(WWW, "hls", "master.m3u8"), "w").write("#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=900000,RESOLUTION=640x360\nindex_hi.m3u8\n#EXT-X-STREAM-INF:BANDWIDTH=200000,RESOLUTION=320x180\nindex.m3u8\n")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(WWW, "moov_end.mp4"), "-c", "copy", "-f", "dash", "-seg_duration", "3", os.path.join(WWW, "dash", "manifest.mpd")], check=True)
B = f"http://127.0.0.1:{port}"
assert abs(sb.hls_duration(f"{B}/hls/master.m3u8?t=1") - 12.0) < 0.3, "master playlist must be followed to a media playlist"
assert abs(sb.hls_duration(f"{B}/hls/index.m3u8") - 12.0) < 0.3 and abs(sb.mpd_duration(f"{B}/dash/manifest.mpd") - 12.0) < 0.3
steam_movie = {"id": 1, "name": "Trailer", "highlight": True, "hls_h264": f"{B}/hls/master.m3u8?t=1", "dash_h264": f"{B}/dash/manifest.mpd?t=1", "dash_av1": f"{B}/dash/manifest.mpd", "thumbnail": f"{B}/t.jpg"}
srcs = sb.movie_sources(steam_movie); assert [k for k, _ in srcs] == ["hls", "dash", "dash"], srcs
o = dict(appid=9, _movies=srcs); sb.trailer_features(o, os.path.join(WWW, "hooks"))
assert o["trailer_kind"] == "hls" and abs(o["trailer_s"] - 12.0) < 0.3 and o["trailer_formats"] == ["hls", "dash", "dash"], o
assert abs(o["time_to_first_cut_s"] - 2.0) < 0.3 and o["cuts_first_5s"] == 2 and len(o["hook_frames"]) == 6, o
o = dict(appid=10, _movies=[("dash", f"{B}/dash/manifest.mpd")]); sb.trailer_features(o, None); assert o["trailer_kind"] == "dash" and abs(o["trailer_s"] - 12.0) < 0.3
o = dict(appid=11, _movies=sb.movie_sources({"id": 2, "thumbnail": f"{B}/t.jpg"})); sb.trailer_features(o, None); assert o["trailer_s"] is None and o["trailer_kind"] is None and o["trailer_formats"] == []
assert sb.parse_iso_duration("PT1M32.5S") == 92.5 and sb.parse_iso_duration("PT90S") == 90.0 and sb.parse_iso_duration("nonsense") is None
print("HLS and DASH trailers ok: duration", o and "12 s", "| first cut", 2.0, "| formats ranked mp4 > hls > dash > webm")
print("ALL STORE_BENCH TESTS PASSED")
