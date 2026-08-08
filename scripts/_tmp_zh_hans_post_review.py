#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "assets/locales/wave1-locales.json"
CATALOG_PATH = ROOT / "catalog/locales/zh-Hans.json"


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def patch_pack() -> None:
    payload = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    zh = payload["locales"]["zh-Hans"]

    zh["static"].update({
        "public_location_one": "{count} 个公开位置",
        "public_location_many": "{count} 个公开位置",
    })
    zh["shell"].update({
        "shell_002": "content=\"Commonworld 让人们在涵盖全球、区域、本地和数字空间的共享地球界面上发现 Commons。\"",
        "shell_048": "选择多个存在形式时必须同时满足（AND）。",
        "shell_102": "颜色表示 Commons 类型。在全球视图中，每个国家/地区的条纹按已发布位置记录中的 Commons 类型比例显示。放大后，视图会转为区域分组，并最终显示具体位置。目录覆盖范围尚未评估；地图既不表示密度，也不能证明某地不存在 Commons。",
        "shell_112": "aria-label=\"搜索 Commons 和筛选数字环组\"",
        "shell_122": "与地球视图使用相同的身份、筛选器和选择——只是没有空间显示。",
    })
    runtime = zh["proposal_runtime"]
    runtime.update({
        "no email address or phone number in public suggestions.": "公开建议中不得包含电子邮件地址或电话号码。",
        "no private address or coordinates in public suggestions.": "公开建议中不得包含私人地址或坐标。",
        "Region": "区域",
        "Location precision: only a country or broad region is allowed.": "位置精度：仅允许国家或大区域。",
        "Region: do not provide one for digital-only presence.": "区域：仅数字存在时不要填写。",
        "Location precision: do not provide it for digital-only presence.": "位置精度：仅数字存在时不要填写。",
        "Editorial note": "编辑审核说明",
        "Official website: only a valid HTTPS address is allowed.": "官方网站：仅允许有效的 HTTPS 地址。",
        "Sensitive-location indication: required.": "必须说明位置是否敏感。",
        "Ways to engage: check the type and HTTPS address.": "参与方式：请检查类型和 HTTPS 地址。",
        "not applicable (digital only)": "不适用（仅数字）",
        "The automatic release change was paused because the draft could not be stored safely in this tab. The form remains open.": "自动版本切换已暂停，因为草稿无法安全保存在此标签页中。表单仍保持打开。",
        "Draft input was restored after this tab changed release version.": "此标签页切换发布版本后，草稿输入已恢复。",
        "Automated submission blocked.": "自动提交已阻止。",
        "Repeated preparation is rate-limited: wait one minute or use the existing GitHub tab.": "重复准备受到频率限制：请等待一分钟，或使用已经打开的 GitHub 标签页。",
        "The GitHub tab was blocked. Use the direct link or the JSON download.": "GitHub 标签页被浏览器拦截。请使用直接链接或下载 JSON。",
        "GitHub was opened. The suggestion is transferred only when you submit the public issue; this does not publish it in the catalog.": "已打开 GitHub。只有提交公开议题后，建议才会被转移；这不会将其发布到目录中。",
        "Commons basis draft: status must remain needs_review.": "Commons 基础草案：状态必须保持为 needs_review。",
    })

    serialized = json.dumps(zh, ensure_ascii=False)
    forbidden = (
        "世界观", "过滤环束", "公开问题", "字体 {index}", "西班牙语",
        "Commons型", "数字戒指", "录取决定", "拔模", "尺寸无效",
    )
    for marker in forbidden:
        if marker in serialized:
            raise RuntimeError(f"post-review forbidden zh-Hans marker remains: {marker}")
    write_json(PACK_PATH, payload)


