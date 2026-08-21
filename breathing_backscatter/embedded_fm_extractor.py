# -*- coding: utf-8 -*-

import numpy as np
from gnuradio import gr


class blk(gr.basic_block):
    """
    Pilot + random payload FM extractor.

    输入:
        dechirp 后 complex64:
            rx * conj(local_upchirp)

    每 pilot_period 个 LoRa symbol 中，固定 pilot symbol，
    其余是随机 payload symbol。

    本 block:
        1. 每个LoRa symbol窗口FFT找峰值频率
        2. 检测pilot
        3. 在pilot slot输出频点漂移
        4. payload slot直接忽略

    output_mode:
        0: pilot 频点去中心后的漂移
        1: pilot 绝对频率
        2: 所有 symbol 的原始峰值频率，用于调试
        3: 当前 pilot_offset
        4: 峰值dB
    """

    def __init__(
        self,
        fs=250e3,
        sf=7,
        bw=125e3,
        nfft=4096,

        band_min=-125e3,
        band_max=125e3,

        pilot_period=8,

        auto_offset=1,
        auto_offset_symbols=512,

        center_lock_len=32,
        smooth_alpha=0.08,

        output_mode=0,
        output_khz=1,

        quality_threshold_db=6.0,
        hold_bad=1,
        debug_print=0
    ):
        gr.basic_block.__init__(
            self,
            name="lora_pilot_payload_fm_extractor",
            in_sig=[np.complex64],
            out_sig=[np.float32]
        )

        self.fs = float(fs)
        self.sf = int(sf)
        self.bw = float(bw)
        self.nfft = int(nfft)

        self.M = 2 ** self.sf
        self.sym_len = int(round(self.fs * self.M / self.bw))
        self.bin_hz = self.bw / self.M

        self.band_min = float(band_min)
        self.band_max = float(band_max)

        self.pilot_period = int(pilot_period)
        if self.pilot_period <= 0:
            self.pilot_period = 8

        self.auto_offset = bool(auto_offset)
        self.auto_offset_symbols = int(auto_offset_symbols)
        if self.auto_offset_symbols < self.pilot_period * 8:
            self.auto_offset_symbols = self.pilot_period * 8

        self.offset_done = not self.auto_offset
        self.pilot_offset = 0

        self.center_lock_len = int(center_lock_len)
        if self.center_lock_len <= 0:
            self.center_lock_len = 1

        self.smooth_alpha = float(smooth_alpha)
        self.smooth_alpha = min(max(self.smooth_alpha, 0.0), 1.0)

        self.output_mode = int(output_mode)
        self.output_khz = bool(output_khz)

        self.quality_threshold_db = float(quality_threshold_db)
        self.hold_bad = bool(hold_bad)
        self.debug_print = bool(debug_print)

        self.buf = np.zeros(0, dtype=np.complex64)

        self.window = np.hanning(self.sym_len).astype(np.float32)

        self.f_axis = np.fft.fftshift(
            np.fft.fftfreq(self.nfft, d=1.0 / self.fs)
        )
        self.df = self.fs / self.nfft

        self.band_mask = (
            (self.f_axis >= self.band_min) &
            (self.f_axis <= self.band_max)
        )
        self.band_indices = np.where(self.band_mask)[0]

        if len(self.band_indices) < 3:
            raise ValueError("band too narrow.")

        # offset 自动检测缓存
        self.slot_freqs = [[] for _ in range(self.pilot_period)]
        self.slot_qualities = [[] for _ in range(self.pilot_period)]

        self.symbol_count = 0
        self.pilot_count = 0

        self.center_freq = None
        self.center_buf = []

        self.smooth_value = None
        self.last_output = np.float32(0.0)

        self.last_freq = 0.0
        self.last_quality = 0.0

        print("===== lora_pilot_payload_fm_extractor =====")
        print("fs =", self.fs)
        print("sf =", self.sf)
        print("bw =", self.bw)
        print("symbol length =", self.sym_len)
        print("symbol rate =", self.fs / self.sym_len, "Hz")
        print("LoRa bin =", self.bin_hz, "Hz")
        print("pilot_period =", self.pilot_period)
        print("pilot output rate =", self.fs / self.sym_len / self.pilot_period, "Hz")
        print("nfft =", self.nfft)
        print("fft df =", self.df, "Hz")
        print("band =", self.band_min, "~", self.band_max)
        print("auto_offset =", self.auto_offset)
        print("auto_offset_symbols =", self.auto_offset_symbols)

    def forecast(self, noutput_items, ninput_items_required):
        need = min(self.sym_len, 1024)

        try:
            for i in range(len(ninput_items_required)):
                ninput_items_required[i] = need
        except TypeError:
            return [need]

    def estimate_peak(self, seg):
        xw = seg * self.window

        X = np.fft.fftshift(
            np.fft.fft(xw, n=self.nfft)
        )

        p = np.abs(X) ** 2

        p_band = p[self.band_indices]
        noise = float(np.median(p_band)) + 1e-30

        local_idx = int(np.argmax(p_band))
        peak_idx = int(self.band_indices[local_idx])

        peak_power = float(p[peak_idx])
        quality_db = 10.0 * np.log10((peak_power + 1e-30) / noise)

        # 抛物线插值
        delta = 0.0

        if 1 <= peak_idx < self.nfft - 1:
            y0 = np.log(p[peak_idx - 1] + 1e-30)
            y1 = np.log(p[peak_idx] + 1e-30)
            y2 = np.log(p[peak_idx + 1] + 1e-30)

            denom = y0 - 2.0 * y1 + y2

            if abs(denom) > 1e-12:
                delta = 0.5 * (y0 - y2) / denom
                delta = float(np.clip(delta, -0.5, 0.5))

        f_peak = float(self.f_axis[peak_idx] + delta * self.df)

        return f_peak, quality_db

    def try_finish_auto_offset(self):
        if self.offset_done:
            return

        if self.symbol_count < self.auto_offset_symbols:
            return

        best_slot = 0
        best_score = 1e99

        print("===== AUTO OFFSET SCORES =====")

        for slot in range(self.pilot_period):
            arr = np.array(self.slot_freqs[slot], dtype=np.float64)

            if len(arr) < 4:
                continue

            med = np.median(arr)
            mad = np.median(np.abs(arr - med))
            std = np.std(arr)

            # pilot slot 频率最稳定，所以 mad/std 最小
            score = mad + 0.2 * std

            print(
                "slot =", slot,
                "median =", f"{med:.2f}",
                "mad =", f"{mad:.2f}",
                "std =", f"{std:.2f}",
                "score =", f"{score:.2f}"
            )

            if score < best_score:
                best_score = score
                best_slot = slot

        self.pilot_offset = int(best_slot)
        self.offset_done = True

        print("===== AUTO PILOT OFFSET DONE =====")
        print("pilot_offset =", self.pilot_offset)
        print("score =", best_score, "Hz")

    def is_pilot_symbol(self):
        return (self.symbol_count % self.pilot_period) == self.pilot_offset

    def make_drift(self, f_peak):
        if self.center_freq is None:
            self.center_buf.append(float(f_peak))

            if len(self.center_buf) >= self.center_lock_len:
                self.center_freq = float(np.median(np.array(self.center_buf)))

                print("===== CENTER LOCK =====")
                print("center_freq =", self.center_freq, "Hz")

            return 0.0

        drift = f_peak - self.center_freq

        if self.smooth_value is None:
            self.smooth_value = drift
        else:
            a = self.smooth_alpha
            self.smooth_value = (1.0 - a) * self.smooth_value + a * drift

        return float(self.smooth_value)

    def make_output(self, f_peak, q_db):
        drift = self.make_drift(f_peak)

        if self.output_mode == 0:
            value = drift
        elif self.output_mode == 1:
            value = f_peak
        elif self.output_mode == 2:
            value = f_peak
        elif self.output_mode == 3:
            value = float(self.pilot_offset)
        elif self.output_mode == 4:
            value = q_db
        else:
            value = drift

        if self.output_khz and self.output_mode in [0, 1, 2]:
            value = value / 1000.0

        return np.float32(value)

    def general_work(self, input_items, output_items):
        x = input_items[0]
        y = output_items[0]

        if len(x) > 0:
            self.buf = np.concatenate(
                (self.buf, x.astype(np.complex64, copy=False))
            )

        out_count = 0

        while len(self.buf) >= self.sym_len and out_count < len(y):
            seg = self.buf[:self.sym_len]

            f_peak, q_db = self.estimate_peak(seg)

            slot = self.symbol_count % self.pilot_period

            # 自动检测阶段：统计每个 slot 的频率稳定性
            if not self.offset_done:
                self.slot_freqs[slot].append(f_peak)
                self.slot_qualities[slot].append(q_db)

                self.try_finish_auto_offset()

                self.buf = self.buf[self.sym_len:]
                self.symbol_count += 1
                continue

            # 调试模式：输出所有 symbol 的原始频率
            if self.output_mode == 2:
                value = f_peak
                if self.output_khz:
                    value = value / 1000.0

                y[out_count] = np.float32(value)
                self.last_output = np.float32(value)
                out_count += 1

                self.buf = self.buf[self.sym_len:]
                self.symbol_count += 1
                continue

            # 正式模式：只在 pilot slot 输出
            if self.is_pilot_symbol():
                if q_db < self.quality_threshold_db:
                    if self.hold_bad:
                        y[out_count] = self.last_output
                    else:
                        y[out_count] = np.float32(np.nan)

                    out_count += 1

                else:
                    value = self.make_output(f_peak, q_db)

                    y[out_count] = value
                    self.last_output = value
                    out_count += 1

                    self.last_freq = f_peak
                    self.last_quality = q_db
                    self.pilot_count += 1

                    if self.debug_print and self.pilot_count % 50 == 0:
                        print(
                            "[PILOT]",
                            "sym =", self.symbol_count,
                            "slot =", slot,
                            "f =", f"{f_peak:.2f}",
                            "q =", f"{q_db:.2f}",
                            "out =", f"{float(value):.5f}"
                        )

            # payload slot 不输出
            self.buf = self.buf[self.sym_len:]
            self.symbol_count += 1

        self.consume_each(len(x))
        return out_count