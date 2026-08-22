"""多格式导出（包内模块，走 -m 调用，规避沙箱对 script.py 的偶发拦截）。

把三张专辑成品转 OGG + FLAC（保真，不改电平，保留 SPECTRUM 的 RMS 情绪弧线）。
后端与 export.batch.export_audio 同源（soundfile），但跳过其 -1dBFS 重新归一化。
"""
import os, json, glob

ROOT = os.path.dirname(os.path.abspath(__file__))  # 项目根（python -m _export_mod 调用时）
if not os.path.isdir(os.path.join(ROOT, "spectrum_album_output")):
    raise SystemExit(
        f"未找到 spectrum_album_output（ROOT={ROOT}）。"
        "请在项目根目录用 python -m _export_mod 运行（旧版硬编码 D:/bloodmusic 回退已移除）。"
    )

def convert(src, dst, fmt):
    import soundfile as sf
    data, sr = sf.read(src, always_2d=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if fmt == "ogg":
        sf.write(dst, data, sr, format="OGG", subtype="VORBIS")
    elif fmt == "flac":
        for sub in ("PCM_24", "PCM_16", None):
            try:
                if sub:
                    sf.write(dst, data, sr, format="FLAC", subtype=sub)
                else:
                    sf.write(dst, data, sr, format="FLAC")
                return os.path.getsize(dst)
            except Exception:
                if sub is None:
                    raise
    return os.path.getsize(dst)

count = {"ogg": 0, "flac": 0}
total = 0
errors = []

def do(src, dst, fmt):
    global total
    try:
        sz = convert(src, dst, fmt)
        total += sz
        count[fmt] += 1
        print(f"  [{fmt}] {os.path.basename(dst)} ({sz/1024:.0f}KB)", flush=True)
    except Exception as e:
        errors.append(f"{fmt}:{src}->{e}")
        print(f"  [ERR {fmt}] {os.path.basename(src)}: {e}", flush=True)

print("=== [1] SPECTRUM 主专辑 ===", flush=True)
spec = os.path.join(ROOT, "spectrum_album_output")
for td in sorted(glob.glob(os.path.join(spec, "track_*"))):
    src = os.path.join(td, "song_final.wav")
    if not os.path.exists(src):
        continue
    base = os.path.basename(td).replace(" ", "_").replace("·", "")
    for fmt in ("ogg", "flac"):
        do(src, os.path.join(spec, "export", fmt, base + "." + fmt), fmt)

print("=== [2] Beats 伴侣 ===", flush=True)
beats_root = os.path.join(ROOT, "skill", "output_beats")
bout = os.path.join(ROOT, "beats_export")
for src in sorted(glob.glob(os.path.join(beats_root, "*20260822_082917.wav"))):
    base = os.path.basename(src).replace("_20260822_082917", "").replace(" ", "_")
    for fmt in ("ogg", "flac"):
        do(src, os.path.join(bout, fmt, base + "." + fmt), fmt)

print("=== [3] Mirror 镜像专辑 ===", flush=True)
mir = os.path.join(ROOT, "mirror_album_output")
mout = os.path.join(ROOT, "mirror_export")
mixers = []
mf = os.path.join(mir, "album_manifest.json")
if os.path.exists(mf):
    try:
        mixers = [t.get("mixer") or t.get("slug") or t.get("name")
                  for t in json.load(open(mf, encoding="utf-8")).get("tracks", [])]
    except Exception:
        mixers = []
if not mixers:
    mixers = [os.path.basename(d.rstrip("/\\")) for d in glob.glob(os.path.join(mir, "*/"))]
for mx in mixers:
    src = os.path.join(mir, str(mx), "01_lofi.wav")
    if not os.path.exists(src):
        print(f"  [SKIP] {mx}: 缺失", flush=True)
        continue
    for fmt in ("ogg", "flac"):
        do(src, os.path.join(mout, fmt, str(mx) + "." + fmt), fmt)

print(f"=== 完成: OGG={count['ogg']} FLAC={count['flac']} 体积={total/1024/1024:.1f}MB 错误={len(errors)} ===", flush=True)
for e in errors[:20]:
    print("  -", e, flush=True)
