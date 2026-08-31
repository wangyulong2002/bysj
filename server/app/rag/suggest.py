"""推荐问题配置（T7-5，8.5/6.2）。

v1 从本模块读固定列表（按知识分类 5.3.15 各 1~2 条），降低首屏输入门槛；
预留按 `campus_rag_log` 高频问题动态生成（v1 不实现，8.5）。
键为 `campus_knowledge.category`（1师资 2宿舍 3食堂 4制度 5招生 6设施 7其他）。
"""

SUGGEST_QUESTIONS: dict[str, list[str]] = {
    "1": ["学校有哪些知名教授和师资力量？"],
    "2": ["学校宿舍条件如何？", "宿舍有空调和独立卫浴吗？"],
    "3": ["食堂有哪些风味窗口？"],
    "4": ["奖学金评定办法是什么？", "请假流程怎么走？"],
    "5": ["新生报到流程是什么？"],
    "6": ["图书馆开放时间是几点？", "体育馆怎么预约？"],
}


def build_suggest_list() -> list[str]:
    """按分类顺序各取 1~2 条，拼接为推荐问题列表（去重保序）。"""
    items: list[str] = []
    for cat in sorted(SUGGEST_QUESTIONS):
        for q in SUGGEST_QUESTIONS[cat][:2]:
            if q not in items:
                items.append(q)
    return items
