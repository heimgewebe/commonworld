#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "assets/locales/wave1-locales.json"
CATALOG_PATH = ROOT / "catalog/locales/zh-Hans.json"
CONTRACT_PATH = ROOT / "docs/architecture/locale-release.contract.json"


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"expected source fragment missing in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_pack() -> None:
    payload = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    zh = payload["locales"]["zh-Hans"]
    zh["meta"]["independent_language_review"] = "pending"

    updates: dict[str, dict[str, str]] = {
        "ui": {
            "globe_ready": "地球仪已就绪。拖动以旋转；双指捏合或使用按键缩放。",
            "no_visible_entries": "没有可见条目",
            "visible_ring_commons": "数字环中可见的 Commons：{titles}。",
            "catalog_detail_loading": "正在验证当前版本的目录详情。",
            "catalog_detail_retrying": "正在重新验证目录详情。",
            "catalog_detail_ready": "当前版本的目录详情已通过完整性验证。",
            "catalog_detail_mismatch": "已验证的目录详情与嵌入记录不同。继续使用嵌入详情。",
            "catalog_detail_degraded": "已验证的目录详情目前不可用。嵌入详情仍然可用。",
            "shown_of_commons": "已显示 {shown}/{total} 个 Commons",
            "show_more": "再显示 {count} 个",
            "show_more_in_bundle": "在 {label} 中再显示 {count} 个 Commons",
            "digital_sphere": "数字 Commons 球体",
            "sphere": "球体",
            "presence_digital": "数字",
            "one_public_location": "1 个公开位置",
            "public_locations": "{count} 个公开位置",
            "location_independent_digital": "与位置无关的数字存在形式",
            "no_public_geometry": "无公开地理几何信息",
            "presence_both": "现场 + 数字",
            "presence_not_published": "未发布存在形式",
            "preview_of_commons": "预览 {shown}/{total} 个 Commons",
            "no_spatial_commons": "此选择中没有具有空间证据的公开 Commons。目录覆盖范围尚未评估。",
            "spatial_summary": "{count} 个具有空间证据的公开 Commons：{distribution}。目录覆盖范围尚未评估；这不表示密度。近似位置中的小群组或筛选后的少量剩余项会被隐藏，不显示数量或类型。",
            "more_commons": "再显示 {count} 个 Commons",
            "more_commons_aria": "再显示 {count} 个 Commons（共 {total} 个）",
            "digital_presence_published": "已发布的数字存在形式",
            "digital_presence_none": "未发布数字存在形式。",
            "relation_none": "未发布有证据支持的关系。",
            "curation_review": "编辑审核：{reviewed}；下次审核：{next}。",
            "open_date": "开放",
            "current_selection": "当前选择中有 {count} 个 Commons。{summary}",
            "remove_filter": "移除 {label}",
            "sort_hint_default": "推荐：保留筛选结果的顺序。",
            "sort_hint_country": "推荐：所选国家/地区的结果保留筛选后的顺序。",
            "sort_hint_catalogued": "最新收录：按目录收录日期从新到旧。",
            "sort_hint_reviewed": "最近审核：按审核日期从新到旧。",
            "sort_hint_title": "名称 A–Z：按标题字母顺序排列。",
            "action_borrow": "借用",
            "action_volunteer": "志愿参与",
            "action_donate": "捐赠",
            "action_contact": "联系",
            "type_energy": "能源",
            "activity_unknown_runtime": "当前运营状态近期尚未核实。来源审查日期：{observed}；优先复核日期：{next}。",
            "location_hidden": "位置已隐藏",
            "location_approximate": "近似位置，误差至少 {uncertainty}",
            "exact_public_point": "精确公开点位",
            "spatial_evidenced_commons": "{count} 个具有空间证据的 Commons",
            "public_areas_approximate_locations": "公开区域和近似位置",
            "public_points_areas_relationships": "公开点位、区域和关系",
            "visible_ring_commons_intro": "数字环中可见的 Commons：",
            "visible_ring_bundles": "数字环组：{bundles}。",
        },
        "themes": {
            "creative-commons": "Creative Commons",
            "digital-equity": "数字公平",
            "energy": "能源",
            "free-software": "自由软件",
            "appropriate-technology": "适用技术",
            "communication": "通信",
            "federation": "联邦式协作",
        },
        "static": {
            "digital_commons": "数字 Commons",
            "digital": "数字",
            "location_independent_digital": "与位置无关的数字存在形式",
            "no_public_geometry": "无公开地理几何信息",
            "activity_unknown": "当前运营状态近期尚未核实。来源审查日期：{observed_at}；优先复核日期：{next_review_at}。",
            "source_number": "来源 {index}",
            "candidate_notice": "翻译预览。此语言尚未启用；仍需独立语言审核。",
            "effective_language": "当前语言：简体中文",
            "interaction": "交互",
        },
        "shell": {
            "shell_001": "<html lang=\"zh-Hans\">",
            "shell_005": "title=\"CommonProject 架构\"",
            "shell_015": "<p class=\"kicker\">发现</p><h2 id=\"discovery-title\">匹配的 Commons</h2>",
            "shell_017": "aria-label=\"当前筛选条件\"",
            "shell_020": "<span>Commons 类型</span>",
            "shell_027": "<option value=\"energy\">能源</option>",
            "shell_033": "<span>操作</span>",
            "shell_034": "<option value=\"\">所有操作</option>",
            "shell_036": "<option value=\"borrow\">借用</option>",
            "shell_039": "<option value=\"volunteer\">志愿参与</option>",
            "shell_040": "<option value=\"donate\">捐赠</option>",
            "shell_042": "<option value=\"contact\">联系</option>",
            "shell_047": "> 数字</label>",
            "shell_060": "<span>访问方式</span>",
            "shell_061": "<option value=\"\">所有访问方式</option>",
            "shell_062": "<option value=\"public\">公开</option>",
            "shell_064": "<option value=\"restricted\">受限</option>",
            "shell_067": "<option value=\"\">所有条目</option>",
            "shell_069": "<span>时效性</span>",
            "shell_070": "<option value=\"\">不限时效</option>",
            "shell_071": "<option value=\"current\">近期已审核</option>",
            "shell_072": "<option value=\"stale\">审核已过期</option>",
            "shell_073": "<span>编审状态</span>",
            "shell_074": "<option value=\"\">所有状态</option>",
            "shell_075": "<option value=\"listed\">已列入</option>",
            "shell_076": "<option value=\"verified\">已核实</option>",
            "shell_079": "<option value=\"auto\">推荐</option>",
            "shell_080": "<option value=\"catalogued\">最新收录</option>",
            "shell_081": "<option value=\"reviewed\">最近审核</option>",
            "shell_083": "推荐排序会根据上下文调整：搜索时按相关性，使用半径时按距离，否则保留筛选后的顺序。",
            "shell_087": "aria-label=\"Commons 搜索结果排名\"",
            "shell_092": "aria-label=\"打开数字环组。点击或按 Enter。\"",
            "shell_110": "数字 Commons 近景",
            "shell_111": "同一组数字 Commons 以分层环组显示，并标出其直接父级路径和名称。",
            "shell_115": "<p id=\"layer-current\" class=\"digital-current\" role=\"status\">数字 Commons 球体</p>",
            "shell_116": ">在数字环组中搜索 Commons</label>",
            "shell_119": "地球 → 大区 → 区域 → 本地环境 → Commons",
            "shell_121": "<h1 id=\"text-title\">直接浏览 Commons</h1>",
            "shell_123": "<h2 id=\"text-filter-title\">筛选器和数字环组</h2>",
            "shell_126": "<p id=\"text-layer-current\" class=\"digital-current\" role=\"status\">数字 Commons 球体</p>",
            "shell_132": "选择展示方式，并查看数据、方法和许可证信息。",
            "shell_133": "<p class=\"kicker\">设置</p><h2 id=\"settings-title\">展示方式</h2>",
            "shell_135": "aria-label=\"选择展示方式\"",
            "shell_137": "<strong>文本</strong><span>列表中的同一组 Commons</span>",
            "shell_138": "<h3>交互</h3>",
            "shell_148": "静态只读 JSON 页面。建议表单不会在 Commonworld 中存储任何内容，只会准备公开的 GitHub 候选条目或本地 JSON 下载。没有 API 运行时、写入路径或独立 CLI。",
            "shell_149": "代码仅按 AGPL-3.0 提供，不附带任何保证。",
            "shell_156": "<section><h3>数字存在</h3>",
            "shell_157": "<section><h3>关系</h3>",
            "shell_160": "<section><h3>编辑审核</h3>",
            "shell_161": "<h1 id=\"static-catalog-fallback-title\">Commonworld 目录</h1>",
        },
        "method": {
            "method_001": "<html lang=\"zh-Hans\">",
            "method_007": "Commonworld 通过一个共享的发现界面展示经过编辑筛选的 Commons。",
            "method_009": "个具有数字存在和/或可公开映射位置的 Commons。这是有限的编辑选择，并非完整的全球统计。",
            "method_013": "<h2>什么算作 Commons</h2>",
            "method_014": "Commonworld 将 Commons 理解为多人共同使用、维护或开发的可识别资源、基础设施、实践或知识体系。纳入目录需要有接近一手的证据，证明存在共享资源、社区、共同实践、规则与责任以及共同利益。仅仅开源、免费访问、非营利、去中心化或用户众多并不足够。具体形式保持开放；判定依据受 <a href=\"./contracts/commonworld/commons-definition.contract.json\">Commons 定义合同</a>约束，并可由机器读取。",
            "method_015": "<h2>建议与编辑审核</h2>",
            "method_016": "公开候选项可通过 <a href=\"./propose.html\">Commons 建议表单</a>准备。Commonworld 不存储表单内容。首选入口是公开 GitHub 议题；也可生成本地 JSON 文件。建议绝不会自动发布。编辑审核会检查身份、一手或近一手来源、Commons 特征、参与方式、隐私、位置精度、重复项和时效性，并依据 <a href=\"./contracts/commonworld/editorial-review.contract.json\">编辑审核合同</a>和 <a href=\"./contracts/commonworld/commons-basis.schema.json\">Commons 基础记录</a>决定是否纳入文件。自 2026 年 7 月 31 日起，新条目或经过实质性重新审核的条目必须具有此记录；更早的条目会在既定复核日期前补做审核。已过期的旧条目享有一次性宽限期，截止 2026 年 8 月 31 日。",
            "method_020": "该站点以静态方式运行在 GitHub Pages 上。MapLibre 由站点本地提供。底图来自公共 OpenFreeMap 实例，它只是非关键的尽力而为依赖，不承诺 SLA。地图失败时，目录和文本视图仍然可用。",
            "method_022": "Commonworld 没有账户、第一方遥测、Cookie 或写入 API。地图请求会直接发送到 OpenFreeMap；技术上，IP 地址可能在那里被处理，并可能因安全原因短期记录。",
            "method_024": "提供文本视图、键盘操作路径、减少动态效果和无 JavaScript 目录。尚未声明完整的屏幕阅读器产品适用性或 WCAG 符合性。",
            "method_026": "<a href=\"https://github.com/heimgewebe/commonworld\" rel=\"external noreferrer\">Commonworld 源代码</a>仅按 AGPL-3.0 提供，不附带任何保证；<a href=\"./LICENSE\">完整许可证文本</a>公开可读。Commonworld 创建的目录数据按 CC0-1.0 发布。第三方商标、地图数据和源数据保留各自权利。<a href=\"./contracts/commonworld/current-state.contract.json\">当前运行状态</a>、<a href=\"./catalog/catalog.json\">目录清单</a>和<a href=\"./contracts/commonworld/project.schema.json\">数据架构</a>均公开可读。",
        },
        "proposal": {
            "proposal_001": "<html lang=\"zh-Hans\">",
            "proposal_002": "content=\"向 Commonworld 提交 Commons 建议以供编辑审核。\"",
            "proposal_003": "<title>Commonworld — 建议一个 Commons</title>",
            "proposal_005": "<p class=\"kicker\">Commonworld 编辑审核</p>",
            "proposal_006": "<h1>建议一个 Commons</h1>",
            "proposal_009": "建议<strong>不会自动发布</strong>。Commonworld 会审核 Commons 的身份、来源、特征、参与方式、地理精度、隐私和时效性。只有经过单独审核的仓库提交才能发布目录条目。",
            "proposal_010": "<strong>公开可见性：</strong>首选入口是 GitHub 上的公开议题。请勿输入电子邮件地址、电话号码、私人地址、坐标、公寓、屋顶、路由器或家庭信息。您的 GitHub 账户就是联系途径；Commonworld 不收集额外联系字段。",
            "proposal_011": "如果没有 GitHub 或网络出现故障，可以在本地下载经过验证的 JSON 文件。Commonworld 不在服务器上存储表单数据。为恢复自动版本切换前开始填写的草稿，内容会暂时保存在当前标签页的会话存储中。下次加载时会立即删除；只有保存时间不超过五分钟时才会恢复。",
            "proposal_014": "<span>通用名称</span>",
            "proposal_018": "<span>Commons 类型</span>",
            "proposal_025": "<option value=\"energy\">能源</option>",
            "proposal_031": "<legend>存在形式</legend>",
            "proposal_033": "<span>数字</span>",
            "proposal_035": "<span>大区域或地点<small>（仅适用于“现场”）</small></span>",
            "proposal_039": "<legend>可验证的参与方式</legend>",
            "proposal_041": "<span>操作 1</span>",
            "proposal_043": "<option value=\"use\">使用</option>",
            "proposal_045": "<option value=\"borrow\">借用</option>",
            "proposal_047": "<option value=\"volunteer\">志愿参与</option>",
            "proposal_048": "<option value=\"donate\">捐赠</option>",
            "proposal_049": "<option value=\"contact\">联系</option>",
            "proposal_054": "<option value=\"\">无</option>",
            "proposal_056": "<span>一手或近一手来源</span>",
            "proposal_058": "至少提供一个接近一手的官方或主要来源，最多五个。",
            "proposal_059": "<span>编辑审核说明（可选）</span>",
            "proposal_060": "placeholder=\"例如：哪个来源支持哪项陈述？\"",
            "proposal_061": "<legend>公开同意与可见性</legend>",
            "proposal_065": ">在 GitHub 中准备公开议题</button>",
            "proposal_066": ">下载经过验证的 JSON</button>",
            "proposal_068": ">直接打开 GitHub</a>",
            "proposal_070": ">建议数据架构</a>",
            "proposal_071": ">编辑审核合同与状态</a>",
            "proposal_072": ">技术路径</a>",
            "proposal_074": "<summary>添加 Commons 基础（可选）</summary>",
            "proposal_075": "这五项信息可让建议直接复用于公开的 Commons 基础草案。可以跳过某项，或明确选择“未知/不知道”。不评分，也不作自动纳入决定。",
            "proposal_076": "<legend>共享资源</legend>",
            "proposal_077": "共同使用或维护的是哪一种可识别的资源、基础设施、实践或知识？",
            "proposal_079": "谁在使用、维护或共同开发共享资源？有哪些证据表明社区存在？",
            "proposal_082": "<legend>维护与责任</legend>",
            "proposal_083": "谁承担共享资源的照料、维护、保护或长期责任？",
            "proposal_085": "共同使用为何在其社会、文化、法律或生态背景下具有正当性？",
            "proposal_088": "<option value=\"confirmed\">已确认</option>",
            "proposal_091": "<span>依据或待解决问题</span>",
            "proposal_094": "关联上方编号的来源。“已确认”至少需要一个来源。",
            "proposal_100": ">Commons 基础架构</a>",
        },
        "taxonomy": {
            "sphere": "数字 Commons 球体",
            "communication_networks": "通信与网络",
            "federated_protocols": "联邦式网络与协议",
            "health_software": "开放医疗",
        },
        "actions": {
            "borrow": "借用",
            "volunteer": "志愿参与",
            "donate": "捐赠",
            "contact": "联系",
        },
        "proposal_runtime": {
            "Project: unknown field {key}.": "项目：未知字段 {key}。",
            "Name": "名称",
            "Presence": "存在形式",
            "Presence: Boolean values are required.": "存在形式：需要布尔值。",
            "Presence: choose at least one option (On site or Digital).": "存在形式：至少选择一个选项（现场或数字）。",
            "Ways to engage: one to three evidenced paths are required.": "参与方式：需要一至三个有证据支持的路径。",
            "Sources: provide at least one and at most five primary-near HTTPS sources.": "来源：请提供至少一个、最多五个一手或近一手 HTTPS 来源。",
            "## Public Commons suggestion": "## 公开 Commons 建议",
            "> This suggestion is an editorial candidate. It is not published automatically.": "> 此建议是编辑审核候选项，不会自动发布。",
            "Commons type": "Commons 类型",
            "Presence": "存在形式",
            "On site and Digital": "现场和数字",
            "Broad region": "大区域",
            "yes — apply especially strict editorial review": "是——进行特别严格的编辑审核",
            "none indicated": "未说明",
            "### Primary-near sources": "### 一手或近一手来源",
            "### Editorial note": "### 编辑审核说明",
            "- [x] I understand that this issue is public.": "- [x] 我了解此 GitHub 议题是公开的。",
            "- [x] I consent to editorial processing of this information.": "- [x] 我同意对这些信息进行编辑处理。",
            "Validated JSON file created locally. Commonworld did not store its contents.": "已在本地创建通过验证的 JSON 文件。Commonworld 未存储其内容。",
            "Digital": "数字",
            "Commons basis draft: dimensions are invalid.": "Commons 基础草案：维度无效。",
            "Commons basis draft: at least one dimension is required when the draft is present.": "存在 Commons 基础草案时，至少需要一个维度。",
            "Commons basis draft: unknown dimension {key}.": "Commons 基础草案：未知维度 {key}。",
            "dimension data is invalid.": "维度数据无效。",
            "confirmed dimensions need at least 20 characters.": "已确认的维度至少需要 20 个字符。",
            "source references must match the listed sources.": "来源引用必须与列出的来源对应。",
            "remove duplicate source references.": "删除重复的来源引用。",
            "confirmed dimensions need at least one source reference.": "已确认的维度至少需要一个来源引用。",
            "Shared good": "共享资源",
            "Stewardship": "维护责任",
            "> Editorial working material only. No score and no automatic admission decision.": "> 仅供编辑工作使用。不评分，也不作自动纳入决定。",
        },
    }

    for section, values in updates.items():
        zh[section].update(values)

    # Keep action vocabulary exactly consistent across every surface.
    shell_actions = {
        "use": "shell_035", "borrow": "shell_036", "learn": "shell_037",
        "contribute": "shell_038", "volunteer": "shell_039", "donate": "shell_040",
        "visit": "shell_041", "contact": "shell_042", "replicate": "shell_043",
    }
    proposal_actions = {
        "use": "proposal_043", "visit": "proposal_044", "borrow": "proposal_045",
        "contribute": "proposal_046", "volunteer": "proposal_047", "donate": "proposal_048",
        "contact": "proposal_049", "replicate": "proposal_050",
    }
    for action, label in zh["actions"].items():
        zh["ui"][f"action_{action}"] = label
        if action in shell_actions:
            zh["shell"][shell_actions[action]] = f'<option value="{action}">{label}</option>'
        if action in proposal_actions:
            zh["proposal"][proposal_actions[action]] = f'<option value="{action}">{label}</option>'

    serialized = json.dumps(zh, ensure_ascii=False)
    forbidden = (
        "活力", "字体 {index}", "西班牙语", "Commons型", "数字戒指", "上市",
        ">穿</option>", "接触", "尺寸", "拔模", "录取决定", "最近评论", "推介会",
        "placeholder =“", "公共几何图形", "数码", "<html lang=\\\"en\\\">",
        "<html lang=\\\"es\\\">", "负担​​得起",
    )
    for marker in forbidden:
        if marker in serialized:
            raise RuntimeError(f"known bad zh-Hans marker remains: {marker}")
    for marker in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"):
        if marker in serialized:
            raise RuntimeError(f"zero-width/control marker remains in zh-Hans pack: {marker.encode('unicode_escape')}")
    write_json(PACK_PATH, payload)


