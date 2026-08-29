#!/usr/bin/env python3
"""生成演示数据 SQL（每张业务表 >= 10 条，幂等可重复执行）。

用法：
  python3 scripts/gen_seed_demo.py          # 生成 sql/seed_demo_data.sql
  mysql -h127.0.0.1 -P3307 -uroot -p123456 < sql/seed_demo_data.sql

设计约束对齐（设计报告 5.x）：
- 数据段：id 50000~50130（避开业务自增 id），删除走固定 id 段 → 幂等
- 外键依赖顺序：dept→class/course→term→sys_user→student/teacher→offering→schedule/score/...
- 通用审计字段：create_by/create_time/update_by/update_time/del_flag('0')
- sys_user 密码：PBKDF2（123456），role_code 区分角色
- campus_term.is_current 仅一条；排课不冲突；score (student,offering) 唯一
"""
import hashlib
import os

START = 50000
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sql", "seed_demo_data.sql")


def pbkdf2(raw: str = "123456") -> str:
    """生成与 Django 兼容的 PBKDF2 密码哈希（123456）。"""
    iterations = 10000
    salt = os.urandom(8).hex()
    dk = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt.encode(), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${__import__('base64').b64encode(dk).decode().rstrip('=')}"


# ---- 基础数据 ----
DEPTS = ["计算机学院", "软件学院", "人工智能学院", "电子信息学院", "机械工程学院",
         "土木工程学院", "经济管理学院", "外国语学院", "艺术设计学院", "数理学院"]
CLASSES = ["计科2301", "软工2301", "人工智能2301", "电信2301", "机械2301",
           "土木2301", "经管2301", "英语2301", "艺术2301", "数理2301"]
COURSES = [("程序设计基础", "CS101"), ("数据结构", "CS201"), ("操作系统", "CS301"),
           ("计算机网络", "CS302"), ("数据库原理", "CS401"), ("软件工程", "SE201"),
           ("机器学习", "AI301"), ("数字电路", "EE201"), ("机械制图", "ME101"),
           ("高等数学", "MA101")]

# ---- 仿真演示内容（公告/知识库为 RAG 数据源，内容须真实可信；学校统一名称：wyl学院）----
SCHOOL = "wyl学院"

MAJORS = ["计算机科学与技术", "软件工程", "人工智能", "电子信息工程", "机械设计制造及其自动化",
          "土木工程", "工商管理", "英语", "视觉传达设计", "应用数学"]

TEACHER_NAMES = ["张明远", "李慧敏", "王建国", "刘婷婷", "陈志强",
                 "赵雅琴", "孙浩然", "周雨欣", "吴俊杰", "郑晓彤"]
STUDENT_NAMES = ["李文博", "王梦琪", "张子豪", "刘思远", "陈嘉怡",
                 "杨一帆", "黄晓萌", "徐子轩", "孙一诺", "胡凯文"]

