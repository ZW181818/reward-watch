from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from PIL import Image

from .wordpress import clean_text


SOURCE_NAME = "泉州市公安局"
MEDIA_DIR = Path(__file__).resolve().parents[2] / "data" / "media" / "china-police"
MEDIA_URL_PREFIX = "/media/china-police"
USER_AGENT = "RewardWatchMVP0/0.1 (+official-source-research)"
SAFETY_WARNING = "请勿自行接近或实施抓捕。请直接通过官方通告所列渠道向公安机关提供线索。"
_NOTICE_CLOSED_MARKERS = (
    "撤销悬赏",
    "撤销通告",
    "终止悬赏",
    "停止悬赏",
)
_SUBJECT_CLOSED_MARKERS = (
    "已抓获",
    "抓获归案",
    "投案自首",
)


@dataclass(frozen=True)
class ChinaPoliceSubject:
    case_id: str
    name: str
    aliases: tuple[str, ...]
    sex: str
    portrait_box: tuple[int, int, int, int]
    summary: str | None = None


@dataclass(frozen=True)
class ChinaPoliceNotice:
    notice_id: str
    source_url: str
    source_title: str
    source_author: str
    source_published_date: str
    published_date: str
    poster_filename: str
    region: str
    field_office: str
    case_type: str
    reward: int
    reward_text: str
    expected_poster_sha256: str
    subjects: tuple[ChinaPoliceSubject, ...]
    source_encoding: str = "utf-8"


QUANZHOU_2025_NOTICE = ChinaPoliceNotice(
    notice_id="quanzhou-20251113",
    source_url=(
        "https://gaj.quanzhou.gov.cn/jwzx/gayw/202511/"
        "t20251113_3230264.htm"
    ),
    source_title="悬赏通告",
    source_author=SOURCE_NAME,
    source_published_date="2025-11-13",
    published_date="2025-11-13",
    poster_filename="W020251113318965478061.jpg",
    region="福建省",
    field_office="福建省泉州市",
    case_type="涉嫌煽动分裂国家罪",
    reward=250_000,
    reward_text="对提供有效线索或配合抓获有关犯罪嫌疑人的有功人员，视情给予5万至25万元人民币的奖励。",
    expected_poster_sha256=(
        "480e2e806306129827ae81a3b639bb5a8dab6fa809c965bc352135c6d8468d24"
    ),
    subjects=(
        ChinaPoliceSubject(
            case_id="cn-police-qz-20251113-wen-ziyu",
            name="温子渝",
            aliases=("八炯",),
            sex="男",
            portrait_box=(833, 587, 1383, 1166),
            summary=(
                "泉州市公安局通告称，温子渝长期在境外社交平台发布、传播相关言论，"
                "其行为涉嫌煽动分裂国家罪。公安机关公开征集线索，并对提供有效线索"
                "或协助抓获的有功人员给予5万至25万元人民币奖励。"
            ),
        ),
        ChinaPoliceSubject(
            case_id="cn-police-qz-20251113-chen-baiyuan",
            name="陈柏源",
            aliases=("闽南狼",),
            sex="男",
            portrait_box=(1568, 587, 2118, 1167),
            summary=(
                "泉州市公安局通告称，陈柏源长期在境外社交平台发布、传播相关言论，"
                "其行为涉嫌煽动分裂国家罪。公安机关公开征集线索，并对提供有效线索"
                "或协助抓获的有功人员给予5万至25万元人民币奖励。"
            ),
        ),
    ),
)


MPS_100_SOURCE_URL = (
    "https://gaj.wuhan.gov.cn/jmzx/gayw/202512/"
    "t20251210_2692759.html"
)
MPS_100_SOURCE_TITLE = "公安机关公开通缉100名电信网络诈骗犯罪在逃金主和骨干人员"
MPS_100_REWARD_TEXT = (
    "对向公安机关提供有效线索并配合抓获犯罪嫌疑人的有功人员，"
    "给予20万元人民币奖励。"
)


