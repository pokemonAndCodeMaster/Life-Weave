GSSM v5 与官方代码核验记录（2026-09-19）

基准：arXiv 2505.13556v5，2026-03-22；代码 main / 0ee2542eb28e50948cae8561332365d5f76e29d4（2026-03-09）。文件均在 code/ 中保持作者路径。下述为静态源码核验及少量合成输入检验，非论文结果复现。

| 对象 | v5/文本证据 | 当前源码证据 | 判断 |
| --- | --- | --- | --- |
| 条件分布 | §2.4，式3：s 条件对数正态，参数依赖 X | src_posterior_inference/model.py:107–155；inference_utils/utils_data.py:77–122 | 观测间距是目标；网络输入不含 s，输出 μ、log variance。 |
| 核心评分 | 式1、4：log10[ln(.5)/ln(1−F)] | src_safety_evaluation/validation_utils/utils_evaluation.py:78–91 | 函数主体相符，但 s 和 survival 做 1e−6 截断，n 下限1，因此 M 下限0、上限约5.84，非论文所写全部实数及正无穷。 |
| 空间坐标 | 式2显示矩阵与位移向量相加 | src_data_preparation/represent_utils/coortrans.py:32–33,90–92 | 实现为旋转矩阵乘位移向量，符合尺寸与坐标变换；报告采用实现对应的数学表达。 |
| s 的几何意义 | §2.3 使用径向位置距离 | represent_utils/utils_data_segmentation.py:149–150 | 中心/位置参考点的欧氏距离，无车身边界扣减；尺寸另作输入。有限车身接触不要求 s=0。 |
| 极值解释 | §2.2 写 q^n>.5 推得 n>ln(.5)/ln q | 数学直接计算 | 因 ln q<0，正确为 n<临界值；等式定义式1本身有效。n 是连续临界尺度，不是对实际帧的独立采样计数保证。 |
| 式5 NLL | 负对数乘积等同平均，左侧漏1/N | model.py:116–122 | 逐样本 lognormal NLL 与代码一致，代码取mean。 |
| 式6平滑 | 宣称严格 Jensen–Shannon divergence | model.py:138–144 | 用均值参数/平均方差构造单个正态，再平均两个 KL；真正 JS 中间分布应为两个密度的混合。反例 N(−2,1),N(2,1)：代码代理值2，大于严格JS上界 ln2。 |
| 扰动尺度 | 表A.2 变量 range 的1% | utils_train_eval_test.py:83–87 | 实际按训练特征标准差1%，不是极差。 |
| 编码器层数 | A.3 当前5层、环境4层 Linear | inference_utils/modules.py:39,75,42–56,78–90 | 分别传入10和6，实际10/6个Linear；历史单层LSTM、6 attention blocks、2 Conv1d、双3层输出头与描述主要结构相符。 |
| 式15纠错 | v3：∫_R^1 TPR dFPR /(1−R)；v5：∫_R^1(1−FPR(r))dr/(1−R) | validation_utils/utils_eval_metrics.py:29–53 | 代码对FPR网格积分(TPR−R)_+/(1−R)，完整单调ROC下与v5几何等价；1000点插值、阈值端点外推会有数值口径差异。 |
| 式16 | 召回≥R的最大precision | utils_eval_metrics.py:74–88 | 相符，未达指定召回返回None。 |
| AUPRC | PR面积 | utils_eval_metrics.py:56–71 | 按1000网格插值后梯形积分；不等于所有软件的average_precision定义。 |
| 检测单位 | §5.3.1 危险事件TP至少预警0.5秒 | utils_evaluation.py:432–438 | conflict.sum()>5，10Hz数据至少6个点；不要求连续。FP则安全对象时段任意1点报警即计。 |
| TTI | 式14 最后一次safe→unsafe至impact | utils_evaluation.py:440–461 | 最后一次转变的定义相符；报警时间在TP判定外单独赋值，FN也可能有非空warning_timestamp。 |
| TTI聚合 | §5.3.2 仅正确检测事件 | utils_eval_metrics.py:123–149 | get_time不显式筛true_warning；调用处未见相关过滤，因此是否混入FN须用实际输出审计，不能声称作者时间结果已重现。 |
| 置信区间 | 正文、图表宣称99% sign-test CI | utils_eval_metrics.py:91–120；utils_tabfig.py:781–782,968–969 | 底层默认alpha=.01，但调用包装函数默认alpha=.05并传给底层，图表调用未覆盖，当前路径计算95%口径。 |
| 切分 | §5.1约80/20 | segment_datasets.py:33–40 | 先event_id切分再分段；highD按ego轨迹id，Argoverse按log_id，SafeBaseline按event_id。没证明同驾驶员/地点/同时交通参与者完全隔离。 |
| 事件投票 | §5.2 票数>1/3，反对<1/3 | vote_conflicting_target.py:79–88 | 赞成实际上>=1/3，反对严格<1/3；弃权另计。阈值边界差异。 |
| 重建式11 | 加性状态更新末两项仍写ψ,v | reconstruction_utils/utils_ekf.py:184–189 | 实现保持速度与航向（后者wrap），不会把二者每步加倍。 |

注意：这里识别“文稿—代码”差异，不据此推断差异改变了已发表表值。没有原始输出和生成日志，不能断言期刊数值使用了哪一历史代码路径。当前主分支不是一个明确命名为 v5 的实验冻结标签。已查询标签 12Nov2025，指向 4c5d7082732cc43715f0f2aeaab2d3690ca4729f；论文也提供 Zenodo 永久代码入口。

源码核验入口：[冻结提交](https://github.com/Yiru-Jiao/GSSM/tree/0ee2542eb28e50948cae8561332365d5f76e29d4)、[v5全文](https://arxiv.org/html/2505.13556v5)、[v3式15](https://arxiv.org/html/2505.13556v3#S5.E15)。

样本数交叉核对：表7五类事件数为1787、611、93、29、31，总和2551而非2591。PDF第26页图A.2显示 Other lateral=193，其中 Turning&Crossing=116，与表7的93不同；饼图另列Parked=11、Oncoming=4、Unknown=2等。仅用“有些类别省略”不能完整解释40的差额，其中交叉/转弯的23例差异仍需事件清单核验。本轮不从图表自行修改作者的表值。

实际运行的最小官方函数检查：partial_auc在合成ROC上输出0.5749987992567012，v5手算0.575；rotate_coor对轴(3,4)、位移(6,8)输出(约0,10)；get_time对含一个TP（TTI=2）和一个FN（TTI=8）的合成输入返回5，而只统计TP应为2。依赖numpy2.2.6、pandas2.3.3、scipy1.15.3，运行CPU，不载入模型。详情在 checks/official_function_checks.py 与 checks/official-function-results.json。日志中的平滑散度反例是将源代码代数表达式代入计算，未安装PyTorch或运行该模型类。