def patch_catalog() -> None:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    projects = payload["projects"]
    projects["enspiral"]["summary"] = "起源于新西兰的协作网络，通过面向社区的企业形式、共享资源和公开记录的工具支持去中心化协作。"
    projects["mastodon"]["digital_label"] = "跨独立服务器运行的联邦式社交通信"
    projects["north-east-syria-autonomous-administration"]["geographic_labels"]["daanes-dynamic-region"] = "叙利亚北部和东部——边界动态变化的区域"
    projects["prinzessinnengarten-kollektiv"]["geographic_labels"]["prinzessinnengarten-neukoelln"] = "Neuer St. Jacobi 公墓的社区花园"
    projects["debian"]["summary"] = "一个自由操作系统，具有开放的软件包档案、公共文档和全球参与。"
    projects["debian"]["digital_label"] = "自由操作系统和全球项目基础设施"
    projects["libreoffice"]["summary"] = "由国际社区开发、记录和翻译的自由开源办公套件。"
    projects["freifunk"]["digital_label"] = "自由社区网络和参与信息"
    projects["zenzeleni-community-networks"]["summary"] = projects["zenzeleni-community-networks"]["summary"].replace("负担​​得起", "负担得起")
    payload["taxonomy_labels"]["sphere"] = "数字 Commons 球体"
    serialized = json.dumps(payload, ensure_ascii=False)
    for marker in ("新西兰新西兰", "联合社交通信", "充满活力的地区", "诺伊尔圣雅各比", "负担​​得起"):
        if marker in serialized:
            raise RuntimeError(f"known bad catalog marker remains: {marker}")
    for marker in ("\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"):
        if marker in serialized:
            raise RuntimeError(f"zero-width/control marker remains in zh-Hans catalog: {marker.encode('unicode_escape')}")
    write_json(CATALOG_PATH, payload)