def _reviewed_subjects(
    case_prefix: str,
    subjects: tuple[tuple[str, str, str, tuple[int, int, int, int]], ...],
) -> tuple[ChinaPoliceSubject, ...]:
    return tuple(
        ChinaPoliceSubject(
            case_id=f"{case_prefix}-{slug}",
            name=name,
            aliases=(),
            sex=sex,
            portrait_box=portrait_box,
        )
        for slug, name, sex, portrait_box in subjects
    )


def _mps_subjects(
    prefix: str,
    subjects: tuple[tuple[str, str, str, tuple[int, int, int, int]], ...],
) -> tuple[ChinaPoliceSubject, ...]:
    return _reviewed_subjects(
        f"cn-police-mps-20251209-{prefix}",
        subjects,
    )


def _mps_notice(
    *,
    notice_id: str,
    poster_filename: str,
    source_author: str,
    region: str,
    field_office: str,
    expected_poster_sha256: str,
    subjects: tuple[ChinaPoliceSubject, ...],
    source_url: str = MPS_100_SOURCE_URL,
    source_published_date: str = "2025-12-10 09:41",
    source_encoding: str = "utf-8",
) -> ChinaPoliceNotice:
    return ChinaPoliceNotice(
        notice_id=notice_id,
        source_url=source_url,
        source_title=MPS_100_SOURCE_TITLE,
        source_author=source_author,
        source_published_date=source_published_date,
        published_date="2025-12-09",
        poster_filename=poster_filename,
        region=region,
        field_office=field_office,
        case_type="电信网络诈骗犯罪",
        reward=200_000,
        reward_text=MPS_100_REWARD_TEXT,
        expected_poster_sha256=expected_poster_sha256,
        subjects=subjects,
        source_encoding=source_encoding,
    )


MPS_HANGZHOU_2025_NOTICE = _mps_notice(
    notice_id="mps-20251209-hangzhou",
    poster_filename="W020251210350394014512_ORIGIN.jpg",
    source_author="杭州市公安局",
    region="浙江省",
    field_office="浙江省杭州市",
    expected_poster_sha256=(
        "516f30273748ad044f6bd4084a17fd9692db22b154bbcce8785628a9d419a97c"
    ),
    subjects=_mps_subjects(
        "hz",
        (
            ("wu-qiping", "吴启平", "男", (94, 171, 171, 273)),
            ("lan-xiantan", "兰先谈", "男", (203, 171, 280, 273)),
            ("lan-chaohui", "兰朝辉", "男", (314, 171, 391, 273)),
            ("wen-renxuan", "温仁煊", "男", (423, 171, 500, 273)),
        ),
    ),
)

MPS_KUNMING_2025_NOTICE = _mps_notice(
    notice_id="mps-20251209-kunming",
    poster_filename="W020251210350394527633_ORIGIN.jpg",
    source_author="昆明市公安局",
    region="云南省",
    field_office="云南省昆明市",
    expected_poster_sha256=(
        "1ad5f5ae4f648210059759d862c51f4f9d01715a3c45c0f547576e7173abfe17"
    ),
    subjects=_mps_subjects(
        "km",
        (
            ("chen-yanrong", "陈炎荣", "男", (94, 171, 172, 273)),
            ("chen-yili", "陈以利", "男", (262, 171, 339, 273)),
            ("xu-xinwu", "许信武", "男", (432, 171, 509, 273)),
        ),
    ),
)