# 公告 10 条：(标题, 正文, ann_type, dept_offset[None=校园级])
# 状态/置顶由循环控制：i0~i4 发布（i0/i1 置顶），i5~i7 草稿，i8~i9 下架
# 覆盖：招生/新生报到/宿舍/食堂/奖学金/教师招聘/课程设计/学科竞赛/校车/图书馆
ANNOUNCEMENTS = [
    ("wyl学院2026年全日制普通本科招生简章",
     "经浙江省教育厅批准，wyl学院2026年面向全国12个省（自治区、直辖市）计划招收全日制普通本科生3200名，"
     "涵盖计算机科学与技术、软件工程、人工智能、电子信息工程等24个本科专业。学费标准：普通专业4800元/年，"
     "艺术类专业9000元/年，住宿费1000至1500元/年。考生可于6月26日至7月2日登录省教育考试院志愿填报系统报考，"
     "院校代码3388，录取原则为分数优先、遵循志愿，录取结果7月中旬可在招生网查询。招生咨询热线0571-88012345，"
     "邮箱zsb@wyl.edu.cn。wyl学院招生办公室", "1", None),
    ("2026级新生入学报到须知",
     "2026级新生请于9月6日8:00至17:00在wyl学院大学生活动中心办理报到手续，需携带录取通知书原件、身份证原件"
     "及复印件2份、纸质档案袋、一寸免冠照片8张，户口迁移证按自愿原则办理。学费与住宿费请于8月25日前登录"
     "智慧校园平台线上缴纳，报到当天凭缴费凭证领取宿舍钥匙与校园一卡通。家庭经济困难学生可现场申请绿色通道，"
     "并设生源地助学贷款咨询台。9月6日7:00至16:00，地铁1号线wyl学院站B出口与学校东门设有新生接站校车。"
     "咨询电话0571-88012789。wyl学院学生工作处", "1", None),
    ("关于2026-2027学年学生宿舍安排的通知",
     "为优化住宿资源配置，现将2026-2027学年学生宿舍安排通知如下：学生公寓1至5号楼为4人间，上床下桌、独立卫浴、"
     "配备空调，住宿费1500元/年；6至9号楼为6人间，独立卫浴、配备空调，住宿费1000元/年。宿舍调整申请请于"
     "8月20日至9月5日登录智慧校园宿舍服务模块提交，逾期不再受理。宿舍门禁时间为23:00至次日6:00，晚归须向"
     "宿管员登记。设施报修通过宿管在线小程序提交，或拨打后勤值班电话0571-88013567。wyl学院后勤管理处",
     "1", None),
    ("关于第一食堂营业时间调整的通知",
     "自9月1日起，wyl学院第一食堂营业时间调整为早餐6:30-9:00、午餐11:00-13:00、晚餐16:30-19:00；第二食堂与"
     "清真餐厅维持原时间：早餐6:30-9:30、午餐10:30-13:30、晚餐16:30-19:30，第二食堂一楼夜宵窗口营业至22:00。"
     "第一食堂已完成智慧餐台改造，支持自选称重结算，校园一卡通、微信、支付宝均可支付。师生对菜品质量与价格"
     "如有意见，可向饮食服务中心反馈，电话0571-88014233。wyl学院后勤管理处", "1", None),
    ("关于开展2025-2026学年奖学金评定的通知",
     "wyl学院2025-2026学年奖学金评定工作定于9月10日启动。本次评定设国家奖学金8000元/人、国家励志奖学金"
     "5000元/人、校一等奖学金3000元/人、二等奖学金2000元/人、三等奖学金1000元/人。申请条件：热爱祖国、"
     "品行端正，当学年必修课程无不及格记录，综合测评成绩位于班级前30%。学生须于9月25日前登录智慧校园"
     "奖助申请模块提交申请并上传成绩单，经班级民主评议、学院审核后公示5个工作日。政策咨询请联系学生资助"
     "管理中心0571-88015478。wyl学院学生工作处", "1", None),
    ("计算机学院2026年专任教师招聘公告",
     "因学科建设与专业发展需要，wyl学院计算机学院面向社会公开招聘专任教师6名，其中教授或副教授2名、讲师4名，"
     "研究方向为人工智能、大数据、网络安全与软件工程。应聘者须具有博士学位，副教授及以上职称者原则上不超过"
     "45周岁。学校提供安家费15至60万元、科研启动经费5至20万元，并协助解决周转房与子女入学。报名截止"
     "2026年10月31日，简历请发送至rsc@wyl.edu.cn，邮件主题注明应聘计算机学院岗位与姓名。联系人：人事处"
     "王老师，电话0571-88016234。wyl学院人事处", "2", 0),
    ("计算机学院2026年秋季学期课程设计安排",
     "本学期课程设计安排如下：涉及数据结构、操作系统、数据库原理三门课程，实施周期为第9周至第16周。选题须于"
     "第8周周五前在实验教学平台确认，每组2至3人，成果须包含需求分析、设计文档与可运行源码三部分。中期检查"
     "安排在第12周，未参加者成绩作降档处理；验收答辩安排在第16周周四至周五，地点为实验楼A305、A307教室。"
     "指导教师分组名单与评分标准已在各班级群公布，如有疑问请联系计算机学院教务办0571-88017321。"
     "wyl学院计算机学院", "2", 0),
    ("关于组织学生参加2026年蓝桥杯程序设计大赛的通知",
     "2026年第十七届蓝桥杯全国软件和信息技术专业人才大赛报名工作已启动，wyl学院拟组织学生参加Python程序设计"
     "与C/C++程序设计两个组别。校内选拔赛定于10月中旬举行，通过选拔者由学院统一报名省赛并全额报销报名费。"
     "有意参赛的同学请于10月8日前将姓名、学号与参赛组别报送至所在班级辅导员处。赛前培训每周三晚19:00在"
     "实验楼B201举行，由陈志强老师主讲算法与真题解析。wyl学院人工智能学院", "2", 2),
    ("关于调整校园班车时刻表的通知",
     "自10月8日起，wyl学院校园班车运行方案调整如下：东门至教学楼线路7:00-18:00每15分钟一班；东门至地铁站"
     "线路早晚高峰（7:00-9:00、16:30-19:00）每10分钟一班，平峰每20分钟一班；周末及节假日仅保留东门至地铁站"
     "线路。乘车须出示校园一卡通，禁止携带易燃易爆物品。班车实时位置可在智慧校园校车服务模块查询，寒暑假停运。"
     "wyl学院后勤管理处", "1", None),
    ("关于图书馆空调系统检修临时闭馆的通知",
     "因中央空调系统年度检修需要，图书馆定于10月12日8:00-18:00临时闭馆，当日19:00恢复开放。闭馆期间到期的"
     "图书归还日期自动顺延，线上预约的研修间自动取消且不扣信用分；数字资源（电子图书、知网等数据库）经校园网"
     "或VPN访问不受影响。由此带来的不便敬请谅解，如有疑问请拨打图书馆服务台电话0571-88017891。wyl学院图书馆",
     "1", None),
]