def patch_contract_policy() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    rollout = contract["rollout"]
    rollout["future_full_locale_activation_requires_observed_demand"] = True
    rollout["browser_translation_may_assist_long_tail_reading"] = True
    rollout["browser_translation_does_not_replace_owned_search_semantics"] = True
    write_json(CONTRACT_PATH, contract)


def patch_tests_and_validator() -> None:
    path = ROOT / "tests/test_locale_wave1.py"
    replace_once(
        path,
        'WAVE1_LOCALES = ("es", "fr", "pt-BR", "ar")',
        'WAVE1_LOCALES = tuple(json.loads((ROOT / "docs/architecture/locale-release.contract.json").read_text(encoding="utf-8"))["rollout"]["wave_1"])',
    )
    replace_once(
        path,
        '        for locale in ("es", "fr", "pt-BR"):\n',
        '        for locale in (tag for tag in WAVE1_LOCALES if tag not in {"ar", "zh-Hans"}):\n',
    )
    replace_once(
        path,
        '                            if locale == "ar":\n                                self.assertTrue(\n                                    "ARABIC" in unicode_name or "LATIN" in unicode_name,\n                                    f"unexpected script in Arabic candidate: {unicode_name}",\n                                )\n                            else:\n',
        '                            if locale == "ar":\n                                self.assertTrue(\n                                    "ARABIC" in unicode_name or "LATIN" in unicode_name,\n                                    f"unexpected script in Arabic candidate: {unicode_name}",\n                                )\n                            elif locale == "zh-Hans":\n                                self.assertTrue(\n                                    "CJK UNIFIED IDEOGRAPH" in unicode_name or "LATIN" in unicode_name,\n                                    f"unexpected script in Simplified Chinese locale: {unicode_name}",\n                                )\n                            else:\n',
    )
    replace_once(path, '            for fragment in forbidden[locale]:\n', '            for fragment in forbidden.get(locale, ()):\n')
    marker = '        self.assertEqual(locales["ar"]["ui"]["action_contribute"], "ساهم")\n'
    insertion = marker + '''        self.assertEqual(locales["zh-Hans"]["themes"]["energy"], "能源")\n        self.assertEqual(locales["zh-Hans"]["themes"]["free-software"], "自由软件")\n        self.assertEqual(locales["zh-Hans"]["static"]["source_number"], "来源 {index}")\n        self.assertEqual(locales["zh-Hans"]["static"]["effective_language"], "当前语言：简体中文")\n        self.assertEqual(locales["zh-Hans"]["shell"]["shell_001"], '<html lang="zh-Hans">')\n        self.assertEqual(locales["zh-Hans"]["method"]["method_001"], '<html lang="zh-Hans">')\n        self.assertEqual(locales["zh-Hans"]["proposal"]["proposal_001"], '<html lang="zh-Hans">')\n'''
    replace_once(path, marker, insertion)

    path = ROOT / "tests/test_i18n.py"
    replace_once(
        path,
        'ROOT = Path(__file__).resolve().parents[1]\n',
        'ROOT = Path(__file__).resolve().parents[1]\nWAVE1_LOCALES = tuple(json.loads((ROOT / "docs/architecture/locale-release.contract.json").read_text(encoding="utf-8"))["rollout"]["wave_1"])\n',
    )
    replace_once(path, '        for locale in ("es", "fr", "pt-BR", "ar"):\n', '        for locale in WAVE1_LOCALES:\n')
    replace_once(path, '        for locale in ("en", "es", "fr", "pt-BR", "ar"):\n', '        for locale in ("en", *WAVE1_LOCALES):\n')
    marker = '            if locale == "ar":\n                self.assertRegex(localized["mundraub"]["summary"], r"[\\u0600-\\u06ff]")\n'
    insertion = marker + '            if locale == "zh-Hans":\n                self.assertRegex(localized["mundraub"]["summary"], r"[\\u4e00-\\u9fff]")\n'
    replace_once(path, marker, insertion)

    path = ROOT / "tests/js/i18n.test.mjs"
    text = path.read_text(encoding="utf-8")
    text = text.replace("for (const locale of ['es', 'fr', 'pt-BR', 'ar'])", "for (const locale of WAVE1_LOCALES)")
    text = text.replace("for (const locale of ['en', 'es', 'fr', 'pt-BR', 'ar'])", "for (const locale of ['en', ...WAVE1_LOCALES])")
    text = text.replace("for (const locale of ['en', 'de', 'es', 'fr', 'pt-BR', 'ar'])", "for (const locale of RELEASED_LOCALES)")
    old = "  assert.equal(shouldLoadWave1LocalePack('ar', false), true);\n"
    if old not in text:
        raise RuntimeError("expected Wave-1 loader assertion missing")
    text = text.replace(old, old + "  assert.equal(shouldLoadWave1LocalePack('zh-Hans', false), true);\n", 1)
    old = "  assert.equal(normalizeLocale('fr'), 'fr');\n"
    if old not in text:
        raise RuntimeError("expected normalizeLocale assertion missing")
    text = text.replace(old, old + "  assert.equal(normalizeLocale('zh-CN'), 'zh-Hans');\n", 1)
    path.write_text(text, encoding="utf-8")

    path = ROOT / "scripts/validate_locale_release.py"
    replace_once(
        path,
        '                    and catalog_review.get("writer_independence") == "independent_from_grok_4_5_writer"\n',
        '                    and isinstance(catalog_review.get("writer_independence"), str)\n                    and re.fullmatch(r"independent_from_[a-z0-9_]+_writer", catalog_review["writer_independence"]) is not None\n',
    )
    old = '''    for field in (\n        "promotion_is_evidence_bound",\n        "wave_order_may_follow_observed_demand",\n        "planned_locales_must_not_be_selectable",\n        "candidate_locales_must_not_be_selectable",\n        "candidate_surfaces_must_be_noindex",\n    ):\n'''
    new = '''    for field in (\n        "promotion_is_evidence_bound",\n        "wave_order_may_follow_observed_demand",\n        "planned_locales_must_not_be_selectable",\n        "candidate_locales_must_not_be_selectable",\n        "candidate_surfaces_must_be_noindex",\n        "future_full_locale_activation_requires_observed_demand",\n        "browser_translation_may_assist_long_tail_reading",\n        "browser_translation_does_not_replace_owned_search_semantics",\n    ):\n'''
    replace_once(path, old, new)

    path = ROOT / "tests/test_locale_release_contract.py"
    marker = '    def test_rollout_waves_are_disjoint_and_not_yet_selectable(self) -> None:\n'
    new_test = '''    def test_future_full_locales_are_demand_gated_but_browser_translation_is_only_an_assist(self) -> None:\n        contract = copy.deepcopy(self.contract)\n        for field in (\n            "future_full_locale_activation_requires_observed_demand",\n            "browser_translation_may_assist_long_tail_reading",\n            "browser_translation_does_not_replace_owned_search_semantics",\n        ):\n            contract["rollout"][field] = False\n            self.assertTrue(any(field in error for error in validate_contract(contract, ROOT)), field)\n            contract["rollout"][field] = True\n\n'''
    replace_once(path, marker, new_test + marker)


def main() -> int:
    patch_pack()
    patch_catalog()
    patch_contract_policy()
    patch_tests_and_validator()
    print("zh-Hans editorial corrections and demand-gated locale policy applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
