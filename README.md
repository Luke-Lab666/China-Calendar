# China Calendar

面向 iPhone、iPad 和 Mac 的中国大陆日历订阅，合并展示：

- 国务院正式发布的法定节假日与调休补班；
- 中国官方纪念日、传统节日和常见社会日期；
- 二十四节气的准确交节时刻，按北京时间精确到分钟。

## 一键订阅

主日历包含全部内容：

```text
https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/calendar.ics
```

也可以按内容分别订阅：

| 日历 | 订阅地址 |
| --- | --- |
| 法定节假日与调休 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/holidays.ics` |
| 二十四节气 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/solar-terms.ics` |
| 传统节日与纪念日 | `https://raw.githubusercontent.com/Luke-Lab666/China-Calendar/main/calendars/observances.ics` |

iOS 添加方式：复制订阅地址，打开“设置” → “App” → “日历” → “日历账户” →
“添加账户” → “其他” → “添加已订阅的日历”，粘贴地址并保存。

日历文件提供橙色作为建议颜色。若 iOS 没有自动采用，可在“日历”App 底部点“日历”，
再点该订阅右侧的 `ⓘ`，手动选择橙色。

> 这是“订阅日历”，不要下载后再导入。订阅后，仓库更新会由系统定期同步；具体拉取频率由 iOS 控制。

## 更新策略

- GitHub Actions 每天北京时间 **21:00** 检查一次并重新生成日历。
- 数据从 **2025 年**开始，不生成更早年份。
- 调休安排只在国务院正式通知发布后加入；公告为空的未来年份保持为空，绝不预测。
- 生成结果覆盖上一年到未来两年，随时间滚动扩展。
- 日历内不设置提醒，不会突然弹出大量通知。

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

## iOS 显示方式

- `春节（休）`：整段假期显示为连续的多日横条，日期旁显示“休”；
- `春节（班）`：国务院安排的补班日，日期旁显示“班”；
- `立春`：事件开始时间就是准确的北京时间交节瞬间，精确到分钟；
- `传统 · 元宵节`：按农历计算的传统节日；
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

只想在输出中保留今天及之后的法定放假/补班，可加：

```bash
python -m china_calendar.cli --future-holidays-only
```

## License

[MIT](LICENSE)
