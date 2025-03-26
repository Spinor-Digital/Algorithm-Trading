# ETH日交易算法 (ETH Day Trading Algorithm)

基于"裸K实战买入形态"的ETH和ETH期权日内交易系统，采用1小时K线判断趋势方向，15分钟K线寻找入场点，实现高杠杆期权交易策略。

## 项目简介

本项目是一套完整的ETH(以太坊)日内交易算法系统，具有以下特点：

- 基于"裸K实战买入形态"的交易策略
- 通过1小时K线判断市场趋势，15分钟K线寻找精确入场点
- 识别关键支撑位和阻力位
- 检测经典K线形态(吞没形态、锤子线、启明星等)
- 自动计算止损止盈位置
- 支持100倍杠杆的ETH期权交易
- 回测功能，评估策略历史表现
- 美观直观的Streamlit用户界面

## 核心功能

1. **市场分析**
   - 趋势识别: 判断当前市场是上升趋势、下降趋势或横盘整理
   - 支撑/阻力位识别: 自动计算关键价格水平
   - K线形态识别: 检测重要的蜡烛图形态

2. **交易信号生成**
   - 多因素评分系统
   - 自动计算入场点、止损位和止盈位
   - 风险管理和头寸规模计算

3. **期权合约选择**
   - 自动选择最佳的期权合约(基于Delta、到期时间等)
   - 利用期权实现高杠杆交易

4. **回测系统**
   - 在历史数据上评估策略表现
   - 计算关键绩效指标(回报率、夏普比率、最大回撤等)
   - 可视化回测结果

## 技术架构

- **数据获取**: 通过Binance和Deribit API获取价格和期权数据
- **市场分析**: 实现各种技术分析指标和形态识别算法
- **交易策略**: 裸K交易系统规则实现
- **回测引擎**: 在历史数据上模拟交易
- **用户界面**: 使用Streamlit构建交互式界面

## 安装步骤

### 环境要求

- Python 3.9.16 (推荐)
- pip (Python包管理器)
- 交易所API密钥 (Binance, Deribit)

### 快速安装（推荐）

使用提供的自动化安装脚本：

```bash
./setup_venv.sh
```

这个脚本会：
1. 检查并使用pyenv安装Python 3.9.16（如果已安装pyenv）
2. 创建虚拟环境
3. 安装所有依赖

### 手动安装

1. 克隆本仓库到本地:

```bash
git clone <仓库URL>
cd eth_daytrader
```

2. 创建并激活虚拟环境:

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

3. 安装必要的依赖包:

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

4. 创建环境变量文件 `.env`，设置API密钥:

```
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_API_SECRET=your_binance_api_secret_here
DERIBIT_API_KEY=your_deribit_api_key_here
DERIBIT_API_SECRET=your_deribit_api_secret_here
USE_TESTNET=True
DEBUG=True
LOG_LEVEL=INFO
```

5. 运行初始化脚本, 创建必要的目录结构:

```bash
python setup.py
```

## 使用指南

### 启动应用

```bash
source venv/bin/activate  # 激活虚拟环境
streamlit run streamlit_app.py
```

启动后，应用将在浏览器中打开 http://localhost:8501

### 可能的问题及解决方案

如果遇到Python版本不兼容的问题：

1. 检查Python版本
   ```
   python --version
   ```

2. 如果不是Python 3.9.x，建议使用pyenv安装：
   ```
   # Mac
   brew install pyenv
   pyenv install 3.9.16
   
   # 设置本地版本
   pyenv local 3.9.16
   ```

3. 如果遇到distutils相关错误，请确保setuptools已正确安装：
   ```
   pip install --upgrade setuptools wheel
   ```

### 主要功能页面

1. **市场分析**
   - 查看当前ETH市场趋势和K线形态
   - 实时更新的K线图，带有支撑位/阻力位标记
   - 详细的市场状态信息

2. **交易信号**
   - 查看当前交易信号和推荐操作
   - 管理当前持仓
   - 查看历史交易记录

3. **回测结果**
   - 运行策略回测
   - 查看策略在历史数据上的表现
   - 分析关键绩效指标

### 参数设置

在侧边栏可以调整各种参数:

- **API设置**: 交易所API密钥配置
- **交易参数**: 调整仓位大小、杠杆倍数、最大持仓时间等
- **分析参数**: 调整技术指标参数和信号阈值
- **回测参数**: 设置回测时间范围和初始资金

## 风险警告

⚠️ **特别注意**:
- 本交易系统使用高杠杆期权合约，风险极高
- 强烈建议在测试网络环境或小资金下测试
- 过去的回测结果不能保证未来表现
- 使用者需承担所有交易风险

## 贡献与开发

欢迎贡献代码或提出建议。开发新功能或修改请遵循以下步骤:

1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 许可证

本项目基于MIT许可证开源 - 详见 LICENSE 文件

## 联系方式

如有问题或建议，请通过GitHub issues联系我们。

## 致谢

- 感谢所有开源库的贡献者
- 特别感谢Binance和Deribit提供的API服务