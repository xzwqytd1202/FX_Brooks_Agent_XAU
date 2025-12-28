# FX Brooks Agent XAU

基于 **Al Brooks Price Action** 理念的黄金智能交易系统。

## 项目结构

```
FX_Brooks_Agent_XAU/
├── app/                    # Python 后端
│   ├── config.py          # 配置参数
│   ├── schemas.py         # 数据模型
│   ├── main.py            # FastAPI 主程序
│   └── services/          # L0-L5 决策层
│       ├── global_risk.py # L0: 全局风控
│       ├── l1_perception.py # L1: K线感知
│       ├── l2_structure.py  # L2: 结构计数
│       ├── l3_context.py    # L3: 环境判断
│       ├── l4_probability.py # L4: 概率计算
│       └── l5_execution.py   # L5: 交易执行
├── mql5/                  # MT5 终端
│   └── N99_AB_Gold_Agent.mq5
├── docker-compose.yml     # 容器编排
├── Dockerfile             # 镜像构建
└── requirements.txt       # Python 依赖

```

## 快速启动

### 1. 部署 Python 后端

```bash
cd FX_Brooks_Agent_XAU
docker-compose up -d
```

服务将运行在 **端口 8002**。

### 2. 配置 MT5

1. 将 `mql5/N99_AB_Gold_Agent.mq5` 复制到 MT5 的 `Experts` 文件夹
2. 编译并加载到 XAUUSD 图表
3. 确保在 `工具 -> 选项 -> 专家顾问` 中允许 WebRequest 到 `http://127.0.0.1:8002`

## 核心特性

- **L0 风控层**: 账户熔断、保证金检查、硬时间过滤
- **L1 感知层**: 识别 K 线的 Control、Momentum、Rejection
- **L2 结构层**: Leg Counting，识别 H1/H2/L1/L2 Setup
- **L3 环境层**: 判断市场循环（趋势/震荡/突破）
- **L4 概率层**: 综合胜率计算
- **L5 执行层**: 风险回报比判断，生成订单

## 参数配置

关键参数在 `app/config.py` 中：

- `AB_AVG_BODY_SIZE`: 黄金 M5 平均实体大小（默认 $2）
- `AB_STRONG_BAR_RATIO`: 强趋势 K 线倍数（默认 1.5x）
- `MIN_PROB`: 开仓最低胜率（默认 65%）
