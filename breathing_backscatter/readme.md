# Backscatter呼吸检测实验

本目录包含报告中使用Backscatter进行模拟信息传感的实验实现。

该实验是在WindScatter思路基础上的进一步探索：不再仅利用传感器产生数字开关事件，而是尝试将在背散射标签上，将**传感电容连续变化转化为Lora信号频移**，并在接收端通过算法恢复呼吸波形。

## 1. 目录结构

```text
breathing_backscatter/
├── README.md
├── pilot_tx.py
├── lora_test.grc
├── embedded_fm_extractor.py
├── show.py
└── waveforms/
    ├── lora_pilot_payload_tx_sf7_bw125k_fs250k.cf32
    ├── lora_pilot_payload_ref_sf7_bw125k_fs250k.cf32
    └── lora_pilot_payload_symbols.txt
├──hardware/
      ├── AD文件.zip
      ├── Gerber文件.zip
      └── 原理图PDF.pdf
```

各文件作用如下：

* `pilot_tx.py`：生成实验使用的LoRa pilot + payload基带波形；
* `lora_test.grc`：GNU Radio收发与dechirp Flowgraph；
* `embedded_fm_extractor.py`：GNU Radio Embedded Python Block的代码副本，便于阅读；
* `show.py`：通过ZeroMQ接收处理结果并实时显示频移；
* `waveforms/`：由 `pilot_tx.py` 生成的波形文件；
* `hardware/`：标签PCB原理图PDF与制版文件。

## 2. 标签端原理

使用柔性导电布作为传感电极，将两个电极贴附于胸腹部衣物。

人体呼吸会导致衣物形变、电极间距离和人体耦合路径变化，从而产生连续的等效电容变化。

```text
呼吸
 ↓
电极电容变化
 ↓
RC 振荡频率变化
 ↓
Backscatter 调制频率变化
 ↓
接收端计算频移
```

## 3. 软件环境
使用VMWare虚拟机，Ubuntu22.04上的
```text
Python 3
GNU Radio 3.10
```
Python库依赖
```bash
pip install numpy pyzmq PyQt5 pyqtgraph
```
## 4. LoRa 参数

实验使用：
```text
采样率：       250 kS/s
扩频因子：     SF = 7
LoRa 带宽：    BW = 125 kHz
符号周期：     1.024 ms
```

`pilot_tx.py` 中相应设置为：

```python
FS = 250e3
SF = 7
BW = 125e3
AMP = 0.2
```
每 8 个 LoRa symbol 中插入两个固定 pilot，其余 symbol 使用随机 payload。
固定 pilot 的作用是给接收端提供稳定的参考频率。

## 5. 生成发送波形

首先运行pilot_tx.py

程序将在：
```text
waveforms/
```
目录中产生：
```text
lora_pilot_payload_tx_sf7_bw125k_fs250k.cf32
lora_pilot_payload_ref_sf7_bw125k_fs250k.cf32
lora_pilot_payload_symbols.txt
```
其中：
```text
lora_pilot_payload_tx_sf7_bw125k_fs250k.cf32
```
包含实际发送的：pilot + random payload LoRa symbol序列。


```text
lora_pilot_payload_ref_sf7_bw125k_fs250k.cf32
```
始终由普通 upchirp 构成，用于接收端 dechirp。

```text
lora_pilot_payload_symbols.txt
```
记录实际生成的 symbol 序列，便于调试检查。

## 6. GNU Radio实验
首先需要根据原理图PDF与制板文件制作标签端PCB，并根据报告描述选择合适电阻、芯片等器件，制作柔性电极并贴附于衣物，从而完成标签制作

GNU Radio中打开lora_test.grc

实验 Flowgraph 的主要参数为：
```text
samp_rate      = 250e3

TX center      = 433 MHz
TX gain        = 80

RX center      = 441.55 MHz
RX gain        = 30
RX antenna     = RX2
```

实际实验中，SDR 发射中心为 `433 MHz`，接收中心约为 `441.55 MHz`。复现时接收中心频率需要根据实际背散射频移后的频率更改。

TX File Source 循环发送：
```text
waveforms/lora_pilot_payload_tx_sf7_bw125k_fs250k.cf32
```

同时使用：
```text
waveforms/lora_pilot_payload_ref_sf7_bw125k_fs250k.cf32
```
作为本地参考chirp，USRP 接收数据与参考 chirp 进行dechrip：

Embedded Python Block 的输入为 dechirp 后的 `complex64` 数据。

其处理流程为：

```text
每个 LoRa symbol
        ↓
      FFT
        ↓
查找峰值频率
        ↓
统计不同 symbol slot 的稳定性
        ↓
自动识别固定 pilot slot
        ↓
估计中心频率
        ↓
去除固定频移与频偏
        ↓
输出频移信息
```

Block 会对每个symbol做FFT，并利用峰值相对于噪声底的质量进行判断。
完成同步后，只在识别出的pilot时隙输出结果，payload被忽略。

发送端每8个symbol中设置了两个连续 pilot，当前接收算法从中选择一个稳定slot 作为感知窗口，因此最终等效的采样率约为：

```text
250000 / 256 / 8
≈ 122.07 samples/s
```
## 8. 实时显示
GNU Radio 中 Embedded Python Block 的输出通过：

```text
tcp://127.0.0.1:5555
```
发布。

运行 show.py 通过ZeroMQ SUB接收数据并维护20秒的缓冲区。

正常工作时能够看到连续变化的：
```text
Residual FM Drift
```
即消除固定频移、LoRa symbol 信息及中心频率后的残余频率漂移。
报告中得到的最终呼吸波形由该程序得到。

## 9. 实验局限

当前样机最大的限制是振荡器功耗和寄生电容。

样机总等效电容约 `350 pF`，而实际传感电极本身只有pF级变化，因此寄生参数显著降低了传感灵敏度。

同时RC充放电振荡器使整机功耗达到约 `3 mW`。

这是后续进一步考虑利用TDO负阻LC自激振荡结构、降低传感振荡功耗的主要原因。