# 知识库 10 条：(标题, 分类, 正文, 标签)；分类 1师资 2宿舍 3食堂 4制度 5招生 6设施 7其他
KNOWLEDGE_DOCS = [
    ("wyl学院师资力量概况", "1",
     "wyl学院现有专任教师760余人，其中教授82人、副教授216人，具有博士学位教师占比58%；拥有省级教学名师6人、"
     "省级科技创新团队4个。计算机学院现有专任教师128人，人工智能、软件工程等热门专业课程均由教授领衔授课。"
     "学校每年选派教师赴国内外高校访学与进修，近三年获省级以上教学成果奖9项。", "师资,教授,计算机学院"),
    ("学生宿舍介绍", "2",
     "wyl学院学生宿舍分为4人间与6人间，均配备空调、独立卫浴、热水与无线网络。4人间为上床下桌组合家具，"
     "6人间为上下铺。门禁时间23:00至次日6:00，晚归需向宿管员登记。每栋楼配备宿管员、自助洗衣机与开水间。"
     "住宿费：4人间1500元/年，6人间1000元/年。宿舍设施报修通过宿管在线小程序提交，一般48小时内响应。",
     "宿舍,空调,住宿费"),
    ("食堂与餐饮服务", "3",
     "wyl学院共有两个食堂与一处清真餐厅。第一食堂以基础大伙为主，人均8至12元；第二食堂设有麻辣香锅、煲仔饭、"
     "面食等风味档口，人均10至18元。营业时间：早餐6:30-9:30，午餐10:30-13:30，晚餐16:30-19:30，第二食堂夜宵"
     "窗口营业至22:00。支持校园一卡通、微信与支付宝支付。", "食堂,餐饮,营业时间"),
    ("学生请假管理制度", "4",
     "wyl学院学生请假制度：1天以内由辅导员审批；1至3天由辅导员签署意见后报学院教学院长审批；3天以上须报教务处"
     "备案。病假需附医院证明，事假需说明具体事由。请假期间离校须履行登记手续，假期结束应及时销假。一学期事假"
     "累计超过课程总学时三分之一者，该课程不得参加期末考核。", "请假,制度,审批"),
    ("招生常见问题解答", "5",
     "wyl学院招生常见问题：学费标准为普通专业4800元/年、艺术类专业9000元/年、中外合作办学18000元/年；住宿费"
     "1000至1500元/年。学校面向全国12个省份招生，院校代码3388，录取原则为分数优先、遵循志愿。新生可申请转专业，"
     "转出无门槛、转入需参加考核，于第一学年末统一办理。招生办咨询电话0571-88012345。", "招生,学费,转专业"),
    ("图书馆与体育设施", "6",
     "wyl学院图书馆馆藏纸质图书156万册、电子图书90万册，开放时间7:00-22:00，考试周延长至23:00。学生可借图书"
     "30册、借期30天，可续借1次。体育馆含游泳馆、篮球馆与健身房，凭一卡通免费或低收费预约，开放时间14:00-21:30。"
     "智慧教室覆盖全部教学楼，专业实验室晚间向预约学生开放。", "图书馆,体育馆,设施"),
    ("校园网与一卡通使用指南", "7",
     "wyl学院校园网账号为学生学号，初始密码为证件号后6位，登录自助服务平台后请及时修改；宿舍有线与无线网络"
     "已全覆盖，出口带宽10G。校园一卡通支持食堂消费、图书借阅、门禁与班车乘坐，可通过智慧校园APP在线充值"
     "（支持微信与支付宝），卡片遗失请第一时间在一卡通中心或APP上挂失。", "校园网,一卡通,充值"),
    ("教师答疑与办公安排", "1",
     "各专任教师每周安排不少于2小时的固定答疑时间，地点在各系办公室，具体时间表于开学第一周在教务系统公布。"
     "学生可通过教务系统教师信息栏目查询教师邮箱与办公地点。学业问题请优先联系任课教师，未能解决的由系教学"
     "秘书协调处理。", "答疑,办公,教师", ),
    ("宿舍安全管理规定", "2",
     "宿舍内严禁使用电磁炉、电热锅等大功率电器，严禁私拉乱接电线，严禁存放易燃易爆物品；宿舍内吸烟一经发现"
     "按校纪处理。每学期组织消防演练不少于1次。发现安全隐患请立即报告宿管员，或拨打保卫处24小时值班电话"
     "0571-88011110。", "宿舍,安全,消防"),
    ("2026年招生专业与计划增补", "5",
     "wyl学院2026年新增智能科学与技术、数据科学与大数据技术两个本科专业，首批各招收90人；计算机科学与技术"
     "专业获批省级一流专业建设点，招生计划扩大至240人。具体分省分专业招生计划以各省教育考试院公布为准，"
     "考生可关注wyl学院招生网与官方微信公众号获取最新信息。", "招生,专业,计划"),
]

