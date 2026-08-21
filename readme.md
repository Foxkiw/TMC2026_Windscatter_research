# WindScatter与拓展
本仓库包含《TMC2026 WindScatter 调研报告》对应的实验代码、GNU Radio Flowgraph 与LTspice仿真文件。

项目以WindScatter 原文复现为起点，进一步探索如何将其“传感量直接控制 Backscatter”的思想拓展到连续的模拟量的感知，并针对实验中振荡器功耗较高的问题，进一步尝试负阻LC自激振荡方案。倘若可拓展为连续的模拟信息感知，应用场景将得到广泛拓展，不仅是报告中呈现的呼吸监测任务。

文件结构为
```text
WindScatter-Reproduction/
├── README.md
├── requirements.txt
├── .gitignore
│
├── windscatter/
│   ├── README.md
│   ├── capture.grc
│   ├── dechirp.py
│   ├── data/
│   └── hardware/
│
├── breathing_backscatter/
│   ├── README.md
│   ├── pilot_tx.py
│   ├── lora_test.grc
│   ├── embedded_fm_extractor.py
│   ├── show.py
│   ├── waveforms/
|   └── hardware/
│
├── circuit/
│   ├── README.md
│   └── tdo_sensor_oscillator.asc
│
└── docs/
    └── 报告.pdf
```

三个子目录分别对应项目中的三个阶段。

## 1、WindScatter 复现

windscatter/ 对应WindScatter基本原理的复现实验。

实验使用Backscatter标签对LoRa激励信号进行调制，USRP B200接收原始IQ数据后，通过：

Dechirp → FFT → OOK 检测 → 上升沿提取 → 标签振荡频率估计

## 2、Backscatter对连续模拟信息传感

breathing_backscatter/ 对 WindScatter 的思想进行了进一步拓展。

实验利用柔性电极感知人体呼吸引起的电容变化，并通过RC振荡器将
呼吸信息映射为Backscatter 频移变化，最终由 USRP 实时恢复为连续频率漂移波形。

## 3、Backscatter对连续模拟信息传感

circuit/对连续模拟量标签的进一步低功耗实现进行了探索。

借鉴了TMC2025年工作Twaltz，针对RC充放电振荡器的动态功耗问题，使用LTspice建立简化负阻模型，将传感电容直接作为LC谐振网络的一部分，使 感知电容变化映射为谐振频率变化

仿真文件为circuit/tdo_sensor_oscillator.asc，主要用于验证机制可行性，并未采用真实 TDO 的完整器件模型，因此仿真得到的功耗不能直接作为实际硬件功耗预测。