MPS_LONGYAN_2025_NOTICE = _mps_notice(
    notice_id="mps-20251209-longyan",
    poster_filename=(
        "20251209a2fd5c51f8b640e089af8ebe69cbcbb7_"
        "2025120984181df17c314c9d90b978529c4ea402.jpg"
    ),
    source_author="龙岩市公安局",
    region="福建省",
    field_office="福建省龙岩市",
    expected_poster_sha256=(
        "8b7d798b1371497a2abb2a63df9366b796f450c4e21380337e66a080214a391e"
    ),
    source_url=(
        "https://www.news.cn/legal/20251209/"
        "a2fd5c51f8b640e089af8ebe69cbcbb7/c.html"
    ),
    source_published_date="2025-12-09",
    subjects=_mps_subjects(
        "ly",
        (
            ("liu-jiguang", "刘积光", "男", (76, 224, 209, 408)),
            ("zhang-zhongcheng", "张忠诚", "男", (261, 224, 394, 408)),
            ("ou-changhua", "欧长华", "男", (448, 224, 581, 408)),
            ("ou-changlong", "欧长龙", "男", (635, 224, 768, 408)),
            ("xue-zhengjun", "薛政军", "男", (819, 224, 952, 408)),
            ("zhang-zerui", "张泽锐", "男", (76, 531, 209, 715)),
            ("ma-zhiwei", "马智威", "男", (261, 531, 394, 715)),
            ("xu-zaijun", "许在俊", "男", (448, 531, 581, 715)),
            ("xiang-hongsheng", "向红升", "男", (635, 531, 768, 715)),
            ("gu-lei", "辜磊", "男", (819, 531, 952, 715)),
            ("zhang-wen", "张文", "男", (76, 842, 209, 1025)),
            ("zhang-baoshun", "张宝顺", "男", (261, 842, 394, 1025)),
            ("tang-wenqiang", "汤文强", "男", (448, 842, 581, 1025)),
            ("lin-jiachen", "林嘉宸", "男", (635, 842, 768, 1025)),
            ("wang-wenchang", "王文昌", "男", (819, 842, 952, 1025)),
            ("wang-mian", "汪冕", "男", (76, 1170, 209, 1352)),
            ("liu-rugui", "刘如贵", "男", (261, 1170, 394, 1352)),
            ("liu-wei", "刘伟", "男", (448, 1170, 581, 1352)),
            ("jiang-jingwen", "蒋景文", "男", (635, 1170, 768, 1352)),
            ("lin-hailong", "林海龙", "男", (819, 1170, 952, 1352)),
            ("su-fuquan", "苏福全", "男", (76, 1487, 209, 1671)),
            ("chen-qilong", "陈其龙", "男", (261, 1487, 394, 1671)),
            ("jiang-xialu", "蒋夏露", "男", (448, 1487, 581, 1671)),
            ("liao-jianquan", "廖键权", "男", (635, 1487, 768, 1671)),
            ("qiao-ying", "乔莹", "女", (819, 1487, 952, 1671)),
            ("zhang-wei", "张伟", "男", (76, 1806, 209, 1989)),
            ("diao-junlin", "刁俊林", "男", (261, 1806, 394, 1989)),
            ("diao-junqiang", "刁俊强", "男", (448, 1806, 581, 1989)),
            ("ning-min", "宁敏", "女", (635, 1806, 768, 1989)),
            ("liu-jun", "刘俊", "男", (819, 1806, 952, 1989)),
            ("luo-zhen", "罗振", "男", (76, 2125, 209, 2309)),
            ("zou-weilong", "邹威龙", "男", (261, 2125, 394, 2309)),
            ("jiang-junting", "蒋骏烃", "男", (448, 2125, 581, 2309)),
            ("xue-hao", "薛浩", "男", (635, 2125, 768, 2309)),
            ("jiang-shiqi", "江世其", "男", (819, 2125, 952, 2309)),
            ("wu-yanbing", "吴艳兵", "男", (76, 2446, 209, 2629)),
            ("xu-xiaoman", "徐小曼", "女", (261, 2446, 394, 2629)),
            ("zhang-meiyu", "张美玉", "女", (448, 2446, 581, 2629)),
            ("chen-dejun", "陈德军", "男", (635, 2446, 768, 2629)),
            ("yu-kuanxiang", "于宽相", "男", (819, 2446, 952, 2629)),
            ("liu-yong", "刘勇", "男", (76, 2763, 209, 2945)),
            ("lin-shuangqing", "林双庆", "男", (261, 2763, 394, 2945)),
            ("liu-yuanxiang", "刘远香", "女", (448, 2763, 581, 2945)),
        ),
    ),
)

