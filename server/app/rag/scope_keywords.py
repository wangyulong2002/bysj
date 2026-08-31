"""越界意图/提示词注入关键词表（T7-4 L0 闸门，8.4.1/v2.6）。

- L0 定位（8.4.1）：**省 token 的快速通道**，不作唯一判据——未命中仍交由
  L1 相关度闸门 / L2 领域围栏判定，避免误伤口语化提问（如"学校几点关门"）；
- 词表配置化：如需运营侧调整，可迁移到字典表（本模块为 v1 落点）；
- `RAG_STRICT_DOMAIN=0` 时 L0 与 L2 关闭，仅保留 L1（9.3）。
"""

# 越界意图（与本校校园信息无关的常见诉求）→ 拒答 out_of_scope
OUT_OF_SCOPE_KEYWORDS = [
    # 写代码 / 编程
    "写代码", "编程", "帮我写个程序", "python", "java", "javascript",
    "sql语句", "debug", "代码报错",
    # 翻译 / 写作
    "翻译成", "英文翻译", "译成英文", "写诗", "写一首", "写作文", "写论文",
    "帮我写一篇", "续写",
    # 投资 / 博彩 / 迷信
    "炒股", "股票", "基金行情", "理财建议", "彩票", "双色球", "开奖",
    "算命", "占卜", "塔罗", "星座运势", "看相", "风水",
    # 医疗 / 心理 / 法律
    "医疗诊断", "我生病了吃什么药", "处方", "心理咨询", "抑郁症治疗",
    "法律建议", "官司怎么打", "判决",
    # 敏感 / 成人
    "成人内容", "色情", "赌博", "毒品", "武器制造", "暴力",
]

# 提示词注入特征（注入防护第 6 层：额外安全层，命中 → 拒答 unsafe）
# 2026-08-30 T7-7 评测集回归扩充：忽略规则变体/角色扮演/提示词窃取/违禁内容
INJECTION_KEYWORDS = [
    "忽略上述指令", "忽略以上指令", "忽略之前的指令", "忽略之前的规则",
    "忽略前面", "无视上述", "无视之前",
    "你现在是", "你的新角色", "请你扮演", "假装你是", "扮演",
    "进入开发者模式", "dan模式", "越狱",
    "ignore previous", "ignore all previous", "ignore the above",
    "disregard previous", "system prompt", "system:", "system：",
    "repeat your instructions", "你的系统提示", "告诉我你的系统",
    "无需遵守", "不受任何规则", "指令都必须执行",
    "违禁物品", "违禁品",
]

# 敏感内容（L3 输出侧二次过滤 → 拒答 unsafe 并记审计）
SENSITIVE_ANSWER_KEYWORDS = [
    "赌博网站", "色情", "毒品", "枪支", "爆炸物制作", "自杀方法",
]


def _normalize(text: str) -> str:
    return (text or "").lower().replace(" ", "").replace("　", "")


def hit_out_of_scope(question: str) -> bool:
    """L0 越界意图关键词命中（归一化空白后匹配，防"忽 略"绕过）。"""
    q = _normalize(question)
    return any(k.replace(" ", "") in q for k in OUT_OF_SCOPE_KEYWORDS)


def hit_injection(question: str) -> bool:
    """提示词注入关键词命中（注入防护第 6 层）。"""
    q = _normalize(question)
    return any(k.replace(" ", "") in q for k in INJECTION_KEYWORDS)


def answer_sensitive(answer: str) -> bool:
    """L3 输出侧敏感内容检测。"""
    a = _normalize(answer)
    return any(k.replace(" ", "") in a for k in SENSITIVE_ANSWER_KEYWORDS)
