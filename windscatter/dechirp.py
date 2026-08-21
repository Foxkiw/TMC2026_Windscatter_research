import numpy as np
import matplotlib.pyplot as plt
from collections import deque
import time

# ===== 参数 =====
fs = 1_000_000
bw = 125_000
sf = 7
file_path = 'data/first.cfile'
threshold = 10          
display_seconds = 2.0   # 每次显示2秒
update_seconds = 0.2    # 每0.2秒刷新一次
hop_ratio = 8

# ===== LoRa参数 =====
Tsym = (2**sf) / bw
Ns = int(round(Tsym * fs))
hop = Ns // hop_ratio

print("Ns =", Ns)
print("hop =", hop)
print("time resolution =", hop / fs, "s")

# ===== downchirp =====
t = np.arange(Ns) / fs
k = bw / Tsym
phase_up = 2 * np.pi * ((-bw / 2) * t + 0.5 * k * t**2)
downchirp = np.exp(-1j * phase_up)

# ===== 读取文件 =====
data = np.fromfile(file_path, dtype=np.complex64)
data = data - np.mean(data)

block_len = int(update_seconds * fs)
display_len = int(display_seconds * fs)

buf = deque(maxlen=display_len)

def remove_short_runs(x, min_len=5):
    y = x.copy()
    n = len(y)
    i = 0
    while i < n:
        j = i
        while j < n and y[j] == y[i]:
            j += 1
        if j - i < min_len:
            y[i:j] = 1 - y[i]
        i = j
    return y

def process_iq(iq):
    iq = np.asarray(iq, dtype=np.complex64)
    iq = iq - np.mean(iq)

    times = []
    ratios = []

    for start in range(0, len(iq) - Ns, hop):
        seg = iq[start:start + Ns]
        dechirped = seg * downchirp
        X = np.fft.fft(dechirped)
        mag = np.abs(X)

        peak = np.max(mag)
        avg = np.mean(mag)
        ratio = peak / (avg + 1e-12)

        times.append(start / fs)
        ratios.append(ratio)

    times = np.array(times)
    ratios = np.array(ratios)

    ook = (ratios > threshold).astype(int)
    ook = remove_short_runs(ook, min_len=5)

    rising = np.where((ook[1:] == 1) & (ook[:-1] == 0))[0] + 1
    edge_times = times[rising]

    freq = None
    if len(edge_times) >= 2:
        intervals = np.diff(edge_times)

        # 简单去异常
        med = np.median(intervals)
        valid = (intervals > 0.5 * med) & (intervals < 1.5 * med)
        intervals = intervals[valid]

        if len(intervals) > 0:
            freq = 1.0 / np.mean(intervals)

    return times, ratios, ook, freq

# ===== 实时绘图 =====
plt.ion()
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

line_ratio, = ax1.plot([], [])
line_th, = ax1.plot([], [], '--')
ax1.set_ylabel("Peak / AVG")
ax1.grid(True)

line_ook, = ax2.step([], [], where='post')
ax2.set_ylabel("OOK")
ax2.set_xlabel("Time in buffer (s)")
ax2.set_ylim(-0.2, 1.2)
ax2.grid(True)

idx = 0

while idx + block_len <= len(data):
    block = data[idx:idx + block_len]
    idx += block_len

    buf.extend(block)

    if len(buf) < Ns * 3:
        continue

    iq = np.array(buf)
    times, ratios, ook, freq = process_iq(iq)

    line_ratio.set_data(times, ratios)
    line_th.set_data(times, np.ones_like(times) * threshold)

    ax2.clear()
    ax2.step(times, ook, where='post')
    ax2.set_ylabel("OOK")
    ax2.set_xlabel("Time in buffer (s)")
    ax2.set_ylim(-0.2, 1.2)
    ax2.grid(True)

    ax1.set_xlim(0, display_seconds)
    ax1.set_ylim(0, max(20, np.max(ratios) * 1.2))

    if freq is not None:
        fig.suptitle(f"Real-time OOK detection | estimated frequency = {freq:.2f} Hz")
    else:
        fig.suptitle("Real-time OOK detection | frequency = N/A")

    fig.canvas.draw()
    fig.canvas.flush_events()

    time.sleep(0.05)

plt.ioff()
plt.show()