MPS_QUANZHOU_2025_NOTICE = _mps_notice(
    notice_id="mps-20251209-quanzhou",
    poster_filename="W020251210350395855099_ORIGIN.jpg",
    source_author="泉州市公安局",
    region="福建省",
    field_office="福建省泉州市",
    expected_poster_sha256=(
        "d6234862e50f11e0ba293bbfae73b3a1e7c6fcb21f6111d4a55b5fd5038b9a27"
    ),
    subjects=_mps_subjects(
        "qz",
        (
            ("zhang-dehui", "张德会", "男", (42, 113, 120, 214)),
            ("zhang-jun", "张俊", "男", (153, 113, 231, 214)),
            ("wang-xiaoling", "王晓玲", "男", (262, 113, 340, 214)),
            ("hu-lei", "胡磊", "男", (372, 113, 450, 214)),
            ("chen-jiyue", "陈基跃", "男", (479, 113, 557, 214)),
            ("qiu-bin", "邱斌", "男", (42, 283, 120, 383)),
            ("wang-fang", "王芳", "女", (153, 283, 231, 383)),
            ("wang-wen", "王文", "男", (262, 283, 340, 383)),
            ("bian-zhouzhou", "卞洲洲", "男", (372, 283, 450, 383)),
            ("zeng-zhiping", "曾志平", "男", (479, 283, 557, 383)),
            ("chen-fangyan", "陈方艳", "女", (42, 454, 120, 555)),
        ),
    ),
)

MPS_SHENZHEN_2025_NOTICE = _mps_notice(
    notice_id="mps-20251209-shenzhen",
    poster_filename="W020251210350396368493_ORIGIN.jpg",
    source_author="深圳市公安局",
    region="广东省",
    field_office="广东省深圳市",
    expected_poster_sha256=(
        "e64eae4c8a7bbb386d1ba6ead02403b43c6451f67f6bfecb85476606e9731b2e"
    ),
    subjects=_mps_subjects(
        "sz",
        (
            ("bai-yingneng", "白应能", "男", (42, 125, 120, 226)),
            ("feng-zuxiong", "冯祖雄", "男", (155, 125, 233, 226)),
            ("yang-zaijun", "杨再军", "男", (264, 125, 342, 226)),
            ("huang-hongkun", "黄虹昆", "男", (372, 125, 450, 226)),
            ("lin-changchun", "林长春", "男", (479, 125, 557, 226)),
            ("xu-zhihong", "徐志洪", "男", (42, 296, 120, 397)),
            ("bai-yingxiang", "白应香", "女", (155, 296, 233, 397)),
            ("bai-yinglan", "白应兰", "女", (264, 296, 342, 397)),
            ("bai-yingping", "白应萍", "女", (372, 296, 450, 397)),
            ("bai-yinggai", "白应改", "女", (479, 296, 557, 397)),
            ("lu-jianjiao", "鲁健娇", "女", (42, 468, 120, 570)),
            ("cao-qiangli", "曹强力", "男", (155, 468, 233, 570)),
            ("luo-wenyun", "罗文筠", "男", (264, 468, 342, 570)),
            ("liu-hualong", "刘华龙", "男", (372, 468, 450, 570)),
            ("yang-zaihua", "杨再华", "男", (479, 468, 557, 570)),
            ("fang-mei", "方梅", "男", (42, 649, 120, 753)),
            ("zhong-jianhong", "钟建鸿", "男", (155, 649, 233, 753)),
            ("xiao-jiwei", "肖基伟", "男", (264, 649, 342, 753)),
        ),
    ),
)

