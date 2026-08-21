# WindScatter复现

本目录包含报告中 WindScatter 原文复现实验所使用的采集与处理代码。

整体流程为：

```text
商用LoRa发射机产生Lora信号
        ↓
Backscatter标签反射信号
        ↓
USRP B200接收
        ↓
存储原始复数IQ数据
        ↓
滑动窗口Dechirp
        ↓
FFT峰值检测
        ↓
OOK判决，估计上升沿周期
```

## 1. 文件说明

```text
windscatter/
├── README.md
├── capture.grc
├── dechirp.py
├── data/
|    └── first.cfile
└── hardware/
     ├── Gerber.zip
     ├── backscatter_AD文件.zip
     └── 原理图PDF.pdf
```

其中：

* `capture.grc`：使用USRP B200采集原始IQ数据的GNU Radio Flowgraph；
* `dechirp.py`：B200采集背散射信号的处理脚本；
* `data/first.cfile`：USRP接收到的 `complex64`原始IQ数据。
* `hardware`：原理图与PCB制板文件

## 2. 实验环境

使用VMware虚拟机，Ubuntu22.04，Python 3，依赖numpy matplotlib

### 硬件采集环境

实验使用：
```text
SDR：Ettus USRP B200
GNU Radio：3.10.1.1
商用Lora模块：DX-LR22
```
使用商用 LoRa 模块作为射频激励源，并由 USRP B200 接收 Backscatter 信号。采用滑动窗口 dechirp、FFT 峰值检测以及上升沿周期估计完成标签振荡频率恢复。

## 3. 硬件准备

完成完整硬件实验需要：
* 商用LoRa发射模块；
* Ettus USRP B200；
* Backscatter标签PCB；
* TX/RX天线；
* 电机驱动风扇；
* 径向磁铁

LoRa信号作为Backscatter标签的外部射频激励。标签通过周期性切换RF开关改变负载阻抗，从而对反射信号进行调制。标签的开关频率由传感电路控制，因此可以在接收端通过估计调制频率恢复传感信息。

报告中的功率测量实验中，标签、频谱仪与激励源之间的距离约为2m。

## 4. 信号参数

```text
LoRa 扩频因子：SF = 7
LoRa 带宽：BW = 125 kHz
USRP 采样率：1 MS/s
IQ 数据格式：complex64
采集时间：2s
```
对应 `dechirp.py` 中：
```python
fs = 1_000_000
bw = 125_000
sf = 7
threshold = 10
display_seconds = 2.0
```

其中 `threshold=10` 用于根据 FFT 峰值与平均频谱幅度之比进行 OOK 判决。

## 5. 原始 IQ 数据采集
首先需根据原理图与制板文件，选择对应电子器件完成标签端PCB制作

GNU Radio中打开capture.grc

采集前需要完成以下准备：
1. 连接 USRP B200；
2. 将接收天线连接到 `RX2`；
3. 启动商用LoRa发射模块；
4. Backscatter标签供电；
5. 将 `center_freq` 设置为实际使用的背散射频移后的LoRa信号频率；
6. 启动Flowgraph采集IQ数据。

当前Flowgraph将接收到的 IQ 保存为：
```text
data/first.cfile
```

采集数据类型为 `complex float32`，采样率为 1 MS/s。

 `capture_windscatter.grc` 中的 `center_freq` 应根据实际使用的背散射频移后的LoRa信号频率重新设置。

## 6. 算法复现

获得有效的IQ数据后，在 `windscatter/` 目录下运行：
```bash
python3 dechirp.py
```
程序首先读取：

```text
data/first.cfile
```

数据按 `complex64` 格式解析。

随后按照以下流程处理：

```text
原始 IQ
   ↓
按照一个 LoRa Symbol 长度滑窗
   ↓
Dechirp
   ↓
FFT
   ↓
计算 Peak / Average
   ↓
Threshold 判决高低电平
   ↓
得到OOK 序列
   ↓
提取上升沿
   ↓
计算相邻上升沿周期
   ↓
估计标签振荡频率
```

## 7. 预期结果

程序将绘制Peak / AVG与OOK曲线

当风扇旋转且标签正常工作时，FFT峰均比中应出现周期性高低变化，对应标签RF开关的周期性切换。

程序检测OOK上升沿后，根据相邻上升沿间隔估算标签振荡频率，并显示在图像标题中。

报告中的实验结果表明，风扇转动状态下可以观察到明显的周期性检测结果；风扇停止后，该周期结构消失或发生显著变化。

## 8. 商用LoRa模块的特殊问题

实验过程中发现，商用LoRa数据包之间存在无载波空白期。

在这段时间中，Backscatter标签没有入射信号可供反射，因此检测结果中会出现周期性断点。

这与WindScatter原文中较连续的激励条件不同，因此原文直接针对随机噪声设计的上升沿统计方法不能完全直接迁移到商用LoRa。

因此在分析结果时，需要区分标签 RF 开关造成的OOK变化与LoRa数据包间隔造成的无载波空白

## 9. 当前原始数据说明

本仓库提供：

* WindScatter 处理代码；
* USRP IQ采集Flowgraph；
* 实验参数与复现步骤。

在整理开源仓库时，当前保留下来的 `first.cfile` 经检查没有包含有效 LoRa 信号，需等待硬件条件恢复后，使用 `capture.grc` 重新获得有效信号，报告中的 WindScatter 实验结果来自此前完成的有效硬件采集。

