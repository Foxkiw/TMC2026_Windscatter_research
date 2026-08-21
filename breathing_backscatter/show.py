# -*- coding: utf-8 -*-

import sys
import time
import zmq
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph as pg

# 参数

ZMQ_ADDR = "tcp://127.0.0.1:5555"

FS_PLOT = 250000 / 256 /8

DISPLAY_SECONDS = 20

# 如果 block output_mode=0 且 output_khz=1，则单位是 kHz
Y_MIN = -20
Y_MAX = 20

SCALE = 1
UPDATE_MS = 30

# ZMQ
ctx = zmq.Context()
sock = ctx.socket(zmq.SUB)
sock.connect(ZMQ_ADDR)
sock.setsockopt(zmq.SUBSCRIBE, b"")
sock.setsockopt(zmq.RCVTIMEO, 1)

# Ring buffer

n_buf = int(DISPLAY_SECONDS * FS_PLOT)
data_buf = np.full(n_buf, np.nan, dtype=np.float32)
time_buf = np.linspace(-DISPLAY_SECONDS, 0, n_buf)

# Qt / pyqtgraph

app = QtWidgets.QApplication(sys.argv)

win = pg.GraphicsLayoutWidget(title="Real-time LoRa Symbol-Removed FM Waveform")
win.resize(1000, 500)

plot = win.addPlot(title="Residual FM Drift after LoRa Symbol Removal")
plot.setLabel("bottom", "Time", units="s")
plot.setLabel("left", "Frequency Drift", units="kHz")
plot.setYRange(Y_MIN, Y_MAX)
plot.showGrid(x=True, y=True)

curve = plot.plot(time_buf, data_buf, pen=pg.mkPen(width=2))

text = pg.TextItem("", anchor=(0, 1))
plot.addItem(text)
text.setPos(-DISPLAY_SECONDS, Y_MAX)

win.show()

# 更新函数
last_update = time.time()
recv_count = 0

def update():
    global data_buf, recv_count, last_update

    got = []

    while True:
        try:
            msg = sock.recv(flags=zmq.NOBLOCK)
            vals = np.frombuffer(msg, dtype=np.float32)

            if vals.size > 0:
                got.append(vals)

        except zmq.Again:
            break

    if len(got) > 0:
        vals = np.concatenate(got)

        vals = vals / SCALE

        m = len(vals)

        if m >= n_buf:
            data_buf[:] = vals[-n_buf:]
        else:
            data_buf = np.roll(data_buf, -m)
            data_buf[-m:] = vals

        recv_count += m

    curve.setData(time_buf, data_buf)

    latest = data_buf[-1]

    if np.isfinite(latest):
        text.setText(f"latest = {latest:.4f} kHz | received = {recv_count}")
    else:
        text.setText(f"waiting... | received = {recv_count}")


timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(UPDATE_MS)

sys.exit(app.exec_())