MPS_WENZHOU_2025_NOTICE = _mps_notice(
    notice_id="mps-20251209-wenzhou",
    poster_filename="W020251210350396782435_ORIGIN.jpg",
    source_author="温州市公安局",
    region="浙江省",
    field_office="浙江省温州市",
    expected_poster_sha256=(
        "89a8f6460b0bda8c3237de545d8302ae9b9aed143594e1daef033fa4503c8310"
    ),
    subjects=_mps_subjects(
        "wz",
        (
            ("chen-zhichang", "陈志昌", "男", (42, 111, 120, 213)),
            ("fu-xiaobin", "傅小滨", "男", (153, 111, 231, 213)),
            ("liu-mouyue", "刘谋跃", "男", (262, 111, 340, 213)),
            ("zhang-weishou", "张伟寿", "男", (372, 111, 450, 213)),
            ("wu-weiyu", "吴伟毓", "男", (479, 111, 557, 213)),
            ("fu-xiaobing", "傅晓冰", "男", (42, 281, 120, 383)),
            ("zhang-canxin", "张灿鑫", "男", (153, 281, 231, 383)),
            ("lin-zhichao", "林志超", "男", (262, 281, 340, 383)),
        ),
    ),
)

MPS_CHONGQING_2025_NOTICE = _mps_notice(
    notice_id="mps-20251209-chongqing",
    poster_filename="W020251210350397326650_ORIGIN.jpg",
    source_author="重庆市公安局",
    region="重庆市",
    field_office="重庆市",
    expected_poster_sha256=(
        "d4fb974a5234152899c3b6e87f9d92aa9060f198161c5a40e3be9734e9648f30"
    ),
    subjects=_mps_subjects(
        "cq",
        (
            ("wu-qingzheng", "吴清正", "男", (42, 119, 120, 220)),
            ("zhang-xingjin", "张星金", "男", (153, 119, 231, 220)),
            ("lian-linfeng", "连林锋", "男", (262, 119, 340, 220)),
            ("lin-tiangui", "林天贵", "男", (372, 119, 450, 220)),
            ("wu-wenbiao", "吴文飚", "男", (479, 119, 557, 220)),
            ("hong-guofu", "洪国富", "男", (42, 290, 120, 392)),
            ("chen-yuanhui", "陈元辉", "男", (153, 290, 231, 392)),
            ("wang-wei", "王伟", "男", (262, 290, 340, 392)),
            ("wu-zhihua", "吴志华", "男", (372, 290, 450, 392)),
            ("lian-wenchao", "连文超", "男", (479, 290, 557, 392)),
            ("li-wenhai", "李文海", "男", (42, 462, 120, 564)),
            ("song-shuaifei", "宋帅飞", "男", (153, 462, 231, 564)),
        ),
    ),
)

MPS_PINGDINGSHAN_2025_NOTICE = _mps_notice(
    notice_id="mps-20251209-pingdingshan",
    poster_filename="W020251210350397937714_ORIGIN.jpg",
    source_author="平顶山市公安局",
    region="河南省",
    field_office="河南省平顶山市",
    expected_poster_sha256=(
        "0f0c18ea81acdf669cda3d687bb75efdb693630d911fdb85e004bb1c153ddace"
    ),
    subjects=_mps_subjects(
        "pds",
        (("zhang-yonghui", "张永辉", "男", (247, 130, 353, 268)),),
    ),
)