# 请假演示：(leave_type 1事假2病假3其他, 事由, 审批意见)
LEAVE_DEMOS = [
    ("2", "突发肠胃炎，校医院建议休养两天", "情况属实，同意病假，注意休息"),
    ("1", "家中祖母病重，需返乡探望", "情况属实，同意请假，路上注意安全"),
    ("2", "感冒发热38.5度，需外出就医", "同意病假，返校后请补交就诊证明"),
    ("1", "参加全国大学生数学建模竞赛集训", "同意，注意平衡课程学习"),
    ("2", "智齿拔除手术后需复诊", "同意病假，注意术后护理"),
    ("1", "回户籍地办理身份证换领手续", "材料属实，同意事假"),
    ("2", "急性腹泻，需在校医院输液观察", "同意病假，如有加重及时转诊"),
    ("1", "陪同父母来校参观并办理相关手续", "同意事假，按时报到销假"),
    ("2", "过敏性皮炎复诊", "同意病假"),
    ("1", "参加姐姐婚礼，需返乡两天", "同意事假，注意往返安全"),
]

# RAG 问答演示（前 7 条：真实问题 + 基于资料的回答；ref_ids 指向 chunk id）
# chunk id 规则：偶数位 i → 公告 70000+i//2；奇数位 i → 知识库 20000+i//2，即 chunk id = 80000+i
RAG_QA = [
    ("宿舍是几人间？有独立卫浴和空调吗？",
     "wyl学院学生宿舍分为4人间与6人间，均配备空调、独立卫浴与热水。4人间为上床下桌组合家具，住宿费1500元/年；"
     "6人间住宿费1000元/年。宿舍楼设有自助洗衣机与开水间。", ["80003"]),
    ("学校食堂几点开门？有夜宵吗？",
     "第一食堂早餐6:30-9:00、午餐11:00-13:00、晚餐16:30-19:00；第二食堂与清真餐厅营业至19:30，第二食堂一楼"
     "夜宵窗口营业至22:00，支持校园一卡通、微信与支付宝支付。", ["80005"]),
    ("新生报到需要带哪些材料？",
     "2026级新生9月6日在大学生活动中心报到，需携带录取通知书原件、身份证及复印件2份、纸质档案、一寸免冠照片"
     "8张，户口迁移证自愿办理；线上缴费后凭凭证领取宿舍钥匙与校园一卡通。", ["80002", "80000"]),
    ("wyl学院学费一年多少钱？",
     "wyl学院普通本科专业学费4800元/年，艺术类专业9000元/年，中外合作办学18000元/年；住宿费视房型为1000至"
     "1500元/年。", ["80009"]),
    ("奖学金有哪些？怎么申请？",
     "设有国家奖学金8000元/人、国家励志奖学金5000元/人及校一、二、三等奖学金（3000/2000/1000元）。须于"
     "9月25日前在智慧校园奖助申请模块提交申请，综合测评位于班级前30%且必修课无不及格。", ["80008"]),
    ("请假超过三天找谁审批？",
     "1天以内由辅导员审批；1至3天由辅导员签署意见后报学院教学院长审批；3天以上须报教务处备案。病假需附医院"
     "证明，假期结束应及时销假。", ["80007"]),
    ("计算机学院师资力量怎么样？",
     "wyl学院计算机学院有专任教师128人，人工智能、软件工程等热门专业课程均由教授领衔授课；全校有教授82人、"
     "副教授216人，博士学位教师占比58%，拥有省级教学名师6人。", ["80001"]),
]

