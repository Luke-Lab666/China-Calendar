# China Calendar

无需安装 App 的中国日历订阅，也可在终端查询农历、补班与近期节气。
Python 3.11+，运行时无第三方依赖。

面向 iPhone、iPad 和 Mac 的中国大陆日历订阅，合并展示：

- 国务院正式发布的法定节假日与调休补班；
- 中国官方纪念日、传统节日和常见社会日期；
- 二十四节气的准确交节时刻，按北京时间精确到分钟；
- 三伏、数九和上海正式公布的入梅、出梅日期；
- 结合二十四节气的季节天气健康提醒。

## 选择订阅

**日常使用推荐精简版**：只保留正式放假、调休补班、传统节日和精确交节时刻，
不加入社会纪念日或健康提醒。

```text
https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/essential.ics
```

如果想看全部内容，使用完整日历：

```text
https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/calendar.ics
```

也可以按内容分别订阅：

| 日历 | 订阅地址 |
| --- | --- |
| 精简版（推荐） | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/essential.ics` |
| 法定节假日与调休 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/holidays.ics` |
| 二十四节气 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/solar-terms.ics` |
| 传统节日与纪念日 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/observances.ics` |
| 传统时令与季节健康提醒 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/seasonal.ics` |
| 苹果官方日历补充包 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/supplement.ics` |
| 仅传统节日 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/traditional.ics` |
| 仅季节健康提醒 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/health.ics` |

精简版与完整版二选一。分项订阅已包含在完整版中，重复订阅会产生重复事件。
已有的六个订阅地址继续可用；新订阅按需添加。

iOS 添加方式：复制订阅地址，打开“设置” → “App” → “日历” → “日历账户” →
“添加账户” → “其他” → “添加已订阅的日历”，粘贴地址并保存。

日历文件提供橙色作为建议颜色。若 iOS 没有自动采用，可在“日历”App 底部点“日历”，
再点该订阅右侧的 `ⓘ`，手动选择橙色。

> 这是“订阅日历”，不要下载后再导入。订阅后，仓库更新会由系统定期同步；具体拉取频率由 iOS 控制。

## 原生“休 / 班”角标方案

iOS 只在苹果官方“节假日日历”上显示日期右上角的原生“休 / 班”角标；普通 ICS
订阅即使包含相同的 Apple 私有字段，系统也不会显示角标。要获得原生角标并保留本项目的
精确交节时间，请组合使用两个日历：

1. 打开“日历”App → 底部“日历” → “添加日历” → “添加节假日日历”；
2. 搜索并添加“中国大陆节假日”，颜色选择橙色；
3. 再选择“添加订阅日历”，订阅以下补充包并同样选择橙色：

```text
https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/supplement.ics
```

补充包不包含法定放假和调休，也过滤了苹果已经提供的主要纪念日及传统节日；二十四节气
以“寒露 · 14:29交节”的形式保留准确的北京时间，同时加入三伏、数九、上海梅雨和季节
健康提醒。苹果官方日历仍会显示一个全天节气名称，这是系统日历不可关闭的部分。

完成后请取消勾选或删除原来的完整 `calendar.ics` 订阅，否则法定节假日会重复显示。

## 更新策略

- GitHub Actions 计划每天北京时间 **21:00** 检查并生成日历；实际执行可能延迟。
- 数据从 **2025 年**开始，不生成更早年份。
- 调休安排只在国务院正式通知发布后加入；公告为空的未来年份保持为空，绝不预测。
- 上海入梅、出梅只收录上海气象部门已经正式公布的年份，不使用常年平均日期预测。
- 输出严格限制在上一年到未来两年（最早 2025 年）；旧数据仍保存在仓库，方便复核。
- 请求暂时失败时最多重试两次；全部来源获取并校验成功后才写入源数据，失败不会发布半套订阅。
- 已发布的未来假期不会因为源站临时返回 404 或空结果而被清空，此时更新会报错。
- 代码、配置、源数据或年份范围改变时更新生成时间；输入未变时重复生成保持字节一致。
- 健康提示以独立的全天事件显示，每年约 25 至 27 条；不写入 `VALARM`，不会强制弹出通知。

## 数据来源与准确性

### 节假日及调休