GUANGZHOU_CYBER_2025_NOTICE = ChinaPoliceNotice(
    notice_id="guangzhou-cyber-20250605",
    source_url=(
        "https://www.gwytb.gov.cn/bmst/202506/"
        "t20250605_12704843.htm"
    ),
    source_title='公安机关依法公开通缉台湾"资通电军"重要犯罪嫌疑人',
    source_author="广州市公安局天河区分局",
    source_published_date="2025-06-05 15:08",
    published_date="2025-06-05",
    poster_filename="W020250605553896899888.jpg",
    region="广东省",
    field_office="广东省广州市天河区",
    case_type="涉嫌非法控制、破坏计算机信息系统犯罪",
    reward=10_000,
    reward_text=(
        "对向公安机关提供有效线索，以及配合公安机关抓获有关犯罪嫌疑人的"
        "有功人员，按每名犯罪嫌疑人1万元人民币予以奖励。"
    ),
    expected_poster_sha256=(
        "4e6fe029370e86c3594b1dfc3044e5de7871bf6fe7b2afde88f3902cbe8c1613"
    ),
    subjects=_reviewed_subjects(
        "cn-police-gz-20250605",
        (
            ("ning-enwei", "宁恩纬", "男", (46, 188, 174, 330)),
            ("liu-guanjun", "刘冠均", "男", (191, 188, 320, 330)),
            ("huang-shiheng", "黄士恒", "男", (337, 188, 465, 330)),
            ("jiang-zhixue", "江致学", "男", (483, 188, 611, 330)),
            ("peng-yixuan", "彭依宣", "男", (628, 188, 757, 330)),
            ("gong-jingyi", "龚景翊", "男", (46, 427, 174, 569)),
            ("xiao-zhihao", "萧智豪", "男", (191, 427, 320, 569)),
            ("chen-qixiu", "陈齐修", "男", (337, 427, 465, 569)),
            ("huang-gangzheng", "黄纲正", "男", (483, 427, 611, 569)),
            ("lin-huangqi", "林煌锜", "男", (628, 427, 757, 569)),
            ("chen-juyi", "陈居亿", "男", (46, 665, 174, 807)),
            ("chen-yanying", "陈燕莹", "女", (191, 665, 320, 807)),
            ("hong-jianzhi", "洪健智", "男", (337, 665, 465, 807)),
            ("chen-yiwen", "陈艺文", "男", (483, 665, 611, 807)),
            ("huang-songwei", "黄嵩玮", "男", (628, 665, 757, 807)),
            ("chen-mingting", "陈铭庭", "男", (46, 904, 174, 1046)),
            ("cheng-yudian", "成育典", "男", (191, 904, 320, 1046)),
            ("shen-xiaoxuan", "沈曉璇", "男", (337, 904, 465, 1046)),
            ("zhang-jingzhi", "张景智", "男", (483, 904, 611, 1046)),
            ("wu-naige", "吴乃戈", "男", (628, 904, 757, 1046)),
        ),
    ),
    source_encoding="gb18030",
)


CHINA_POLICE_NOTICES = (
    QUANZHOU_2025_NOTICE,
    MPS_HANGZHOU_2025_NOTICE,
    MPS_KUNMING_2025_NOTICE,
    MPS_LONGYAN_2025_NOTICE,
    MPS_QUANZHOU_2025_NOTICE,
    MPS_SHENZHEN_2025_NOTICE,
    MPS_WENZHOU_2025_NOTICE,
    MPS_CHONGQING_2025_NOTICE,
    MPS_PINGDINGSHAN_2025_NOTICE,
    GUANGZHOU_CYBER_2025_NOTICE,
)