PWD = pbkdf2()
ID = [START + i for i in range(130)]


def audit(creator: int = 1) -> str:
    """通用审计字段（5.1）。"""
    return f"1, NOW(), {creator}, NOW(), '0'"


def main() -> None:
    sql = []
    A = sql.append
    A("-- ============================================================")
    A("-- seed_demo_data.sql  演示数据（每张业务表 >= 10 条）")
    A("-- 由 scripts/gen_seed_demo.py 生成；幂等：删除 id 50000~50129 后重建")
    A("-- 依赖：先执行 init_all.sql（表结构）")
    A("-- ============================================================")
    A("USE campus;")
    A("SET NAMES utf8mb4;")
    A("SET FOREIGN_KEY_CHECKS = 0;")

    # 清理数据段（幂等）：覆盖所有种子 id 段（基础表 50000~50129 +
    # knowledge +20000 / rag_chunk +30000 / rag_log +40000 / rag_task +50000 /
    # idempotency +60000 / announcement +70000），统一 50000~120010
    for t in ["campus_department", "campus_class", "campus_course", "campus_term",
              "campus_student", "campus_teacher", "campus_course_offering",
              "campus_course_schedule", "campus_score", "campus_score_audit",
              "campus_leave", "campus_message", "campus_file", "campus_knowledge",
              "campus_rag_chunk", "campus_rag_log", "campus_rag_task",
              "campus_idempotency_key", "campus_announcement"]:
        A(f"DELETE FROM {t} WHERE id BETWEEN {START} AND {START + 70010};")
    A("DELETE FROM sys_user WHERE username LIKE 'demo\\_%';")
    A("")

    # 1. 院系（10）
    A("-- 1. 院系 campus_department（10）")
    for i in range(10):
        A(f"INSERT INTO campus_department (id, dept_name, dept_code, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[0] + i}, '{DEPTS[i]}', 'D{i + 1:02d}', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 2. 班级（10，辅导员关联后面建，先插入班级再 UPDATE counselor）
    A("-- 2. 班级 campus_class（10，辅导员稍后回填）")
    for i in range(10):
        grade = 2023 + (i % 3)
        A(f"INSERT INTO campus_class (id, class_name, class_code, grade, major, department_id, counselor_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[10] + i}, '{CLASSES[i]}', 'C{i + 1:02d}', {grade}, '{MAJORS[i]}', {ID[0] + (i % 10)}, NULL, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 3. 课程（10）
    A("-- 3. 课程 campus_course（10）")
    for i in range(10):
        name, code = COURSES[i]
        A(f"INSERT INTO campus_course (id, course_name, course_code, credit, hours, department_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[20] + i}, '{name}', '{code}', {3.0 if i % 2 else 2.5}, {48 + i * 4}, {ID[0] + (i % 10)}, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 4. 学期（10，仅一条 is_current）
    A("-- 4. 学期 campus_term（10，仅 1 条当前）")
    for i in range(10):
        year = 2021 + i // 2
        term_no = (i % 2) + 1
        is_cur = "1" if i == 8 else "0"  # 2025-2026 第一学期为当前
        A(f"INSERT INTO campus_term (id, term_name, start_date, end_date, total_weeks, is_current, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[30] + i}, '{year}-{year + 1}学年第{['一', '二'][i % 2]}学期', "
          f"'{year}-09-01', '{year + 1}-01-18', 20, '{is_cur}', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 5. 辅导员（v2.4 无专职辅导员）：由教师兼任（demo_t01~10 被班级 counselor_id 指定）

    # 6. 教师 sys_user + campus_teacher（10）
    A("-- 6. 教师 sys_user + campus_teacher（10，role=teacher）")
    for i in range(10):
        uid = 90000 + i  # sys_user id 段（用固定段便于引用）
        A(f"INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, del_flag, role_code, teacher_no, password_version, create_by, create_time, update_by, update_time) "
          f"VALUES ({uid}, 'demo_t{i + 1:02d}', '{TEACHER_NAMES[i]}', '{PWD}', 0, '0', '0', 'teacher', 'T{i + 1:04d}', 0, 1, NOW(), 1, NOW());")
        A(f"INSERT INTO campus_teacher (id, user_id, teacher_no, title, department_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[40] + i}, {uid}, 'T{i + 1:04d}', '{['讲师', '副教授', '教授', '助教'][i % 4]}', {ID[0] + (i % 10)}, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 7. 学生 sys_user + campus_student（10，每班 1 人）
    A("-- 7. 学生 sys_user + campus_student（10，role=student，每班 1 人）")
    for i in range(10):
        uid = 91000 + i
        A(f"INSERT INTO sys_user (id, username, nick_name, password, is_superuser, status, del_flag, role_code, student_no, password_version, create_by, create_time, update_by, update_time) "
          f"VALUES ({uid}, 'demo_s{i + 1:02d}', '{STUDENT_NAMES[i]}', '{PWD}', 0, '0', '0', 'student', 'S{i + 1:08d}', 0, 1, NOW(), 1, NOW());")
        A(f"INSERT INTO campus_student (id, user_id, student_no, class_id, enroll_year, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[50] + i}, {uid}, 'S{i + 1:08d}', {ID[10] + i}, {2023 + (i % 3)}, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 8. 回填班级辅导员（v2.4：教师兼任，班级 i 的辅导员 = demo_t[i%10+1]，每人兼任 1 班 ≤2）
    A("-- 8. 回填班级辅导员（教师兼任 demo_t01~10）")
    for i in range(10):
        A(f"UPDATE campus_class SET counselor_id = {90000 + i} WHERE id = {ID[10] + i};")
    A("")

    # 9. 教学班（10：当前学期 课程×班级×教师）
    A("-- 9. 教学班 campus_course_offering（10，当前学期）")
    for i in range(10):
        tid = 90000 + i
        A(f"INSERT INTO campus_course_offering (id, course_id, term_id, class_id, teacher_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[60] + i}, {ID[20] + i}, {ID[30] + 8}, {ID[10] + i}, {tid}, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 10. 排课（10：每教学班 1 条，时间不冲突）
    A("-- 10. 排课 campus_course_schedule（10，时间不冲突）")
    for i in range(10):
        day = (i % 5) + 1
        ps = (i % 4) * 2 + 1
        A(f"INSERT INTO campus_course_schedule (id, offering_id, week_start, week_end, day_of_week, period_start, period_end, location, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[70] + i}, {ID[60] + i}, 1, 20, {day}, {ps}, {ps + 1}, '教1-{100 + i}室', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 11. 成绩（10：学生×教学班 唯一）
    A("-- 11. 成绩 campus_score（10，发布）")
    for i in range(10):
        usual = 80 + i
        exam = 70 + (i * 3) % 25
        total = round(usual * 0.4 + exam * 0.6, 2)
        A(f"INSERT INTO campus_score (id, student_id, offering_id, usual_score, exam_score, total_score, usual_ratio, exam_ratio, is_published, version, create_by, update_by, update_time, publish_by, publish_time, del_flag) "
          f"VALUES ({ID[80] + i}, {ID[50] + i}, {ID[60] + i}, {usual}.00, {exam}.00, {total}, 40, 60, '1', 0, 1, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 12. 成绩审计（10）
    A("-- 12. 成绩审计 campus_score_audit（10）")
    for i in range(10):
        A(f"INSERT INTO campus_score_audit (id, student_id, offering_id, old_score, new_score, old_detail, new_detail, operator_id, operation, operation_time, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[90] + i}, {ID[50] + i}, {ID[60] + i}, 75.00, {78 + i}.50, JSON_OBJECT('usual',75,'exam',75), JSON_OBJECT('usual',80,'exam',{75 + i}), 90000, '{['2', '1'][i % 2]}', NOW(), 1, NOW(), 1, NOW(), '0');")
    A("")

    # 13. 请假（10：学生提交，状态混合，审批人=兼任教师 id=90000+；事由仿真）
    A("-- 13. 请假 campus_leave（10，状态混合，审批人=兼任教师）")
    for i in range(10):
        status = "1" if i < 5 else ("0" if i < 8 else "2")
        minutes = (i + 1) * 120
        leave_type, reason, comment = LEAVE_DEMOS[i]
        A(f"INSERT INTO campus_leave (id, student_id, leave_type, reason, start_time, end_time, leave_duration_minutes, total_days, status, approver_id, approve_time, approve_comment, version, create_time, create_by, update_by, update_time, del_flag) "
          f"VALUES ({ID[100] + i}, {ID[50] + i}, '{leave_type}', '{reason}（演示数据）', DATE_SUB(NOW(), INTERVAL {i} DAY), DATE_ADD(DATE_SUB(NOW(), INTERVAL {i} DAY), INTERVAL {i + 1} HOUR), {minutes}, {minutes / 60}, '{status}', "
          f"{(90000 + i) if status == '1' else 'NULL'}, {'NOW()' if status == '1' else 'NULL'}, {'\"' + comment + '\"' if status == '1' else 'NULL'}, 0, NOW(), 1, 1, NOW(), '0');")
    A("")

    # 14. 站内消息（10）
    A("-- 14. 站内消息 campus_message（10）")
    for i in range(10):
        msg_content = f"您的请假申请已{'通过' if i < 5 else '驳回'}，事由：{LEAVE_DEMOS[i][1]}（演示数据）"
        A(f"INSERT INTO campus_message (id, user_id, msg_type, title, content, business_type, business_id, is_read, read_time, create_time, create_by, update_by, update_time, del_flag) "
          f"VALUES ({ID[110] + i}, {91000 + i}, '1', '请假审批结果', '{msg_content}', 'leave', {ID[100] + i}, '{'0' if i % 2 else '1'}', {'NOW()' if i % 2 else 'NULL'}, NOW(), 1, 1, NOW(), '0');")
    A("")

    # 15. 文件（10）
    A("-- 15. 文件 campus_file（10）")
    for i in range(10):
        A(f"INSERT INTO campus_file (id, original_name, stored_name, mime_type, file_size, storage_path, file_hash, uploader_id, owner_id, biz_type, biz_id, visibility, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[120] + i}, 'demo_{i + 1}.jpg', 'demo-{i + 1:08x}', 'image/jpeg', {1024 + i * 100}, 'uploads/demo/demo_{i + 1}.jpg', '{hashlib.sha256(f'demo{i}'.encode()).hexdigest()}', 91000, {91000 + i}, '{['avatar', 'leave_attachment'][i % 2]}', {ID[100] + i}, '2', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 16. 知识库（10，仿真内容：覆盖师资/宿舍/食堂/制度/招生/设施/其他 7 类；content_hash 按正文实时计算，P0-09）
    A("-- 16. 知识库 campus_knowledge（10，仿真内容；content_hash=SHA-256(正文)）")
    for i in range(10):
        k_title, k_cat, k_content, k_tags = KNOWLEDGE_DOCS[i]
        k_hash = hashlib.sha256(k_content.encode()).hexdigest()
        A(f"INSERT INTO campus_knowledge (id, title, category, content, tags, content_hash, status, publisher_id, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[0] + i + 20000}, '{k_title}', '{k_cat}', '{k_content}', '{k_tags}', '{k_hash}', '{'1' if i < 7 else '0'}', 1, 1, NOW(), 1, NOW(), '0');")
    A("")

    # 17. RAG 分片（10，取公告/知识库正文片段；来源对齐：偶数位→公告 70000+i//2，奇数位→知识库 20000+i//2）
    A("-- 17. RAG 分片 campus_rag_chunk（10，来源对齐公告/知识库正文片段）")
    for i in range(10):
        if i % 2 == 0:
            src_type, src_id = "1", ID[0] + i // 2 + 70000
            title = ANNOUNCEMENTS[i // 2][0]
            content = ANNOUNCEMENTS[i // 2][1][:100] + "……"
        else:
            src_type, src_id = "2", ID[0] + i // 2 + 20000
            title = KNOWLEDGE_DOCS[i // 2][0]
            content = KNOWLEDGE_DOCS[i // 2][2][:100] + "……"
        A(f"INSERT INTO campus_rag_chunk (id, source_type, source_id, source_version, chunk_index, content, title, url, status, create_by, create_time, update_by, update_time, del_flag) "
          f"VALUES ({ID[0] + i + 30000}, '{src_type}', {src_id}, 1, 0, '{content}', '{title}', '', '1', 1, NOW(), 1, NOW(), '0');")
    A("")

    # 18. RAG 问答日志（10；v2.6/8.4.1：含 refuse_reason；前 7 条真实校园问答，末 3 条演示三类拒答）
    A("-- 18. RAG 日志 campus_rag_log（10，v2.6 含 refuse_reason；末 3 条为拒答演示）")
    refuse_demo = {
        7: ("帮我写一首关于秋天的诗？", "抱歉，我只能回答与本校校园信息相关的问题～", "out_of_scope"),
        8: "学校附近哪家股票值得买？",
        9: "帮我查一下某某同学的手机号？",
    }
    for i in range(10):
        if i in refuse_demo and isinstance(refuse_demo[i], tuple):
            question, answer, reason = refuse_demo[i]
            ref_ids, hit_count, pt, ct, model = "", 0, 0, 0, "NULL"  # 拒答路径不调用 LLM（8.4.1）
        elif i == 8:
            question, answer, reason = refuse_demo[8], "暂时没有找到相关资料，建议查看校园公告或咨询教务处", "no_context"
            ref_ids, hit_count, pt, ct, model = "", 0, 0, 0, "NULL"
        elif i == 9:
            question, answer, reason = refuse_demo[9], "这个问题我无法回答，换个校园相关的问题试试吧", "unsafe"
            ref_ids, hit_count, pt, ct, model = "", 0, 0, 0, "NULL"
        else:
            question, answer, refs = RAG_QA[i]
            ref_ids = ",".join(refs)
            hit_count = len(refs)
            pt, ct, model = 900 + i * 120, 180 + i * 45, "'deepseek-chat'"
            reason = None
        reason_sql = "NULL" if reason is None else f"'{reason}'"
        A(f"INSERT INTO campus_rag_log (id, session_id, question, answer, ref_ids, hit_count, model, prompt_tokens, completion_tokens, cost_time_ms, ip, feedback, refuse_reason, create_time, create_by, update_by, update_time, del_flag) "
          f"VALUES ({ID[0] + i + 40000}, 'demo-sess-{i}', '{question}', '{answer}', '{ref_ids}', {hit_count}, {model}, {pt}, {ct}, {380 + i * 65}, '192.168.0.100', '{'0' if i % 3 else '1'}', {reason_sql}, NOW(), 1, 1, NOW(), '0');")
    A("")

    # 19. RAG 任务（10，来源与分片对齐：operation upsert=发布链路产物；前 6 条 SUCCESS，其余 PENDING）
    A("-- 19. RAG 任务 campus_rag_task（10，来源与分片对齐）")
    for i in range(10):
        if i % 2 == 0:
            src_type, src_id = "1", ID[0] + i // 2 + 70000
        else:
            src_type, src_id = "2", ID[0] + i // 2 + 20000
        status = "2" if i < 6 else "0"
        A(f"INSERT INTO campus_rag_task (id, operation, source_type, source_id, status, retry_count, next_retry_time, last_error, create_time, update_time, del_flag) "
          f"VALUES ({ID[0] + i + 50000}, '1', '{src_type}', {src_id}, '{status}', 0, NULL, NULL, NOW(), NOW(), '0');")
    A("")

    # 20. 幂等记录（10）
    A("-- 20. 幂等记录 campus_idempotency_key（10）")
    for i in range(10):
        A(f"INSERT INTO campus_idempotency_key (id, biz_key, user_id, method, path, body_hash, response_code, response_body, expire_time, create_time, del_flag) "
          f"VALUES ({ID[0] + i + 60000}, 'demo-biz-{i}', {91000 + i}, 'POST', '/api/demo', '{hashlib.sha256(f'b{i}'.encode()).hexdigest()}', 0, JSON_OBJECT('code',0,'msg','ok'), DATE_ADD(NOW(), INTERVAL 24 HOUR), NOW(), '0');")
    A("")

    # 21. 公告（10，仿真内容：招生/报到/宿舍/食堂/奖学金/教师招聘/课程设计/竞赛/校车/图书馆）
    # v2.5/ADR-011：移除班级公告类型——ann_type 仅 1校园/2院系，target_class_id 列已随 DDL 删除
    # 状态/置顶：i0~i4 发布（i0/i1 置顶），i5~i7 草稿，i8~i9 下架
    A("-- 21. 公告 campus_announcement（10，仿真内容；v2.5 ann_type 仅 1校园/2院系）")
    for i in range(10):
        a_title, a_content, ann_type, dept_off = ANNOUNCEMENTS[i]
        status = "1" if i < 5 else ("0" if i < 8 else "2")
        is_top = "1" if i < 2 else "0"
        target_dept = str(ID[0] + dept_off) if dept_off is not None else "NULL"
        A(f"INSERT INTO campus_announcement (id, title, content, ann_type, target_department_id, publisher_id, is_top, status, publish_time, create_time, update_time, create_by, update_by, del_flag) "
          f"VALUES ({ID[0] + i + 70000}, '{a_title}', '{a_content}', '{ann_type}', {target_dept}, 1, '{is_top}', '{status}', "
          f"{'DATE_SUB(NOW(), INTERVAL ' + str(i + 1) + ' DAY)' if status == '1' else 'NULL'}, NOW(), NOW(), 1, 1, '0');")
    A("")

    A("SET FOREIGN_KEY_CHECKS = 1;")
    A("-- ============================================================")
    A("-- 演示数据生成完成（20 张表各 >= 10 条）。")
    A("-- 登录账号：demo_s01~10（学生）/ demo_t01~10（教师兼任辅导员），密码 123456")
    A("-- ============================================================")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(sql) + "\n")
    print(f"已生成: {OUT}（{len(sql)} 行）")


if __name__ == "__main__":
    main()
