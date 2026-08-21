# -*- coding: utf-8 -*-
from pathlib import Path
import numpy as np

# LoRa参数
FS = 250e3
SF = 7
BW = 125e3
AMP = 0.2

BASE_DIR = Path(__file__).resolve().parent
WAVEFORM_DIR = BASE_DIR / "waveforms"
WAVEFORM_DIR.mkdir(parents=True, exist_ok=True)

M = 2 ** SF
Ts = M / BW
Ns = int(round(FS * Ts))
BIN_HZ = BW / M
SAMPLES_PER_BIN = Ns // M

if Ns % M != 0:
    raise RuntimeError("Ns must be integer multiple of M.")

print("===== LoRa Pilot + Payload TX =====")
print("FS =", FS)
print("SF =", SF)
print("BW =", BW)
print("M =", M)
print("Ts =", Ts)
print("Ns =", Ns)
print("BIN_HZ =", BIN_HZ)
print("SAMPLES_PER_BIN =", SAMPLES_PER_BIN)

#  Lora符号结构
PILOT_PERIOD = 8 
PILOT_REPEAT = 2
PILOT_SYMBOL = 20

symbols = []

# 避开 DC，pilot dechirp 后理论频点约 20 * 976.5625 = 19.53 kHz
PILOT_SYMBOL = 20

# 生成时间
DURATION_SEC = 90.0

# 随机符号
PAYLOAD_MIN_SYMBOL = 0
PAYLOAD_MAX_SYMBOL = 127

RNG_SEED = 2026
rng = np.random.default_rng(RNG_SEED)

print("\n===== Frame Structure =====")
print("PILOT_PERIOD =", PILOT_PERIOD)
print("PILOT_SYMBOL =", PILOT_SYMBOL)
print("Pilot theoretical freq =", PILOT_SYMBOL * BIN_HZ / 1e3, "kHz")
print("Payload symbol range =", PAYLOAD_MIN_SYMBOL, "~", PAYLOAD_MAX_SYMBOL)

#生成upchirp
t = np.arange(Ns) / FS
k = BW / Ts

phase = 2 * np.pi * (
    -BW / 2 * t
    + 0.5 * k * t ** 2
)

upchirp = np.exp(1j * phase).astype(np.complex64)

def make_lora_symbol(sym):
    """
    upchirp的循环平移。
    sym=0 是普通 upchirp。
    """
    sym = int(sym) % M
    shift = sym * SAMPLES_PER_BIN

    # -shift: dechirp 后对应正频率 bin
    y = np.roll(upchirp, -shift)

    return y.astype(np.complex64)


def phase_connect(waves):
    """
    减少相邻 symbol 拼接相位突变。
    """
    out = []
    prev_last = None

    for y in waves:
        y = y.copy()

        if prev_last is not None:
            rot = prev_last / (y[0] + 1e-30)
            rot = rot / (np.abs(rot) + 1e-30)
            y = y * rot

        prev_last = y[-1]
        out.append(y.astype(np.complex64))

    return out

# 生成连续 pilot + random payload符号

NUM_GROUPS = 6000

symbols = []

for _ in range(NUM_GROUPS):
    for _ in range(PILOT_REPEAT):
        symbols.append(PILOT_SYMBOL)

    for _ in range(PILOT_PERIOD - PILOT_REPEAT):
        s = int(rng.integers(PAYLOAD_MIN_SYMBOL, PAYLOAD_MAX_SYMBOL + 1))
        symbols.append(s)

symbols = np.array(symbols, dtype=np.int32)

print("\n===== Generated Symbols =====")
print("Total symbols =", len(symbols))
print("Total duration =", len(symbols) * Ns / FS, "s")
print("First 32 symbols =", symbols[:32].tolist())

# 生成 TX 和 REF
tx_waves = []
ref_waves = []

for s in symbols:
    # TX是pilot/payload LoRa symbol
    tx_waves.append(make_lora_symbol(s))

    # REF是upchirp，用于dechirp
    ref_waves.append(make_lora_symbol(0))

tx_waves = phase_connect(tx_waves)
ref_waves = phase_connect(ref_waves)

tx = AMP * np.concatenate(tx_waves).astype(np.complex64)
ref = AMP * np.concatenate(ref_waves).astype(np.complex64)

#保存
tx_file = WAVEFORM_DIR / "lora_pilot_payload_tx_sf7_bw125k_fs250k.cf32"
ref_file = WAVEFORM_DIR / "lora_pilot_payload_ref_sf7_bw125k_fs250k.cf32"
sym_file = WAVEFORM_DIR / "lora_pilot_payload_symbols.txt"

tx.tofile(tx_file)
ref.tofile(ref_file)

with open(sym_file, "w") as f:
    f.write(",".join(str(int(s)) for s in symbols))

print("\n===== Saved =====")
print("TX file  =", tx_file)
print("REF file =", ref_file)
print("SYM file =", sym_file)
print("TX samples =", len(tx))
print("Duration =", len(tx) / FS, "s")
print("Max abs TX =", np.max(np.abs(tx)))