def patch_catalog() -> None:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    taxonomy = payload["taxonomy_labels"]
    taxonomy.update({
        "communication_networks": "通信与网络",
        "federated_protocols": "联邦式网络与协议",
        "health_software": "开放医疗",
    })
    projects = payload["projects"]
    projects["common-voice"]["summary"] = "一个开放的多语言语音数据集，语言社区在其中贡献录音、句子和验证，为语音技术构建可自由使用的数据。"
    projects["freifunk"]["summary"] = "一项致力于自由、由社区建设的通信网络和开放数字基础设施的非商业倡议。"
    projects["libreoffice"]["digital_label"] = "自由办公套件和开放的参与路径"
    projects["librivox"]["summary"] = "一个全球志愿者社区，将公共领域文本录制为可自由访问的有声读物，并在没有商业访问障碍的情况下发布录音。"
    projects["librivox"]["digital_label"] = "由志愿者制作的开放有声读物集合"
    projects["open-food-facts"]["summary"] = "一个开放的食品数据库，志愿者收集和审查产品数据和图像，并在 ODbL 下发布，供自由再利用。"
    projects["open-source-ecology"]["digital_label"] = "自由获取机器设计、文档并参与全球协作开发"
    projects["openmrs"]["digital_label"] = "自由医疗软件、文档和全球协作"
    projects["reprap"]["summary"] = "一个围绕自由记录、可制造自身大部分零件的 3D 打印机展开的全球开放硬件项目；其设计可由社区协作构建、调整和改进。"
    projects["safecast"]["digital_label"] = "开放环境测量数据、地图、上传和 API 访问"
    projects["the-things-network"]["digital_label"] = "社区 LoRaWAN 网络、开放网络软件、论坛和学习资源"
    projects["wikibooks"]["summary"] = "合作编写和改进的开放教科书、手册和非小说类书籍集合，可自由使用。"
    projects["wikibooks"]["digital_label"] = "开放教科书和开放学习材料"
    projects["wikidata"]["summary"] = "一个开放的知识数据库，提供可在维基媒体项目和其他应用中使用和链接的结构化、机器可读语句。"
    projects["wikidata"]["digital_label"] = "开放的结构化知识数据库"
    projects["wikimedia-commons"]["summary"] = "一个协作构建的开放图像、音频、视频和其他媒体文件集合，可自由再利用。"
    projects["wikimedia-commons"]["digital_label"] = "开放媒体集合，可供全球自由再利用"
    projects["wikipedia"]["summary"] = "一个协作创建、可自由访问的多语言百科全书，其内容由志愿者编写和维护。"
    projects["wikipedia"]["digital_label"] = "多语言开放百科全书"
    projects["wikiversity"]["summary"] = "一个提供多语言开放学习资源、课程和协作教育项目的平台。"
    projects["wikiversity"]["digital_label"] = "开放学习资源和协作教育项目"

    serialized = json.dumps(payload, ensure_ascii=False)
    forbidden = (
        '"federated_protocols": "联盟和协议"',
        '"libreoffice"',
    )
    if '"federated_protocols": "联盟和协议"' in serialized:
        raise RuntimeError("federated_protocols still uses alliance terminology")
    if projects["libreoffice"]["digital_label"].startswith("免费"):
        raise RuntimeError("LibreOffice still conflates software freedom with price")
    if projects["reprap"]["summary"].startswith("一个针对免费记录"):
        raise RuntimeError("RepRap still contains literal machine-translation wording")
    write_json(CATALOG_PATH, payload)


def patch_regressions() -> None:
    path = ROOT / "tests/test_locale_wave1.py"
    text = path.read_text(encoding="utf-8")
    marker = '        self.assertEqual(locales["zh-Hans"]["static"]["effective_language"], "当前语言：简体中文")\n'
    additions = marker + '''        self.assertEqual(locales["zh-Hans"]["static"]["public_location_many"], "{count} 个公开位置")\n        self.assertNotIn("世界观", locales["zh-Hans"]["shell"]["shell_102"])\n        self.assertNotIn("公开问题", locales["zh-Hans"]["proposal_runtime"]["GitHub was opened. The suggestion is transferred only when you submit the public issue; this does not publish it in the catalog."])\n'''
    if marker not in text:
        raise RuntimeError("zh-Hans regression anchor missing")
    path.write_text(text.replace(marker, additions, 1), encoding="utf-8")

    path = ROOT / "tests/test_i18n.py"
    text = path.read_text(encoding="utf-8")
    marker = '            if locale == "zh-Hans":\n                self.assertRegex(localized["mundraub"]["summary"], r"[\\u4e00-\\u9fff]")\n'
    additions = marker + '''                self.assertEqual(localized["libreoffice"]["digital_label"], "自由办公套件和开放的参与路径")\n                self.assertEqual(localized["reprap"]["summary"], "一个围绕自由记录、可制造自身大部分零件的 3D 打印机展开的全球开放硬件项目；其设计可由社区协作构建、调整和改进。")\n'''
    if marker not in text:
        raise RuntimeError("zh-Hans catalog regression anchor missing")
    path.write_text(text.replace(marker, additions, 1), encoding="utf-8")


def main() -> int:
    patch_pack()
    patch_catalog()
    patch_regressions()
    print("zh-Hans post-review linguistic polish applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