def fetch_china_police_reward_cases(
    limit: int | None = None,
    *,
    media_dir: Path = MEDIA_DIR,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    page_cache: dict[str, str] = {}
    poster_cache: dict[str, bytes] = {}
    for notice in CHINA_POLICE_NOTICES:
        if notice.source_url not in page_cache:
            page_cache[notice.source_url] = _fetch_bytes(notice.source_url).decode(
                notice.source_encoding, "replace"
            )
        page_html = page_cache[notice.source_url]
        poster_url = discover_notice_poster_url(
            page_html,
            notice.source_url,
            expected_filename=notice.poster_filename,
        )
        if poster_url not in poster_cache:
            poster_cache[poster_url] = _fetch_bytes(poster_url)
        poster_bytes = poster_cache[poster_url]
        image_urls = _cache_verified_notice_images(
            notice,
            poster_bytes,
            media_dir=media_dir,
        )
        cases.extend(
            parse_china_police_notice(
                page_html,
                notice=notice,
                image_urls=image_urls,
            )
        )

    cases.sort(key=lambda item: (item["publishedDate"], item["title"]), reverse=True)
    return cases[:limit] if limit else cases


def discover_notice_poster_url(
    page_html: str,
    source_url: str,
    *,
    expected_filename: str | None = None,
) -> str:
    soup = BeautifulSoup(page_html, "html.parser")
    images = soup.select(
        ".TRS_Editor img[src], .trs_editor_view img[src], #detailContent img[src]"
    )
    image = next(
        (
            candidate
            for candidate in images
            if not expected_filename
            or Path(urlsplit(clean_text(candidate.get("src"))).path).name
            == expected_filename
        ),
        None,
    )
    if not image:
        expected = f" {expected_filename}" if expected_filename else ""
        raise ValueError(
            f"official police notice does not contain reviewed poster{expected}"
        )

    poster_url = urljoin(source_url, clean_text(image.get("src")))
    source_host = (urlsplit(source_url).hostname or "").lower()
    poster_host = (urlsplit(poster_url).hostname or "").lower()
    if not poster_url or poster_host != source_host:
        raise ValueError("official police poster is not hosted on the issuing website")
    return poster_url


def parse_china_police_notice(
    page_html: str,
    *,
    notice: ChinaPoliceNotice,
    image_urls: dict[str, list[str]],
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(page_html, "html.parser")
    title = _meta_content(soup, "ArticleTitle") or _first_text(soup, "h1")
    published_date = _meta_content(soup, "PubDate") or _meta_content(
        soup, "publishdate"
    )
    page_text = clean_text(soup.get_text(" ", strip=True))
    if not published_date and notice.source_published_date in page_text:
        published_date = notice.source_published_date

    if title != notice.source_title:
        raise ValueError(
            f"official police notice title changed: expected {notice.source_title!r}, got {title!r}"
        )
    if published_date != notice.source_published_date:
        raise ValueError(
            "official police notice publication date changed: "
            f"expected {notice.source_published_date!r}, got {published_date!r}"
        )
    if any(marker in page_text for marker in _NOTICE_CLOSED_MARKERS):
        return []
    if any(not image_urls.get(subject.case_id) for subject in notice.subjects):
        raise ValueError("official police notice has no verified subject image")

    last_verified = datetime.now(UTC).date().isoformat()
    return [
        {
            "id": subject.case_id,
            "title": subject.name,
            "agency": notice.source_author,
            "country": "China",
            "regions": [notice.region],
            "caseType": notice.case_type,
            "description": f"{notice.case_type}（以公安机关原始通告为准）",
            "reward": notice.reward,
            "rewardCurrency": "CNY",
            "rewardText": notice.reward_text,
            "status": "Open",
            "summary": subject.summary or _default_subject_summary(notice, subject),
            "warningMessage": SAFETY_WARNING,
            "aliases": list(subject.aliases),
            "age": None,
            "dateOfBirth": None,
            "placeOfBirth": None,
            "sex": subject.sex,
            "race": None,
            "nationality": None,
            "hair": None,
            "eyes": None,
            "height": None,
            "weight": None,
            "locations": None,
            "distinguishingFeatures": None,
            "fieldOffice": notice.field_office,
            "publishedDate": notice.published_date,
            "lastVerified": last_verified,
            "sourceUpdatedDate": notice.source_published_date[:10],
            "sourceUrl": notice.source_url,
            "sourceTitle": notice.source_title,
            "sourceAuthor": notice.source_author,
            "sourceKind": "official",
            "imageUrl": image_urls[subject.case_id][0],
            "imageUrls": image_urls[subject.case_id],
        }
        for subject in notice.subjects
        if not _subject_is_closed(page_text, subject.name)
    ]


def _default_subject_summary(
    notice: ChinaPoliceNotice,
    subject: ChinaPoliceSubject,
) -> str:
    if notice.case_type != "电信网络诈骗犯罪":
        return (
            f"{notice.source_author}发布的悬赏通告将{subject.name}列为"
            f"{notice.case_type}相关犯罪嫌疑人，公安机关公开征集有效线索及"
            f"协助抓获信息。{notice.reward_text}案件信息及人员状态以公安机关"
            "最新通告为准。"
        )
    return (
        f"{notice.source_author}发布的悬赏通告将{subject.name}列为在逃电信网络诈骗犯罪"
        "‘金主’或骨干人员，公安机关公开征集协助抓获的有效线索；"
        "通告对有功人员给予20万元人民币奖励。案件信息及人员状态以公安机关"
        "最新通告为准。"
    )


def _subject_is_closed(page_text: str, subject_name: str) -> bool:
    start = 0
    while True:
        name_index = page_text.find(subject_name, start)
        if name_index < 0:
            return False
        context = page_text[
            max(0, name_index - 24) : name_index + len(subject_name) + 24
        ]
        if any(marker in context for marker in _SUBJECT_CLOSED_MARKERS):
            return True
        start = name_index + len(subject_name)


def _cache_verified_notice_images(
    notice: ChinaPoliceNotice,
    poster_bytes: bytes,
    *,
    media_dir: Path,
    media_url_prefix: str = MEDIA_URL_PREFIX,
) -> dict[str, list[str]]:
    poster_url = _cache_verified_poster(
        notice,
        poster_bytes,
        media_dir=media_dir,
        media_url_prefix=media_url_prefix,
    )

    with Image.open(BytesIO(poster_bytes)) as poster:
        poster.load()
        subject_images: dict[str, list[str]] = {}
        for subject in notice.subjects:
            left, top, right, bottom = subject.portrait_box
            if left < 0 or top < 0 or right > poster.width or bottom > poster.height:
                raise ValueError(
                    f"reviewed portrait crop is outside the poster for {subject.case_id}"
                )
            portrait = poster.crop(subject.portrait_box).convert("RGB")
            buffer = BytesIO()
            portrait.save(buffer, format="JPEG", quality=92, optimize=True)
            filename = f"{subject.case_id}-portrait.jpg"
            _write_bytes_atomic(media_dir / filename, buffer.getvalue())
            portrait_url = f"{media_url_prefix.rstrip('/')}/{filename}"
            subject_images[subject.case_id] = [portrait_url, poster_url]
    return subject_images


def _cache_verified_poster(
    notice: ChinaPoliceNotice,
    poster_bytes: bytes,
    *,
    media_dir: Path,
    media_url_prefix: str = MEDIA_URL_PREFIX,
) -> str:
    digest = hashlib.sha256(poster_bytes).hexdigest()
    if digest != notice.expected_poster_sha256:
        raise ValueError(
            f"official police poster changed for {notice.notice_id}; manual review required"
        )
    if not poster_bytes.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")):
        raise ValueError("official police poster is not a supported image")

    extension = ".png" if poster_bytes.startswith(b"\x89PNG") else ".jpg"
    filename = f"{notice.notice_id}-poster{extension}"
    media_dir.mkdir(parents=True, exist_ok=True)
    _write_bytes_atomic(media_dir / filename, poster_bytes)
    return f"{media_url_prefix.rstrip('/')}/{filename}"


def _write_bytes_atomic(target: Path, payload: bytes) -> None:
    if target.exists() and target.read_bytes() == payload:
        return
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(target)


def _meta_content(soup: BeautifulSoup, name: str) -> str:
    node = soup.find("meta", attrs={"name": name})
    return clean_text(node.get("content")) if node else ""


def _first_text(soup: BeautifulSoup, selector: str) -> str:
    node = soup.select_one(selector)
    return clean_text(node.get_text(" ", strip=True)) if node else ""


def _fetch_bytes(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read()
