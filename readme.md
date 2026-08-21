# WindScatter与拓展
本仓库包含《TMC2026 WindScatter 调研报告》对应的实验代码、GNU Radio Flowgraph 与LTspice仿真文件。

项目以WindScatter 原文复现为起点，进一步探索如何将其“传感量直接控制 Backscatter”的思想拓展到连续的模拟量的感知，并针对实验中振荡器功耗较高的问题，进一步尝试负阻LC自激振荡方案。

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

