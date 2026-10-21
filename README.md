# 中国日历 · China Calendar

把日子，过成好时节。

一个安静的中国日历：正式放假与补班、农历传统节日、二十四节气，以及传统时令。
支持 iPhone、iPad、Mac 和其他兼容 ICS 的日历客户端。

**[打开互动月历 →](https://luke-lab666.github.io/China-Calendar/)** · [选择订阅](https://luke-lab666.github.io/China-Calendar/#subscribe) · [数据来源](#数据来源)

## 网页能做什么

- 在纸感月历中切换月份，查看农历、正式休班标记和日期详情。
- 按精简、全部、休班或节气筛选；交节时刻显示北京时间。
- 选择订阅方案，一键唤起日历客户端，或复制 HTTPS 订阅地址。
- 明确标注尚未收录放假安排的年份，不把周末直接当作确定的休息日。
- 适配桌面与手机，支持键盘方向键选日期、减少动态效果设置；无追踪脚本、无账户系统。

网页读取构建时从仓库导出的真实数据，没有在线天气预报或假期预测。

## 选一份刚刚好的订阅

日常使用推荐**精简版**。如果已经使用苹果官方“中国大陆节假日”日历，可选择**苹果日历补充**。
精简版和完整版二选一；分项内容已包含在完整版中，避免重复订阅。

| 日历 | 内容 | 订阅 |
| --- | --- | --- |
| **精简版** | 放假、补班、传统节日、精确节气 | [essential.ics](https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/essential.ics) |
| 苹果日历补充 | 精确交节、部分传统与纪念日、传统时令 | [supplement.ics](https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/supplement.ics) |
| 完整版 | 全部内容 | [calendar.ics](https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/calendar.ics) |
| 放假与调休 | 仅正式放假、补班 | [holidays.ics](https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/holidays.ics) |
| 二十四节气 | 精确到分钟的交节事件 | [solar-terms.ics](https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/solar-terms.ics) |
| 传统节日 | 按农历标注的节日 | [traditional.ics](https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/traditional.ics) |
| 传统节日与纪念日 | 含常见社会日期 | [observances.ics](https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/observances.ics) |
| 传统时令 | 按规则自动计算的三伏与数九 | [seasonal.ics](https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/seasonal.ics) |

请在日历 App 中选择“添加订阅日历”并粘贴地址，**不要下载后一次性导入**。
表中列出的 raw 订阅地址保持可用，网页也提供相同内容的订阅。
已下线的独立订阅请在日历 App 中手动移除，以清除客户端保留的缓存。

事件标题使用“（休）/（班）”标明正式安排；原生角标由客户端决定，普通 ICS 无法保证显示。
若使用苹果官方日历搭配补充版，官方的全天节气名称与补充版的精确交节事件可能同时出现。
所有订阅不写入 `VALARM`，不会强制弹出提醒；同步频率由客户端决定。

## 数据来源

- **正式假期与补班**：结构化数据来自 [NateScarlet/holiday-cn](https://github.com/NateScarlet/holiday-cn)，仅接受附国务院 `gov.cn` 正式文件的安排。
- **交节时刻与农历**：来自[香港天文台天文资料](https://www.hko.gov.hk/sc/gts/astronomy/Solar_Term.htm)和[公历农历对照表](https://www.hko.gov.hk/sc/gts/time/conversion.htm)，交节按 UTC+8 精确到分钟。
- **三伏与数九**：按“夏至三庚、立秋后一庚”和“冬至起数九”规则计算。

## 更新与发布

每天计划于北京时间 **21:00** 联网检查；GitHub Actions 实际执行可能延迟。

- 获取、解析全部来源成功后才写入源文件；临时请求错误最多重试两次。
- 未公布的未来假期不保留空 JSON 占位文件，不预测日期；空结果也不能覆盖已收录安排。
- 输出范围是上一年到未来两年，最早从 2025 年开始；正在进行的多日假期保留完整日期和 UID。
- 输入未改变时，生成结果保持字节一致；代码、配置和年份范围参与生成状态校验。
- 日历更新成功后，Pages 工作流重新构建网页及订阅。采用 `workflow_run` 接续自动更新，避免机器人提交不触发后续工作流的问题。
- Pages 只发布 `_site/` 构建产物；源码、测试和原始数据目录不会原样发布。

## 本地使用与开发

Python **3.11+**，运行时无第三方依赖；前端为原生 HTML、CSS、JavaScript，无 npm 安装或打包步骤。

```bash
# 联网更新，或使用缓存离线重建
python -m china_calendar.cli
python -m china_calendar.cli --offline

# 只读检查订阅是否与代码、配置和数据一致
python -m china_calendar.cli --check

# 日期与近期查询（只读、离线）
python -m china_calendar.cli --date 2026-02-14
python -m china_calendar.cli --upcoming 14
python -m china_calendar.cli --date 2026-10-08 --feed calendar --json

# 生成到独立目录；保留尚未结束的完整假期
python -m china_calendar.cli --offline --future-holidays-only --output /tmp/china-calendar-future

# 构建和预览网页
python -m china_calendar.site
python -m http.server 8000 --directory _site
```

浏览器打开 `http://localhost:8000`。自定义路径使用 `--root`、`--output`；
`--today YYYY-MM-DD` 可复现指定日期。查询的 `day_type` 包含放假、补班、普通工作日、周末和未知状态。
JSON 事件的结束日期遵循 ICS 的排他上界。

```bash
python -m unittest discover -s tests -v
node --test tests/test_web.mjs
```

CI 验证 Python 3.11 / 3.12 / 3.13，并运行前端日期测试与静态站点构建。

### 目录

| 路径 | 用途 |
| --- | --- |
| `china_calendar/` | 来源校验、事件生成、CLI 与 Pages 导出 |
| `web/` | 唯一一套网页源文件 |
| `config/`、`data/` | 正式来源、农历和节气缓存 |
| `calendars/` | 保持旧订阅地址兼容的 ICS 文件 |
| `tests/` | 日期、来源故障、订阅和站点回归验证 |
| `_site/` | 自动生成、被 Git 忽略的发布目录 |

2024 年冬至数据仍用于计算 2025 年初的“数九”，不是废弃文件。

[MIT License](LICENSE)
