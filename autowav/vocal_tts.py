# -*- coding: utf-8 -*-
"""
vocal_tts.py —— 人声档 B：语音念白（有词、无旋律）
====================================================

依据 VOICE_SYNTH_RESEARCH_2026.md 的「档 B」调研：
  - 1a SAPI（本文件首选）：Windows System.Speech，系统自带、离线、零 pip 依赖；
    经 PowerShell 子进程渲染 WAV（SetOutputToWaveFile 落盘，不捕获管道输出，
    适配受限沙箱），再用标准库 wave 读回。
  - 1b Piper：可选后端，需要 piper 可执行文件 + .onnx 模型（~60MB）；
    缺失时抛出带安装指引的 RuntimeError，绝不污染核心引擎（懒加载原则）。

用法:
    python -m bloodmusic.autowav.vocal_tts "你好，血音" --out n.wav
    python -m bloodmusic.autowav.vocal_tts --list-voices
    from bloodmusic.autowav.vocal_tts import speak
    audio = speak("欢迎来到 BloodMusic", backend="sapi", rate=1)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

_SR = 22050

# Windows 常见中文语音（按优先级尝试；不在列表则用系统默认语音）
_CN_VOICES = (
    "Microsoft Huihui Desktop",
    "Microsoft Kangkang Desktop",
    "Microsoft Yaoyao Desktop",
    "Microsoft Hanhan Desktop",
    "Microsoft Tracy Desktop",
)


def _powershell_quote(s: str) -> str:
    """把文本安全地放进 PowerShell 单引号字符串。"""
    return "'" + s.replace("'", "''").replace("\r", " ").replace("\n", " ") + "'"


def list_sapi_voices() -> list[str]:
    """列出系统已安装的 SAPI 语音（PowerShell System.Speech）。"""
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name };"
        "$s.Dispose()"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # 无法通过管道取回 stdout 的环境里，改为用临时文件中转
    out_txt = tempfile.mktemp(suffix=".txt")
    ps2 = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name } | Out-File -FilePath "
        + _powershell_quote(out_txt) + " -Encoding UTF8;"
        "$s.Dispose()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps2],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        names = Path(out_txt).read_text(encoding="utf-8-sig").splitlines()
    except Exception:
        names = []
    return [n.strip() for n in names if n.strip()]


def sapi_speak(
    text: str,
    out_path: str | None = None,
    rate: int = 0,
    volume: int = 100,
    voice: str | None = None,
) -> np.ndarray:
    """用 Windows SAPI 把文本念白渲染为 16-bit 单声道 WAV。

    Args:
        text: 念白文本（中文/英文均可，取决于所选语音）。
        out_path: 输出 WAV 路径；None 时仅返回音频数组。
        rate: 语速 -10..10（0=正常）。
        volume: 音量 0..100。
        voice: 语音名；None 时按 _CN_VOICES 自动挑选（无中文语音则用默认）。

    Returns:
        np.float64 单声道音频数组（22050Hz）。

    Raises:
        RuntimeError: SAPI 不可用（非 Windows 或 PowerShell 执行失败）。
    """
    if shutil.which("powershell") is None and sys.platform != "win32":
        raise RuntimeError("SAPI 后端仅支持 Windows（本机未找到 powershell）")

    out = Path(out_path) if out_path else Path(tempfile.mktemp(suffix=".wav"))
    out = out.resolve()

    voices = list_sapi_voices()
    pick = voice or next((v for v in _CN_VOICES if v in voices), None)
    select_cmd = ""
    if pick:
        select_cmd = "$s.SelectVoice(" + _powershell_quote(pick) + ");"

    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        + select_cmd +
        "$s.Rate = " + str(int(rate)) + ";"
        "$s.Volume = " + str(int(volume)) + ";"
        "$s.SetOutputToWaveFile(" + _powershell_quote(str(out)) + ");"
        "$s.Speak(" + _powershell_quote(text) + ");"
        "$s.Dispose()"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(
            "SAPI 念白渲染失败（PowerShell/System.Speech 不可用或语音缺失）"
        )

    audio = _load_wav_mono(out)
    if out_path is None:
        out.unlink(missing_ok=True)
    return audio


def piper_speak(
    text: str,
    model: str | None = None,
    out_path: str | None = None,
) -> np.ndarray:
    """用 Piper TTS 念白（可选后端，需要 piper 可执行文件 + .onnx 模型）。

    Args:
        text: 念白文本。
        model: .onnx 模型路径；None 时用环境变量 PIPER_MODEL。
        out_path: 输出 WAV 路径。

    Returns:
        np.float64 单声道音频数组。

    Raises:
        RuntimeError: piper 缺失或模型缺失（含安装指引，调用方可降级到 SAPI）。
    """
    exe = shutil.which("piper") or shutil.which("piper.exe")
    if exe is None:
        raise RuntimeError(
            "未找到 piper 可执行文件。安装（可选后端，1b 档）：\n"
            "  1) pip install piper-tts（或从官网下载 piper.exe）\n"
            "  2) 下载中文模型 zh_CN-huayan-medium.onnx（~60MB）\n"
            "  3) 设置环境变量 PIPER_MODEL 指向模型文件后重试"
        )
    model_path = model or __import__("os").environ.get("PIPER_MODEL", "")
    if not model_path or not Path(model_path).is_file():
        raise RuntimeError(f"Piper 模型缺失: {model_path or '(未设置 PIPER_MODEL)'}")

    out = Path(out_path) if out_path else Path(tempfile.mktemp(suffix=".wav"))
    txt = Path(tempfile.mktemp(suffix=".txt"))
    txt.write_text(text, encoding="utf-8")
    proc = subprocess.run(
        [exe, "--model", model_path, "--input_file", str(txt), "--output_file", str(out)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    txt.unlink(missing_ok=True)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError("Piper 渲染失败（请检查模型与 piper 版本）")
    audio = _load_wav_mono(out)
    if out_path is None:
        out.unlink(missing_ok=True)
    return audio


def speak(
    text: str,
    backend: str = "sapi",
    out_path: str | None = None,
    rate: int = 0,
    volume: int = 100,
    voice: str | None = None,
    piper_model: str | None = None,
) -> np.ndarray:
    """统一念白入口：backend=sapi（默认，零依赖）| piper（可选）。

    piper 不可用时自动降级到 sapi；sapi 也失败才抛错。
    """
    if backend == "piper":
        try:
            return piper_speak(text, model=piper_model, out_path=out_path)
        except RuntimeError as exc:
            print(f"[vocal_tts] piper 不可用，降级到 sapi：{exc}", file=sys.stderr)
    return sapi_speak(text, out_path=out_path, rate=rate, volume=volume, voice=voice)


def _load_wav_mono(path: Path) -> np.ndarray:
    """读取 16-bit WAV → float64 单声道，重采样到 _SR。"""
    with wave.open(str(path), "rb") as wf:
        n = wf.getnframes()
        ch = wf.getnchannels()
        sr = wf.getframerate() or _SR
        data = wf.readframes(n)
    import struct
    n_samples = n * ch
    fmt = "<" + "h" * n_samples
    samples = np.array(struct.unpack(fmt, data), dtype=np.float64) / 32768.0
    if ch > 1:
        samples = samples.reshape(-1, ch).mean(axis=1)
    if sr != _SR:
        xs = np.linspace(0.0, len(samples) - 1, int(len(samples) * _SR / sr))
        samples = np.interp(xs, np.arange(len(samples)), samples)
    return samples


def _main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="bloodmusic-autowav-tts",
        description="人声档 B：语音念白（SAPI 零依赖 / Piper 可选）",
    )
    p.add_argument("text", nargs="?", help="念白文本")
    p.add_argument("--out", help="输出 WAV 路径")
    p.add_argument("--backend", choices=("sapi", "piper"), default="sapi")
    p.add_argument("--rate", type=int, default=0, help="语速 -10..10（SAPI）")
    p.add_argument("--volume", type=int, default=100, help="音量 0..100（SAPI）")
    p.add_argument("--voice", help="语音名（SAPI，默认自动选中文语音）")
    p.add_argument("--piper-model", help="Piper .onnx 模型路径")
    p.add_argument("--list-voices", action="store_true", help="列出可用 SAPI 语音")
    args = p.parse_args(argv)

    if args.list_voices:
        voices = list_sapi_voices()
        print(f"可用 SAPI 语音（{len(voices)}）:")
        for v in voices:
            print("  -", v)
        return 0
    if not args.text:
        p.error("请提供念白文本（或使用 --list-voices）")

    audio = speak(
        args.text,
        backend=args.backend,
        out_path=args.out,
        rate=args.rate,
        volume=args.volume,
        voice=args.voice,
        piper_model=args.piper_model,
    )
    if args.out:
        print(f"已写入: {args.out}（{len(audio) / _SR:.1f}s, {_SR}Hz）")
    else:
        print(f"念白渲染完成: {len(audio) / _SR:.1f}s（未落盘）")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