结构化数据取自 [NateScarlet/holiday-cn](https://github.com/NateScarlet/holiday-cn)，该项目每天抓取国务院公告。
本仓库会再次校验：只接受带 `https://www.gov.cn/` 正式文件链接的数据；有日期却没有国务院文件的年份会直接拒绝生成。

### 二十四节气与农历

中国科学院紫金山天文台说明，二十四节气是太阳在黄道上每运行 15° 的交节瞬间；紫台也是我国专门研究历书天文并编算年历的机构。
紫台暂未提供稳定的公开机器接口，因此本项目没有冒充“紫台 API”：

- 节气定义采用紫金山天文台历书口径；
- 精确时刻来自[香港天文台官方天文资料](https://www.hko.gov.hk/sc/gts/astronomy/Solar_Term.htm)，
  时间为 UTC+8、精确到分钟；
- 农历日期来自[香港天文台公历与农历对照表](https://www.hko.gov.hk/sc/gts/time/conversion.htm)。

香港天文台注明其二十四节气数据根据英国皇家航海历书局及美国海军天文气象台的天文数据计算。
如紫金山天文台未来开放稳定的结构化数据接口，应优先切换并保留交叉校验。

### 传统时令与季节健康提醒

- 三伏按“夏至三庚、立秋后一庚”的干支纪日规则生成，列出初伏、中伏、末伏和出伏；
- 数九从冬至当天起，每九天为一“九”，列出一九至九九和出九；
- 上海入梅、出梅采用上海市气象部门正式公布日期，目前收录 2025、2026 年；
- 每个二十四节气对应一条季节天气健康提醒，入伏和已公布的上海梅雨节点会增加专项提醒。

健康内容参考中国疾控中心气候变化与健康资料及上海市健康促进中心梅雨防护提示，仅提供
一般性天气健康信息，不替代医疗建议。节气不等于当天一定出现对应天气，实际安排应以当地
天气预报、气象预警和自身情况为准。

## iOS 显示方式

- `春节（休）`：整段假期为连续的多日全天事件，标题标明“休”；
- `春节（班）`：国务院安排的补班日，标题标明“班”；原生角标请使用上面的苹果官方日历方案；
- `立春`：事件开始时间就是准确的北京时间交节瞬间，精确到分钟；
- `传统 · 元宵节`：按农历计算的传统节日；
- `时令 · 初伏`：标记三伏各阶段的起始日，说明中列出本阶段日期范围；
- `时令 · 上海入梅`：仅在上海正式公布后加入；
- `健康提醒 · 小暑·防范中暑`：独立全天提示，不附带强制通知；
- `纪念 · 国家公祭日`：官方纪念日或常见社会日期。

## 本地生成

仅需 Python 3.11+，没有第三方运行时依赖：

```bash
python -m china_calendar.cli
python -m unittest discover -s tests -v
```

使用仓库已有数据离线重建：

```bash
python -m china_calendar.cli --offline
```

检查已生成订阅是否与当前代码、配置和数据一致（离线、只读，过期时返回非零退出码）：

```bash
python -m china_calendar.cli --check
```

查询某一天或从今天起的近期安排，默认仅显示精简版事件，查询不会联网或改写订阅：

```bash
python -m china_calendar.cli --date 2026-02-14
python -m china_calendar.cli --upcoming 14
python -m china_calendar.cli --date 2026-10-08 --feed calendar --json
```

查询会区分工作日、周末、放假与调休补班；本地尚无正式安排的年份会显示“未收录”，
不会把周六、周日直接判定为休息日。时间均以北京时间显示；查询仅反映本地缓存数据，
需要最新安排时先执行不带 `--offline` 的生成命令。`--upcoming` 支持 1 至 366 天。

例如查询 `2026-02-14` 会显示“星期六 · 调休补班”，而不是仅按星期判断为休息日。
JSON 单日查询输出一个对象，近期查询输出数组；`day_type` 可为 `holiday`、
`makeup_workday`、`workday`、`weekend` 或 `unknown`，事件结束日期遵循 ICS 的排他上界。

只保留尚未结束的法定假期/补班，建议生成到单独目录：

```bash
python -m china_calendar.cli --offline --future-holidays-only --output /tmp/china-calendar-future
```

正在进行的多日假期保留完整起止日期和原 UID，避免每天同步时重建同一个事件。
自定义目录使用独立的 `.source-state.json`，不会改写默认订阅的生成状态。
`--root` 指向仓库目录，`--today YYYY-MM-DD` 可复现特定日期的生成与近期查询结果。

CI 在 Python 3.11、3.12、3.13 上运行测试并检查订阅可复现性。

## License

[MIT](LICENSE)
