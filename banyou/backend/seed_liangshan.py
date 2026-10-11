"""凉山州景区内容种子脚本：管理员 + 区域 + 景区/点位/路线 + 应用设置。

用法：
    python seed_liangshan.py            # 增量灌入（同名景区跳过）
    python seed_liangshan.py --reset    # 清空重建（危险：删除全部数据）

说明：点位坐标为演示用近似值，已按真实区位落在合理范围，
上线前可在管理后台逐点校正（后台「点位管理」支持地图选点）。
"""
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.security import hash_password  # noqa: E402
from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models import AdminUser, Region, RouteStop, ScenicArea, Spot, TourRoute  # noqa: E402

REGION = {"code": "liangshan", "name": "凉山彝族自治州", "sort": 0}

# 每个景区：基础信息 + spots（讲解点位）+ routes（伴游路线，stop 引用 spot name）
AREAS = [
    {
        "name": "邛海泸山景区", "en_name": "Qionghai Lake & Lushan Mountain",
        "cover_url": "/uploads/images/area-1.jpg",
        "city": "西昌市", "level": "4A", "rating": 4.6,
        "address": "凉山州西昌市海滨中路", "tel": "0834-3950070",
        "open_time": "全天开放（索道 08:30-17:30，博物馆周一闭馆）",
        "ticket_info": "邛海湿地、泸山免费；奴隶社会博物馆凭证件免费参观",
        "suggested_hours": 6, "lat": 27.860, "lng": 102.268,
        "tags": ["高原湖泊", "湿地候鸟", "彝族文化", "城市近郊", "观星"],
        "best_season": "四季皆宜，11 月-次年 3 月可观越冬候鸟",
        "short_intro": "山、水、城相依的高原湖泊，西昌的「母亲湖」，背靠泸山，怀抱湿地。",
        "intro": (
            "邛海是四川省第二大天然淡水湖，与泸山并肩构成「山、水、城」一体的城市型景区。"
            "环湖建有观鸟岛、梦里水乡、烟雨鹭洲等多片湿地，冬季黑颈鹤、红嘴鸥等候鸟云集；"
            "泸山海拔 2317 米，山腰坐落千年古刹光福寺与凉山彝族奴隶社会博物馆，"
            "登顶可俯瞰邛海全景与西昌城区。月城西昌纬度低、海拔高、晴天多，"
            "夜幕降临后湖畔观星与烧烤烟火气并存的体验尤为独特。"
        ),
        "spots": [
            {
                "name": "邛海公园", "category": "休闲", "lat": 27.853, "lng": 102.266,
                "stay_minutes": 40, "sort": 1,
                "narration": {
                    "zh": (
                        "邛海公园是环湖最早建成的滨湖开放公园，紧邻西昌城区，是本地人晨练、"
                        "亲水的第一站。沿湖步道视野开阔，可以远眺泸山黛色轮廓；"
                        "傍晚湖面被落日染成金色，是拍摄「月城落日」的经典机位。"
                        "公园与观鸟岛湿地之间有绿道相连，步行或骑行均可环湖进入湿地深处。"
                    ),
                    "en": (
                        "Qionghai Park is the lakeside open park closest to downtown Xichang, "
                        "a favorite morning-exercise spot for locals. The lakeshore promenade "
                        "offers a clear view of Lushan Mountain, and sunset here gilds the whole lake."
                    ),
                },
                "tips": "环湖绿道可租双人/四人观光自行车。",
            },
            {
                "name": "观鸟岛湿地公园", "category": "生态", "lat": 27.872, "lng": 102.278,
                "stay_minutes": 60, "sort": 2,
                "narration": {
                    "zh": (
                        "观鸟岛湿地是邛海湿地群的核心片区，栈道深入芦苇荡与浅滩，"
                        "是观察白鹭、骨顶鸡和越冬红嘴鸥的天然观察点。"
                        "湿地起到了净化入湖水质的作用，也重建了鱼类与水鸟的栖息地。"
                        "请保持安静、勿投喂野生鸟类，清晨与黄昏是观鸟的最佳时段。"
                    ),
                    "en": (
                        "Bird Island Wetland is the heart of the Qionghai wetland group. "
                        "Boardwalks run through reeds and shallows where egrets and wintering "
                        "gulls gather. Early morning and dusk are the best birding hours."
                    ),
                },
                "tips": "栈道较长，建议穿舒适的鞋并备饮用水。",
            },
            {
                "name": "月亮湾湿地公园", "category": "观景", "lat": 27.868, "lng": 102.296,
                "stay_minutes": 40, "sort": 3,
                "narration": {
                    "zh": (
                        "月亮湾位于邛海东岸，湖岸线在这里弯出一弯新月形浅滩，因此得名。"
                        "这里水域开阔、芦苇成片，是环湖日出的最佳观赏点之一；"
                        "清晨薄雾未散时，渔舟与远山同框，是摄影爱好者钟爱的画面。"
                    ),
                    "en": (
                        "Moon Bay curves along the eastern shore of Qionghai Lake. "
                        "With open water and reed beds, it is one of the best sunrise spots "
                        "around the lake."
                    ),
                },
            },
            {
                "name": "小渔村", "category": "体验", "lat": 27.880, "lng": 102.262,
                "stay_minutes": 60, "sort": 4,
                "narration": {
                    "zh": (
                        "小渔村是邛海北岸的老渔村改造而成的美食街区，"
                        "湖鲜烧烤是这里的名片：邛海白鱼、银鱼烘蛋、醉虾配苦荞茶，"
                        "再添一炉炭火烤肉，是西昌夜生活的标准打开方式。"
                        "白天来则可以看渔人收网，感受「靠海吃海」的湖居生活。"
                    ),
                    "en": (
                        "Little Fishing Village is a lakeside food street famous for lakeshore "
                        "barbecue: Qionghai whitefish, silverfish omelette and drunken shrimp."
                    ),
                },
                "tips": "傍晚烧烤摊位集中出摊，热门店铺建议提前占座。",
            },
            {
                "name": "泸山山门", "category": "文化", "lat": 27.843, "lng": 102.256,
                "stay_minutes": 15, "sort": 5,
                "narration": {
                    "zh": (
                        "泸山古称「蚌巂山」，山门拾级而上即是全长约两公里的登山道。"
                        "泸山与邛海垂直高差约 800 米，「半山撑船、山顶观海」的立体景观"
                        "让它享有「川南胜境」之名。登山道沿途古树参天，"
                        "野生猕猴时常出没，请收好食物与塑料袋。"
                    ),
                    "en": (
                        "The gate of Lushan Mountain marks the start of a 2-kilometer pilgrim "
                        "trail. Wild macaques roam the shaded path — keep food out of sight."
                    ),
                },
                "tips": "山上猴群活跃，勿手提食物袋、勿逗猴。",
            },
            {
                "name": "光福寺", "category": "宗教", "lat": 27.846, "lng": 102.257,
                "stay_minutes": 40, "sort": 6,
                "narration": {
                    "zh": (
                        "光福寺始建于唐代，是泸山规模最大的寺院，寺内天王殿、望海楼依山而建。"
                        "寺前古汉柏相传植于汉代，已逾两千年树龄。"
                        "寺内收藏的地震碑林陈列着西昌历史上多次强震的碑刻记录，"
                        "是国内罕见的「石头上的地震档案」，对研究安宁河断裂带极具价值。"
                    ),
                    "en": (
                        "Guangfu Temple, first built in the Tang dynasty, is the largest temple "
                        "on Lushan. Its Earthquake Stele Forest preserves stone records of "
                        "historic strong earthquakes in the Anninghe fault zone."
                    ),
                },
            },
            {
                "name": "凉山彝族奴隶社会博物馆", "category": "文化", "lat": 27.847, "lng": 102.253,
                "stay_minutes": 60, "sort": 7,
                "narration": {
                    "zh": (
                        "这是世界上唯一一座反映彝族奴隶社会形态的专题博物馆，1985 年开馆。"
                        "馆内以彝族的谱系、家支制度、毕摩文化、漆器与银饰为主线，"
                        "系统呈现了 1956 年民主改革前凉山彝族社会的社会结构与文化面貌。"
                        "理解了「一山分四季，十里不同天」之上的「一部落一乾坤」，"
                        "再看凉山的山川村寨会有完全不同的眼光。"
                    ),
                    "en": (
                        "This is the world's only museum dedicated to the Yi slave-society era, "
                        "opened in 1985. Its collections cover Yi clan structure, Bimo culture, "
                        "lacquerware and silver ornaments before the 1956 democratic reform."
                    ),
                },
                "tips": "周一闭馆；讲解器与人工讲解可在服务台咨询。",
            },
            {
                "name": "泸山山顶观景台", "category": "观景", "lat": 27.849, "lng": 102.252,
                "stay_minutes": 30, "sort": 8,
                "narration": {
                    "zh": (
                        "登顶观景台，邛海如一面镜子铺展在城市与群山之间，"
                        "天气晴好时可远眺西昌城区与安宁河谷。"
                        "这里也是俯瞰邛海全景的唯一高山视角，日落前一小时光线最为柔和。"
                        "累了可以在山顶茶社歇脚，把「山、水、城」尽收眼底再下山。"
                    ),
                    "en": (
                        "The summit platform lays Qionghai Lake out like a mirror between city "
                        "and mountains — the finest panoramic view, best one hour before sunset."
                    ),
                },
            },
            {
                "name": "海河天街", "category": "休闲", "lat": 27.878, "lng": 102.258,
                "stay_minutes": 50, "sort": 9,
                "narration": {
                    "zh": (
                        "海河天街是连接邛海与西昌城区的滨水商业街，仿川西民居沿河而建。"
                        "夜幕降临后灯火倒映河面，烧烤、咖啡馆与小酒馆一字排开，"
                        "是游览结束后吃晚饭、歇脚的便利选择。"
                    ),
                    "en": (
                        "Haihe Street is a riverside dining and leisure street linking Qionghai "
                        "Lake with downtown Xichang, liveliest after dark."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "邛海环湖湿地休闲线", "theme": "休闲",
                "intro": "沿环湖绿道串起公园、湿地与渔村，骑行或乘观光车皆宜，冬季可一路观鸟。",
                "duration_minutes": 240, "distance_km": 18.0, "difficulty": "轻松",
                "mode": "骑行/观光车",
                "stop_names": ["邛海公园", "观鸟岛湿地公园", "月亮湾湿地公园", "小渔村", "海河天街"],
            },
            {
                "name": "泸山人文登高线", "theme": "人文",
                "intro": "登山道串起古寺、博物馆与山顶观景台，半日读懂凉山历史与彝文化。",
                "duration_minutes": 180, "distance_km": 4.5, "difficulty": "中等",
                "mode": "步行",
                "stop_names": ["泸山山门", "光福寺", "凉山彝族奴隶社会博物馆", "泸山山顶观景台"],
            },
        ],
    },
    {
        "name": "泸沽湖景区", "en_name": "Lugu Lake Scenic Area",
        "cover_url": "/uploads/images/area-2.jpg",
        "city": "盐源县", "level": "4A", "rating": 4.7,
        "address": "凉山州盐源县泸沽湖镇", "tel": "0834-6390302",
        "open_time": "全天开放（游船 08:00-18:00，索道 08:30-17:30）",
        "ticket_info": "门票 70 元/人（川滇联票政策以景区公告为准），游船/索道另计",
        "suggested_hours": 12, "lat": 27.755, "lng": 100.770,
        "tags": ["高原湖泊", "摩梭文化", "女儿国", "环湖", "星空"],
        "best_season": "3-10 月；冬季湖面静谧也可观候鸟",
        "short_intro": "高原断层溶蚀湖泊，摩梭人母系文化的故乡，川滇共拥的一颗「高原明珠」。",
        "intro": (
            "泸沽湖海拔 2690 米，平均水深 40 余米，能见度常年居国内湖泊前列。"
            "湖畔摩梭人至今保留母系大家庭与「走婚」习俗，被称为「东方女儿国」。"
            "四川盐源一侧拥有草海、走婚桥、王妃岛等经典景观，环湖公路串联川滇两岸村落。"
            "清晨的猪槽船、黄昏的女神山、夜晚的银河，构成了泸沽湖「三日不成文」的完整体验。"
        ),
        "spots": [
            {
                "name": "泸沽湖观景台", "category": "观景", "lat": 27.733, "lng": 100.778,
                "stay_minutes": 20, "sort": 1,
                "narration": {
                    "zh": (
                        "观景台建在进入湖区公路的山脊上，是泸沽湖的第一眼全景："
                        "湖水自东向西铺开，里格半岛、女神山与湖心岛屿尽收眼底。"
                        "绝大多数泸沽湖的明信片角度都出自这里，上午顺光拍摄效果最好。"
                    ),
                    "en": (
                        "The viewing platform on the ridge offers the classic first panorama of "
                        "Lugu Lake — the postcard angle, best shot in morning light."
                    ),
                },
            },
            {
                "name": "大落水村", "category": "体验", "lat": 27.747, "lng": 100.767,
                "stay_minutes": 60, "sort": 2,
                "narration": {
                    "zh": (
                        "大落水是泸沽湖最早开发的摩梭村落，湖岸栈道、猪槽船码头与民宿集中。"
                        "村里仍保留母系大家庭的院落格局，祖母屋是全家火塘所在。"
                        "傍晚沿湖散步，看归港的猪槽船被夕阳镀上金边，是泸沽湖最松弛的时刻。"
                    ),
                    "en": (
                        "Daluo Shui Village is the lake's earliest tourist village, home to Mosuo "
                        "extended families and the departure point for pig-trough boats."
                    ),
                },
            },
            {
                "name": "摩梭民俗博物馆", "category": "文化", "lat": 27.752, "lng": 100.764,
                "stay_minutes": 50, "sort": 3,
                "narration": {
                    "zh": (
                        "博物馆系统展示摩梭人的母系家庭、走婚习俗、达巴教与服饰工艺。"
                        "重点看祖母屋复原场景与花楼窗棂：前者是母系家庭的核心空间，"
                        "后者关联着走婚文化中「花楼相会」的礼俗。"
                        "先看博物馆再游湖，摩梭文化的细节会一路「活」起来。"
                    ),
                    "en": (
                        "The Mosuo Folk Museum explains matrilineal family life, walking-marriage "
                        "customs and Daba beliefs. Visit here first and the lake reads differently."
                    ),
                },
            },
            {
                "name": "情人滩", "category": "观景", "lat": 27.774, "lng": 100.761,
                "stay_minutes": 30, "sort": 4,
                "narration": {
                    "zh": (
                        "情人滩是一段平缓的浅水沙滩，湖水清浅、鹅卵石历历可见。"
                        "传说摩梭青年男女曾在湖滩对歌定情，滩名由此而来。"
                        "晴日午后湖水呈现层次分明的蓝色渐变，是环湖路上最出片的一站。"
                    ),
                    "en": (
                        "Lovers' Beach is a shallow pebble cove where Mosuo youth once courted in "
                        "song. The layered blues of the water make it the most photogenic stop."
                    ),
                },
            },
            {
                "name": "里格半岛", "category": "观景", "lat": 27.792, "lng": 100.772,
                "stay_minutes": 50, "sort": 5,
                "narration": {
                    "zh": (
                        "里格半岛以一道细长沙嘴伸入湖心，三面环水，是泸沽湖的地标轮廓。"
                        "观景平台上望去，「湖中一岛、岛边一湾」的画面几乎定义了泸沽湖的美。"
                        "半岛上的民宿多依湖而建，日出时分推窗即是「湖面金线」。"
                    ),
                    "en": (
                        "Lige Peninsula stretches into the lake on a narrow sand spit — the "
                        "landmark silhouette of Lugu Lake, glorious at sunrise."
                    ),
                },
            },
            {
                "name": "格姆女神山索道", "category": "体验", "lat": 27.812, "lng": 100.782,
                "stay_minutes": 90, "sort": 6,
                "narration": {
                    "zh": (
                        "格姆女神山海拔 3770 米，摩梭人视其为守护湖泊的女神化身。"
                        "索道攀升近千米，山腰可远眺整面湖区；山上的女神洞是当地转山节的重要节点。"
                        "每年农历七月二十五的转山节，摩梭人身着盛装绕山祭祀，是湖区最盛大的节日。"
                    ),
                    "en": (
                        "Gemu Goddess Mountain rises 3,770 meters; the cableway climbs nearly a "
                        "kilometer to lake-overlooking slopes sacred to the Mosuo goddess."
                    ),
                },
                "tips": "山顶风大温差大，备防风外套；恐高者可选山下环湖视角。",
            },
            {
                "name": "博凹岛·王妃岛", "category": "观景", "lat": 27.766, "lng": 100.742,
                "stay_minutes": 60, "sort": 7,
                "narration": {
                    "zh": (
                        "博凹岛因末代左所土司喇宝成夫人肖淑明曾居于岛上而俗称「王妃岛」。"
                        "乘猪槽船登岛，可环岛一周俯看清澈湖水由浅碧转深蓝。"
                        "「土司王妃」的传奇身世，为这座小岛添了几分女儿国的人间烟火。"
                    ),
                    "en": (
                        "Bo'ao Island is nicknamed ' Princess Island ' after the last chieftain's "
                        "wife who once lived here; pig-trough boats ferry visitors across."
                    ),
                },
            },
            {
                "name": "草海", "category": "生态", "lat": 27.718, "lng": 100.752,
                "stay_minutes": 40, "sort": 8,
                "narration": {
                    "zh": (
                        "草海是泸沽湖东南面的浅水湿地，万亩芦苇在水面铺成草原，故得此名。"
                        "这里生活着 37 种水鸟，春夏苍翠、秋冬金黄，四季各有性格。"
                        "薄雾清晨乘船穿行水巷，是摄影人排队也要等的画面。"
                    ),
                    "en": (
                        "Caohai (' Grass Sea ') is a vast shallow wetland where reeds float like a "
                        "meadow on water, home to dozens of waterbird species."
                    ),
                },
            },
            {
                "name": "走婚桥", "category": "文化", "lat": 27.714, "lng": 100.747,
                "stay_minutes": 30, "sort": 9,
                "narration": {
                    "zh": (
                        "走婚桥横跨草海，长约 300 米，是摩梭人「走婚」文化的地标。"
                        "传统摩梭社会中男女双方不组建共同家庭，男方夜晚到女方「花楼」相会，"
                        "清晨返回母亲家劳作，家庭以母系血缘为纽带延续。"
                        "桥上走一遭，再回看这片湖山的「女儿国」秩序，会有具体的理解。"
                    ),
                    "en": (
                        "The Walking-Marriage Bridge spans Caohai wetland, emblem of Mosuo "
                        "matrilineal courtship customs in which children belong to the mother's "
                        "household."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "泸沽湖环湖经典伴游线", "theme": "休闲",
                "intro": "顺时针环湖一圈串起川滇两岸精华：观景台、里格、女神山、王妃岛、草海走婚桥。",
                "duration_minutes": 480, "distance_km": 68.0, "difficulty": "轻松",
                "mode": "车行+步行",
                "stop_names": [
                    "泸沽湖观景台", "大落水村", "摩梭民俗博物馆", "情人滩", "里格半岛",
                    "格姆女神山索道", "博凹岛·王妃岛", "草海", "走婚桥",
                ],
            },
        ],
    },
    {
        "name": "螺髻山景区", "en_name": "Luojishan Mountain",
        "cover_url": "/uploads/images/area-3.jpg",
        "city": "普格县", "level": "4A", "rating": 4.5,
        "address": "凉山州普格县螺髻山镇", "tel": "0834-4779199",
        "open_time": "08:00-17:30（索道 08:30-16:30）",
        "ticket_info": "门票 90 元/人，索道往返 130 元/人（以景区公告为准）",
        "suggested_hours": 7, "lat": 27.505, "lng": 102.335,
        "tags": ["古冰川", "高山湖泊", "杜鹃花海", "徒步", "温泉瀑布"],
        "best_season": "4-6 月杜鹃花开；秋季彩林；冬季雪凇",
        "short_intro": "「峨眉山女人髻，螺髻山男人螺」——古冰川遗迹与高山杜鹃之山。",
        "intro": (
            "螺髻山主峰海拔 4359 米，因山形酷似少女发髻而得名，与峨眉山并称「姐妹峰」。"
            "山保存着完整的第三纪古冰川遗迹：冰蚀冰碛湖群、角峰刃脊与巨大的冰川刻槽。"
            "山上 50 余个高山湖泊如珍珠散落，每年 4-6 月三十余种杜鹃次第开放，"
            "「杜鹃花海映冰湖」是川内高山景观的独一份。山麓的温泉瀑布群常年 40℃，"
            "登山归来泡一场山泉瀑布，是普格县的经典动线。"
        ),
        "spots": [
            {
                "name": "螺髻山游客中心", "category": "服务", "lat": 27.486, "lng": 102.353,
                "stay_minutes": 20, "sort": 1,
                "narration": {
                    "zh": (
                        "游客中心是螺髻山的起点，海拔约 2000 米，在此购票换乘观光车前往索道下站。"
                        "山上气温常年比山下低 8-12℃，建议在此租借羽绒服或自备保暖衣物。"
                        "高原徒步注意放缓节奏，老人小孩可在中心寄存多余行李轻装上山。"
                    ),
                    "en": (
                        "The visitor center at about 2,000 m elevation is the starting point; "
                        "summit temperatures run 8-12°C lower, so rent a coat here if needed."
                    ),
                },
                "tips": "山上山下温差大，防风保暖衣物必备。",
            },
            {
                "name": "索道上站", "category": "服务", "lat": 27.503, "lng": 102.338,
                "stay_minutes": 15, "sort": 2,
                "narration": {
                    "zh": (
                        "索道全程约 2.4 公里，攀升 1000 余米，穿云破雾约需 30 分钟。"
                        "出站即进入高山湖泊核心区，脚下是从冰川时代走来的湖群与杜鹃林。"
                        "初到海拔 3600 米，行动放缓、少剧烈奔跑，给身体半小时适应时间。"
                    ),
                    "en": (
                        "The 2.4-kilometer cableway climbs over 1,000 meters in about 30 minutes, "
                        "arriving at 3,600 m — pace yourself in the thin air."
                    ),
                },
            },
            {
                "name": "黑龙潭", "category": "观景", "lat": 27.507, "lng": 102.336,
                "stay_minutes": 40, "sort": 3,
                "narration": {
                    "zh": (
                        "黑龙潭是螺髻山最大的冰碛湖，湖水呈深黛色，晴日倒映角峰如镜。"
                        "湖由古冰川刨蚀洼地积水而成，湖畔一圈圈冰碛垄记录着冰川进退的年轮。"
                        "逆光时湖面碎金浮动，是高山摄影的黄金机位。"
                    ),
                    "en": (
                        "Black Dragon Lake is the largest moraine lake on Luojishan, mirroring "
                        "the horns and ridges carved by Ice-Age glaciers."
                    ),
                },
            },
            {
                "name": "仙草湖", "category": "观景", "lat": 27.509, "lng": 102.344,
                "stay_minutes": 30, "sort": 4,
                "narration": {
                    "zh": (
                        "仙草湖水浅而清，湖底水草随波摇曳，夏日湖畔开满小叶杜鹃。"
                        "栈道绕湖一周约 40 分钟，是高山湖泊群里最轻松的一段散步路线。"
                    ),
                    "en": (
                        "Immortal Grass Lake is shallow and clear with waving waterweeds — the "
                        "easiest 40-minute boardwalk loop among the alpine lakes."
                    ),
                },
            },
            {
                "name": "牦牛崖", "category": "观景", "lat": 27.514, "lng": 102.341,
                "stay_minutes": 30, "sort": 5,
                "narration": {
                    "zh": (
                        "牦牛崖是一片突出的玄武岩崖壁，因岩形似低头饮水的牦牛得名。"
                        "崖顶视野开阔，可同时望见数个冰蚀湖如碎镜散落山坳。"
                        "崖边风大，拍照请勿翻越护栏。"
                    ),
                    "en": (
                        "Yak Cliff is a basalt outcrop named for its drinking-yak silhouette, "
                        "with several glacial lakes visible from the top."
                    ),
                },
            },
            {
                "name": "杜鹃花海", "category": "生态", "lat": 27.511, "lng": 102.330,
                "stay_minutes": 40, "sort": 6,
                "narration": {
                    "zh": (
                        "螺髻山有三十余种杜鹃，从山脚到垭口次第开放，花期从 4 月延续到 6 月。"
                        "高山杜鹃低伏成片，花色由乳白、粉紫到绛红，与黑色火山岩相映成趣。"
                        "「一山有四季，十里不同花」，说的正是这段路。"
                    ),
                    "en": (
                        "Over thirty rhododendron species bloom up the mountain from April to "
                        "June, white to crimson against dark volcanic rock."
                    ),
                },
            },
            {
                "name": "古冰川刻槽", "category": "地质", "lat": 27.505, "lng": 102.333,
                "stay_minutes": 20, "sort": 7,
                "narration": {
                    "zh": (
                        "脚下的花岗岩面上刻着一道道平行的深槽——这是百万年前冰川裹挟砾石"
                        "磨蚀岩床留下的「锉痕」，地质学上称为冰川刻槽。"
                        "螺髻山的刻槽之大、之清晰在国内外都属罕见，是古冰川时代的直接物证。"
                        "伸手抚过槽线，就摸到了地质史的一页。"
                    ),
                    "en": (
                        "Parallel grooves scored into the bedrock are glacial striae — evidence "
                        "of Ice-Age grinding, exceptionally large and clear at Luojishan."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "螺髻山高山湖泊徒步线", "theme": "徒步",
                "intro": "索道直达 3600 米高山湖群，串起黑龙潭、仙草湖与牦牛崖，杜鹃花期最美。",
                "duration_minutes": 240, "distance_km": 8.0, "difficulty": "中等",
                "mode": "索道+徒步",
                "stop_names": ["索道上站", "黑龙潭", "仙草湖", "杜鹃花海", "牦牛崖", "古冰川刻槽"],
            },
        ],
    },
    {
        "name": "西昌卫星发射中心景区", "en_name": "Xichang Satellite Launch Center",
        "cover_url": "/uploads/images/area-4.jpg",
        "city": "冕宁县", "level": "研学基地", "rating": 4.5,
        "address": "凉山州冕宁县泽远镇", "tel": "0834-6770057",
        "open_time": "以景区当日公告为准（发射任务期间临时关闭）",
        "ticket_info": "参观票含展厅与观景平台，具体以景区公告为准",
        "suggested_hours": 3, "lat": 28.240, "lng": 102.028,
        "tags": ["航天", "研学", "亲子", "爱国主义教育"],
        "best_season": "全年；避开发射任务窗口期",
        "short_intro": "北斗与嫦娥的升空之地，中国航天的「烽火台」。",
        "intro": (
            "西昌卫星发射中心 1984 年投入使用，因纬度低、海拔高、峡谷地形隐蔽，"
            "成为中国发射地球同步轨道卫星的「黄金火箭港」。"
            "北斗组网卫星、嫦娥探月工程探测器均从这里奔向太空。"
            "景区可近距离参观发射塔架、指挥控制大楼与航天展厅，"
            "若逢发射窗口，峡谷中火箭点火的轰鸣是最震撼的现场课。"
        ),
        "spots": [
            {
                "name": "游客接待中心", "category": "服务", "lat": 28.222, "lng": 102.024,
                "stay_minutes": 20, "sort": 1,
                "narration": {
                    "zh": (
                        "接待中心是参观的起点，购票后统一乘车进入发射场区。"
                        "参观全程禁止使用无人机，部分区域限制拍照，请以现场标识为准。"
                    ),
                    "en": (
                        "The reception center is the tour start point; shuttle buses enter the "
                        "launch complex. Drones are prohibited throughout."
                    ),
                },
            },
            {
                "name": "航天主题展厅", "category": "研学", "lat": 28.244, "lng": 102.026,
                "stay_minutes": 50, "sort": 2,
                "narration": {
                    "zh": (
                        "展厅陈列长征系列运载火箭模型、嫦娥工程实物件与任务纪念章。"
                        "重点看「嫦娥一号」1:1 备份星与月球土壤展示区，"
                        "它们记录着中国深空探测从零起步的二十年。"
                    ),
                    "en": (
                        "Exhibition halls display Long March rocket models, Chang'e lunar program "
                        "artifacts and mission memorabilia from two decades of deep-space flight."
                    ),
                },
            },
            {
                "name": "发射塔架观景平台", "category": "研学", "lat": 28.246, "lng": 102.028,
                "stay_minutes": 40, "sort": 3,
                "narration": {
                    "zh": (
                        "两座活动塔架矗立在峡谷中，固定勤务塔高达 70 余米。"
                        "嫦娥一号、北斗组网卫星都从这两座塔位升空。"
                        "非任务期可清晰看到塔架回转平台与导流槽结构，"
                        "想象火箭点火瞬间数千度尾焰冲入导流槽的画面。"
                    ),
                    "en": (
                        "Two launch towers rise from the canyon; Chang'e-1 and Beidou satellites "
                        "lifted off here. The umbilical and deflector structures are visible up close."
                    ),
                },
                "tips": "部分点位限制拍照，以现场标识与工作人员指引为准。",
            },
            {
                "name": "指挥控制大楼外景", "category": "研学", "lat": 28.245, "lng": 102.030,
                "stay_minutes": 20, "sort": 4,
                "narration": {
                    "zh": (
                        "发射任务的大脑。「X 分钟准备」的口令从这里发出，"
                        "点火按键按下前，测发、测控、气象各系统在此完成最后确认。"
                        "楼前的倒计时牌是游客最爱合影的位置。"
                    ),
                    "en": (
                        "The mission control building where countdown commands are issued — the "
                        "countdown clock in front is a favorite photo spot."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "航天研学伴游线", "theme": "研学",
                "intro": "展厅—塔架—指挥中心的完整参观动线，配合讲解适合亲子与研学团队。",
                "duration_minutes": 150, "distance_km": 3.0, "difficulty": "轻松",
                "mode": "步行+摆渡车",
                "stop_names": ["游客接待中心", "航天主题展厅", "发射塔架观景平台", "指挥控制大楼外景"],
            },
        ],
    },
    {
        "name": "会理古城", "en_name": "Huili Ancient City",
        "cover_url": "/uploads/images/area-5.jpg",
        "city": "会理市", "level": "4A", "rating": 4.4,
        "address": "凉山州会理市古城街道", "tel": "0834-5622158",
        "open_time": "全天开放（纪念馆 09:00-17:00，周一闭馆）",
        "ticket_info": "古城免费；纪念馆凭证件免费参观",
        "suggested_hours": 4, "lat": 26.658, "lng": 102.245,
        "tags": ["古城", "红色文化", "绿陶", "川滇门户"],
        "best_season": "全年；火把节与春节灯会最热闹",
        "short_intro": "「川滇锁钥」两千余年城址未迁，青瓦深巷里的南丝路重镇。",
        "intro": (
            "会理始建于西汉，两千余年城址未曾迁移，是古代南方丝绸之路入滇的咽喉。"
            "古城格局完整：钟鼓楼居中，四方街巷放射如棋盘，明清民居院落保存完好。"
            "1935 年中央红军长征过会理，著名的会理会议在此召开。"
            "城内会理绿陶烧制技艺传承六百年，「孔雀开屏」釉色是国家级非遗名片。"
        ),
        "spots": [
            {
                "name": "北门城楼·拱极楼", "category": "文化", "lat": 26.662, "lng": 102.245,
                "stay_minutes": 30, "sort": 1,
                "narration": {
                    "zh": (
                        "拱极楼是会理古城的北大门，始建于明，城台上的重檐歇山顶是古城的天际线起点。"
                        "「拱极」取「众星拱北」之意，古代出此门北上即是入川孔道。"
                        "登楼可沿箭窗北望白塔山，南瞰全城青瓦。"
                    ),
                    "en": (
                        "Gongji Gate, the Ming-era north gate, anchors the old city skyline; "
                        "climb up for views from White Pagoda Hill to the tiled rooftops."
                    ),
                },
            },
            {
                "name": "科甲巷", "category": "文化", "lat": 26.659, "lng": 102.247,
                "stay_minutes": 40, "sort": 2,
                "narration": {
                    "zh": (
                        "科甲巷因明清两代巷内科第连绵而得名，「一门七举人」的胡氏民居就在巷中。"
                        "青瓦悬山、穿斗木构的院落里，天井照壁与雕花门楣保留着南丝路商贾人家的体面。"
                        "慢下来看门楣题字，每一方都对应着一个耕读传家的故事。"
                    ),
                    "en": (
                        "Kejia Lane earned its name (' Scholars' Lane ') from generations of "
                        "imperial-exam successes; its Ming-Qing courtyards remain intact."
                    ),
                },
            },
            {
                "name": "钟鼓楼·凌霄楼", "category": "文化", "lat": 26.657, "lng": 102.245,
                "stay_minutes": 30, "sort": 3,
                "narration": {
                    "zh": (
                        "钟鼓楼位于古城几何中心，凌霄楼三重檐攒尖顶直指天心，"
                        "晨钟暮鼓曾是全城的报时标准。"
                        "以钟楼为原点，东西南北四街放射展开，构成会理「田字格」的城市骨架，"
                        "这种格局在川内古城中保存得相当完整。"
                    ),
                    "en": (
                        "The Drum-and-Bell Tower marks the geometric center of Huili; four streets "
                        "radiate from it in a grid that survives from Ming times."
                    ),
                },
            },
            {
                "name": "红军长征过会理纪念馆", "category": "红色", "lat": 26.656, "lng": 102.244,
                "stay_minutes": 50, "sort": 4,
                "narration": {
                    "zh": (
                        "1935 年 5 月，中央红军巧渡金沙江后进入会理，在铁厂村召开了著名的会理会议。"
                        "纪念馆以沙盘、实物与影像再现了巧渡金沙江、会理会议与各族群众支援红军的历史。"
                        "这是长征中一次统一战略方向的重要会议，会理由此写下红色一笔。"
                    ),
                    "en": (
                        "In May 1935 the Central Red Army crossed the Jinsha River and held the "
                        "pivotal Huili Conference; the museum recounts this episode in detail."
                    ),
                },
                "tips": "周一闭馆，节假日开放时间以公告为准。",
            },
            {
                "name": "白塔山·文塔", "category": "观景", "lat": 26.668, "lng": 102.250,
                "stay_minutes": 40, "sort": 5,
                "narration": {
                    "zh": (
                        "白塔山文塔始建于清，九级白塔是会理的文风象征，也是古城北面的制高点。"
                        "登山步道半小时可达塔下，回望古城，钟鼓楼与连片青瓦尽收眼底，"
                        "黄昏时「白塔衔落日」是本地摄影人的偏爱。"
                    ),
                    "en": (
                        "The nine-story White Pagoda crowns the hill north of town — a half-hour "
                        "climb rewards you with a panorama of the old city at dusk."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "会理古城历史漫游线", "theme": "人文",
                "intro": "北门入城，穿科甲巷、钟鼓楼到红军纪念馆，登白塔收尾，半日读懂两千年。",
                "duration_minutes": 180, "distance_km": 3.5, "difficulty": "轻松",
                "mode": "步行",
                "stop_names": ["北门城楼·拱极楼", "科甲巷", "钟鼓楼·凌霄楼", "红军长征过会理纪念馆", "白塔山·文塔"],
            },
        ],
    },
    {
        "name": "彝海景区", "en_name": "Yihai (Yi Sea) Lake",
        "cover_url": "/uploads/images/area-6.jpg",
        "city": "冕宁县", "level": "4A", "rating": 4.4,
        "address": "凉山州冕宁县彝海镇", "tel": "0834-6852088",
        "open_time": "09:00-17:00",
        "ticket_info": "免费开放（红色教育基地）",
        "suggested_hours": 2, "lat": 28.633, "lng": 102.268,
        "tags": ["红色文化", "高山湖泊", "彝海结盟", "研学"],
        "best_season": "5-10 月",
        "short_intro": "海拔 2280 米的高山湖泊，红军长征「彝海结盟」发生地。",
        "intro": (
            "彝海原名「鱼海子」，是一片面积不足一平方公里的高山湖泊，湖水清冽，四周青松环抱。"
            "1935 年 5 月，刘伯承与小叶丹在此歃血为盟，红军顺利借道彝区北上，"
            "「彝海结盟」成为民族政策史上的丰碑。"
            "湖畔纪念碑与纪念馆依山而建，与湖光山色共同构成一处安静的红色教育现场。"
        ),
        "spots": [
            {
                "name": "彝海结盟纪念碑", "category": "红色", "lat": 28.631, "lng": 102.267,
                "stay_minutes": 20, "sort": 1,
                "narration": {
                    "zh": (
                        "纪念碑正面镌刻「彝海结盟纪念碑」，碑座再现刘伯承与小叶丹歃血结盟的场景。"
                        "结盟以彝族最郑重的仪式完成：清水当酒、以水代酒、誓言为盟，"
                        "红军随后被护送通过百里彝区，为抢渡大渡河赢得了宝贵时间。"
                    ),
                    "en": (
                        "The monument commemorates the 1935 alliance sworn between General Liu "
                        "Bocheng and Yi leader Xiaoyedan, which let the Red Army pass safely."
                    ),
                },
            },
            {
                "name": "彝海结盟纪念馆", "category": "红色", "lat": 28.630, "lng": 102.266,
                "stay_minutes": 40, "sort": 2,
                "narration": {
                    "zh": (
                        "纪念馆陈列结盟时的旗帜、写信用的笔墨复制品与红军留下的实物。"
                        "小叶丹在红军走后备受磨难仍嘱咐家人「要相信红军」，"
                        "其妻守护「中国夷民红军沽鸡支队」队旗多年的故事，是馆藏最动人的一章。"
                    ),
                    "en": (
                        "The memorial hall preserves artifacts of the alliance, including the story "
                        "of the banner of the Guji Detachment shielded by Xiaoyedan's family."
                    ),
                },
            },
            {
                "name": "彝海湖畔", "category": "观景", "lat": 28.634, "lng": 102.269,
                "stay_minutes": 30, "sort": 3,
                "narration": {
                    "zh": (
                        "绕湖木栈道一圈约 40 分钟，湖水直接来自山泉与降水，清澈见底。"
                        "结盟当年，刘伯承与小叶丹正是在这片湖边取水代酒。"
                        "湖畔青松与雪山倒影同框，安静得很难想象八十多年前的紧张与豪情。"
                    ),
                    "en": (
                        "A 40-minute boardwalk circles the crystal alpine lake where the oath of "
                        "alliance was sworn with lake water in place of wine."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "彝海结盟红色教育线", "theme": "红色",
                "intro": "纪念碑—纪念馆—湖畔的紧凑动线，适合研学与主题党日活动。",
                "duration_minutes": 90, "distance_km": 1.5, "difficulty": "轻松",
                "mode": "步行",
                "stop_names": ["彝海结盟纪念碑", "彝海结盟纪念馆", "彝海湖畔"],
            },
        ],
    },
    {
        "name": "灵山景区", "en_name": "Lingshan Scenic Area",
        "cover_url": "/uploads/images/area-7.jpg",
        "city": "冕宁县", "level": "4A", "rating": 4.3,
        "address": "凉山州冕宁县灵山寺景区", "tel": "0834-6722117",
        "open_time": "07:30-18:00",
        "ticket_info": "门票以景区公告为准",
        "suggested_hours": 4, "lat": 28.600, "lng": 102.100,
        "tags": ["宗教文化", "森林徒步", "杜鹃", "祈福"],
        "best_season": "春赏杜鹃，秋观彩林",
        "short_intro": "「灵山灵在树」——原始冷杉林环抱的川西南名刹。",
        "intro": (
            "灵山主峰海拔 4000 余米，山腰的灵山寺始建于清代乾隆年间，"
            "因开山祖师悟真和尚「坐化肉身」的传奇而香火绵延，是川西南著名祈福地。"
            "景区森林覆盖率极高，从山门到大殿的步道穿行于原始冷杉与杜鹃林间，"
            "「寺在林中、林在山中」是灵山最直观的印象。"
        ),
        "spots": [
            {
                "name": "灵山寺山门", "category": "宗教", "lat": 28.598, "lng": 102.103,
                "stay_minutes": 20, "sort": 1,
                "narration": {
                    "zh": (
                        "山门匾额「灵山」二字为清代遗墨，进门即是被参天古树包裹的香道。"
                        "当地人说「灵山灵在树」，这片原始森林被寺规保护数百年，"
                        "任何一棵树都不得砍伐，才留下今天这片头顶的浓荫。"
                    ),
                    "en": (
                        "The gate opens onto a pilgrim path shaded by old-growth fir — a forest "
                        "protected by temple rules for centuries."
                    ),
                },
            },
            {
                "name": "灵山寺大殿", "category": "宗教", "lat": 28.600, "lng": 102.100,
                "stay_minutes": 40, "sort": 2,
                "narration": {
                    "zh": (
                        "大殿供开山祖师悟真和尚，殿后肉身殿供奉其坐化真身，二百余年香火不绝。"
                        "每年农历七月灵山庙会，冕宁及周边信众昼夜上山，是当地最盛大的宗教节庆。"
                        "殿前可远望雪岭层叠，晴天视野极佳。"
                    ),
                    "en": (
                        "The main hall honors founder monk Wuzhen; the July temple fair draws "
                        "pilgrims from across western Sichuan."
                    ),
                },
            },
            {
                "name": "灵山栈道·杜鹃林", "category": "生态", "lat": 28.604, "lng": 102.096,
                "stay_minutes": 60, "sort": 3,
                "narration": {
                    "zh": (
                        "栈道向原始林深处延伸，5-6 月高山杜鹃成片开放，秋季则是红黄彩林。"
                        "林间负氧离子浓度高，慢走深呼吸，是灵山除祈福之外的第二种打开方式。"
                    ),
                    "en": (
                        "The boardwalk dives into primeval forest — rhododendrons in early summer, "
                        "fiery foliage in autumn."
                    ),
                },
                "tips": "栈道部分路段较陡，穿防滑徒步鞋。",
            },
        ],
        "routes": [
            {
                "name": "灵山祈福森林线", "theme": "人文",
                "intro": "香道—大殿—杜鹃栈道，祈福与森林浴合一的山地半日线。",
                "duration_minutes": 150, "distance_km": 4.0, "difficulty": "中等",
                "mode": "步行",
                "stop_names": ["灵山寺山门", "灵山寺大殿", "灵山栈道·杜鹃林"],
            },
        ],
    },
    {
        "name": "马湖景区", "en_name": "Mahu Lake",
        "cover_url": "/uploads/images/area-8.jpg",
        "city": "雷波县", "level": "省级风景名胜区", "rating": 4.3,
        "address": "凉山州雷波县马湖风景区", "tel": "0834-8822056",
        "open_time": "全天开放",
        "ticket_info": "免费开放（游船项目另计）",
        "suggested_hours": 4, "lat": 28.402, "lng": 103.504,
        "tags": ["高原湖泊", "地质奇观", "避暑", "彝家美食"],
        "best_season": "6-9 月避暑最佳",
        "short_intro": "全国第三大高山深水湖泊，「四川三湖」之一的地质活化石。",
        "intro": (
            "马湖是与邛海、泸沽湖齐名的四川三大天然湖泊之一，湖面海拔 1110 米，"
            "最深处逾百米，由地震断陷或古山体滑坡堰塞而成，地质学界至今仍有讨论。"
            "湖水四面环山，金龟岛孤峙湖心，海龙庙香火与彝家渔村隔水相望。"
            "夏季均温 20℃ 上下，是凉山东部最凉爽的度假地。"
        ),
        "spots": [
            {
                "name": "马湖观景台", "category": "观景", "lat": 28.406, "lng": 103.510,
                "stay_minutes": 20, "sort": 1,
                "narration": {
                    "zh": (
                        "观景台正对湖面最开阔处，一湖碧水被环形群山捧在掌心。"
                        "马湖的蓝介于泸沽湖的宝石蓝与邛海的碧绿之间，雨后初晴时层次最丰富。"
                    ),
                    "en": (
                        "The platform faces the widest reach of Mahu Lake, ringed entirely by "
                        "mountains — clearest just after rain."
                    ),
                },
            },
            {
                "name": "湖滨栈道", "category": "休闲", "lat": 28.403, "lng": 103.506,
                "stay_minutes": 40, "sort": 2,
                "narration": {
                    "zh": (
                        "沿湖栈道串起渔村与浅滩，湖风带着水汽，六七月也凉爽如秋。"
                        "栈道边多是彝家餐馆，马湖鲶鱼、坨坨肉与杆杆酒是必点三件套。"
                    ),
                    "en": (
                        "The lakeshore boardwalk runs past Yi fishing villages; try the catfish, "
                        "tuotuo meat and bamboo-pole wine at lakeside restaurants."
                    ),
                },
            },
            {
                "name": "金龟岛", "category": "观景", "lat": 28.400, "lng": 103.501,
                "stay_minutes": 40, "sort": 3,
                "narration": {
                    "zh": (
                        "金龟岛是湖心一座小岛，形似浮龟，传说为镇湖神龟所化。"
                        "乘船登岛环行一周约 20 分钟，岛上的古树与湖浪声是马湖的「静音键」。"
                    ),
                    "en": (
                        "Golden Turtle Island rises from the lake center like a floating turtle; "
                        "boats cross in minutes for a quiet 20-minute loop."
                    ),
                },
            },
            {
                "name": "海龙庙", "category": "宗教", "lat": 28.398, "lng": 103.499,
                "stay_minutes": 20, "sort": 4,
                "narration": {
                    "zh": (
                        "海龙庙供奉马湖龙王，明清以来湖畔渔民出海打渔、祈风调雨顺都在此上香。"
                        "庙不大，但与湖光山色构成马湖人文记忆的核心一角。"
                    ),
                    "en": (
                        "Hailong Temple honors the dragon king of Mahu, where fishermen prayed "
                        "for calm waters for centuries."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "马湖环湖休闲线", "theme": "休闲",
                "intro": "观景台—栈道—金龟岛—海龙庙的环湖动线，夏季避暑首选。",
                "duration_minutes": 150, "distance_km": 5.0, "difficulty": "轻松",
                "mode": "步行+游船",
                "stop_names": ["马湖观景台", "湖滨栈道", "金龟岛", "海龙庙"],
            },
        ],
    },
    {
        "name": "越西文昌故里景区", "en_name": "Wenchang Hometown, Yuexi",
        "cover_url": "/uploads/images/area-9.jpg",
        "city": "越西县", "level": "4A", "rating": 4.2,
        "address": "凉山州越西县中所镇", "tel": "0834-7612628",
        "open_time": "全天开放",
        "ticket_info": "免费开放",
        "suggested_hours": 3, "lat": 28.640, "lng": 102.508,
        "tags": ["文昌文化", "南丝路古道", "水景", "民俗"],
        "best_season": "3-10 月；农历二月初三文昌会最热闹",
        "short_intro": "文昌帝君张亚子传说之乡，零关古道穿境而过的南丝路驿站。",
        "intro": (
            "越西是传说中文昌帝君张亚子的诞生地，「文昌故里」由此得名，"
            "每年农历二月初三文昌会，川滇信众云集。"
            "境内零关古道是南方丝绸之路「灵关道」的核心段，马帮铃声回响了上千年。"
            "景区以水观音泉水景与古道遗存为主线，泉眼涌水量巨大，"
            "「一泉贯全镇」的水乡质感在凉山独树一帜。"
        ),
        "spots": [
            {
                "name": "文昌故里牌坊", "category": "文化", "lat": 28.638, "lng": 102.507,
                "stay_minutes": 15, "sort": 1,
                "narration": {
                    "zh": (
                        "牌坊是景区入口，坊额「文昌故里」四字点题。"
                        "文昌信仰随科举文化传入凉山后与本地民俗融合，"
                        "越西因传说中帝君出生地而成为川滇交界文昌文化的重要发祥地之一。"
                    ),
                    "en": (
                        "The memorial arch marks the entrance to the ' Wenchang Hometown ', "
                        "birthplace of the deity of literature and examinations in local legend."
                    ),
                },
            },
            {
                "name": "零关古道体验段", "category": "文化", "lat": 28.641, "lng": 102.509,
                "stay_minutes": 40, "sort": 2,
                "narration": {
                    "zh": (
                        "脚下这段石板路是南方丝绸之路灵关道的越西段遗存，古称「零关道」。"
                        "司马迁《史记》记载的「蜀身毒道」即经由这里沟通川滇与南亚，"
                        "马帮驮着丝绸、茶叶与盐巴在山脊上走了两千年。"
                    ),
                    "en": (
                        "These stone slabs are remnants of the Lingguan Road, the Southern Silk "
                        "Route linking Sichuan with Yunnan and beyond for two millennia."
                    ),
                },
            },
            {
                "name": "水观音", "category": "宗教", "lat": 28.642, "lng": 102.512,
                "stay_minutes": 50, "sort": 3,
                "narration": {
                    "zh": (
                        "水观音是泉水汇成的深潭，泉眼昼夜涌流，水温常年清冽，当地人称「观音水」。"
                        "潭边庙宇依山而建，泉水穿镇而过滋养出「高原水乡」的景致。"
                        "农历二月初三文昌会与六月火把节时，这里是一年中最热闹的地方。"
                    ),
                    "en": (
                        "Shuiguanyin is a spring-fed pool whose waters run through town, creating "
                        "a rare ' plateau water-town ' scene; festival days are the busiest."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "文昌文化半日线", "theme": "人文",
                "intro": "牌坊—古道—水观音，串起文昌信仰与南丝路记忆。",
                "duration_minutes": 120, "distance_km": 2.5, "difficulty": "轻松",
                "mode": "步行",
                "stop_names": ["文昌故里牌坊", "零关古道体验段", "水观音"],
            },
        ],
    },
    {
        "name": "谷克德高原湿地景区", "en_name": "Gukede Plateau Wetland",
        "cover_url": "/uploads/images/area-10.png",
        "city": "昭觉县", "level": "省级生态旅游示范区", "rating": 4.2,
        "address": "凉山州昭觉县尼地乡", "tel": "0834-8373366",
        "open_time": "全天开放",
        "ticket_info": "免费开放",
        "suggested_hours": 3, "lat": 28.106, "lng": 102.727,
        "tags": ["高原湿地", "索玛花", "草原", "彝族风情"],
        "best_season": "4-6 月索玛花开，7-8 月避暑观星",
        "short_intro": "彝语「大雁栖息的坝子」，索玛花海与星空草原的高原秘境。",
        "intro": (
            "谷克德彝语意为「大雁栖息的坝子」，平均海拔 3000 米上下，"
            "湿地、草甸与成片索玛（杜鹃）构成昭觉县的高原生态名片。"
            "4-6 月索玛花海漫山，7-8 月凉爽如春、银河清晰可见，"
            "景区内彝族牧庄可体验坨坨肉、荞麦饼与口弦音乐，是凉山腹地「小众但不将就」的目的地。"
        ),
        "spots": [
            {
                "name": "谷克德观景台", "category": "观景", "lat": 28.104, "lng": 102.725,
                "stay_minutes": 25, "sort": 1,
                "narration": {
                    "zh": (
                        "观景台海拔逾 3000 米，脚下是开阔的高原湿地坝子，"
                        "大雁与黑颈鹤春秋迁徙时在此歇脚，「谷克德」之名由此而来。"
                        "高原紫外线强、风大，防晒与防风外套请提前备好。"
                    ),
                    "en": (
                        "The 3,000-meter platform overlooks the wetland basin where wild geese "
                        "rest on migration — hence the name Gukede (' goose meadow ')."
                    ),
                },
                "tips": "海拔较高，行动放缓；高原紫外线强注意防晒。",
            },
            {
                "name": "索玛花海", "category": "生态", "lat": 28.110, "lng": 102.731,
                "stay_minutes": 60, "sort": 2,
                "narration": {
                    "zh": (
                        "索玛花是彝语对杜鹃花的称呼，被视为彝家的吉祥之花。"
                        "每年 4-6 月，成片索玛从垭口开到坝子边缘，粉白紫红层层叠叠。"
                        "花海间设有木栈道，请勿采摘——彝家相信折断索玛枝会惊走大雁。"
                    ),
                    "en": (
                        "Suoma (' rhododendron ' in Yi) blooms blanket the plateau from April to "
                        "June — an auspicious flower no one may pick."
                    ),
                },
            },
            {
                "name": "彝家牧庄体验点", "category": "体验", "lat": 28.102, "lng": 102.729,
                "stay_minutes": 60, "sort": 3,
                "narration": {
                    "zh": (
                        "牧庄由当地彝家经营，可以吃到现打的荞麦饼、坨坨羊肉与酸菜土豆汤，"
                        "饭后主人常弹起口弦、唱一支哭嫁调或月琴曲。"
                        "高原夜凉，若留宿牧庄看星空，记得向主人家多要一床被子。"
                    ),
                    "en": (
                        "A Yi family ranch offering buckwheat cakes, tuotuo lamb and jaw-harp "
                        "tunes; stay overnight for the Milky Way, but pack warm clothes."
                    ),
                },
            },
        ],
        "routes": [
            {
                "name": "谷克德花海草原线", "theme": "休闲",
                "intro": "观景台—索玛花海—彝家牧庄，花季与星空季皆宜的高原轻徒步。",
                "duration_minutes": 120, "distance_km": 3.0, "difficulty": "轻松",
                "mode": "步行",
                "stop_names": ["谷克德观景台", "索玛花海", "彝家牧庄体验点"],
            },
        ],
    },
]

SEED_SETTINGS = {
    "app_display_name": "凉山伴游",
    "slogan": "口袋里的凉山向导 · 纯伴游模式",
    "announcement": "凉山州景区讲解内容持续更新中；火把节（农历六月廿四）期间各县市活动密集，出行请注意分流。",
    "service_tel": "0834-12345",
    "footer_note": "凉山州文化和旅游 · 智慧导览示范",
}

# 文创好物：area 为景区名（空 = 全域好物）；spots 为关联点位名（非空则仅在这些点位页露出）
PRODUCTS = [
    {"name": "彝族漆器·酒具三件套", "price": 168, "orig_price": 198, "tags": ["非遗", "漆器"],
     "image_url": "/uploads/images/product-1.jpg",
     "desc": "凉山彝族三色漆器，红黄黑手工描纹，喜碗酒具三件套，送礼与自用皆宜。", "stock": 40},
    {"name": "彝绣香囊·索玛花", "price": 39, "tags": ["彝绣", "伴手礼"],
     "image_url": "/uploads/images/product-2.jpg",
     "desc": "彝家绣娘手工缝制，索玛花纹样，内装苦荞壳与艾草，随身安神。", "stock": 120,
     "area": "邛海泸山景区", "spots": ["凉山彝族奴隶社会博物馆"]},
    {"name": "苦荞茶·大凉山礼盒", "price": 88, "orig_price": 108, "tags": ["物产", "茶饮"],
     "image_url": "/uploads/images/product-3.jpg",
     "desc": "大凉山高海拔苦荞，麦香浓郁，独立小袋便于分赠。", "stock": 80,
     "area": "邛海泸山景区"},
    {"name": "摩梭手工花腰带", "price": 129, "tags": ["手作", "摩梭"],
     "image_url": "/uploads/images/product-4.jpg",
     "desc": "泸沽湖摩梭阿妈手工织就，每一根纹样都不同，系腰或作装饰皆可。", "stock": 30,
     "area": "泸沽湖景区", "spots": ["走婚桥", "摩梭民俗博物馆"]},
    {"name": "盐源苹果干·128g", "price": 19.9, "tags": ["物产", "零食"],
     "image_url": "/uploads/images/product-5.jpg",
     "desc": "盐源高原苹果低温烘制，无添加糖，酸甜有嚼劲。", "stock": 200,
     "area": "泸沽湖景区"},
    {"name": "螺髻山杜鹃·植物标本书签", "price": 25, "tags": ["文创", "书签"],
     "image_url": "/uploads/images/product-6.jpg",
     "desc": "取高山杜鹃落花压制而成，附螺髻山冰川故事卡片。", "stock": 150,
     "area": "螺髻山景区", "spots": ["杜鹃花海"]},
    {"name": "长征火箭 1:200 合金模型", "price": 99, "orig_price": 129, "tags": ["航天", "模型"],
     "image_url": "/uploads/images/product-7.jpg",
     "desc": "以西昌发射的长三甲系列为蓝本，合金铸造，底座刻发射纪年。", "stock": 50,
     "area": "西昌卫星发射中心景区", "spots": ["航天主题展厅", "发射塔架观景平台"]},
    {"name": "会理绿陶·茶具套装", "price": 228, "tags": ["非遗", "绿陶"],
     "image_url": "/uploads/images/product-8.jpg",
     "desc": "六百年绿陶窑烧制，「孔雀开屏」釉色，一壶四杯配竹盘。", "stock": 25,
     "area": "会理古城", "spots": ["科甲巷", "钟鼓楼·凌霄楼"]},
    {"name": "彝海结盟·纪念徽章", "price": 29, "tags": ["红色", "徽章"],
     "image_url": "/uploads/images/product-9.jpg",
     "desc": "以纪念碑为原型的合金徽章，附结盟故事小卡。", "stock": 100,
     "area": "彝海景区", "spots": ["彝海结盟纪念碑", "彝海结盟纪念馆"]},
    {"name": "灵山·高山蜂蜜 250g", "price": 76, "tags": ["物产", "蜂蜜"],
     "image_url": "/uploads/images/product-10.jpeg",
     "desc": "灵山原始冷杉林蜜源，一年一取，结晶细腻。", "stock": 60,
     "area": "灵山景区"},
    {"name": "马湖·银鱼干 100g", "price": 45, "tags": ["物产", "湖鲜"],
     "image_url": "/uploads/images/product-11.jpg",
     "desc": "马湖特产银鱼淡晒而成，煎蛋煮汤皆鲜。", "stock": 90,
     "area": "马湖景区"},
    {"name": "火把节·主题帆布包", "price": 59, "tags": ["文创", "帆布包"],
     "image_url": "/uploads/images/product-12.jpg",
     "desc": "彝人执火把游村剪影印花，厚磅帆布，日常通勤能装。", "stock": 100},
]


def seed(reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
        print("已清空全部数据表")
    init_db()

    db = SessionLocal()
    try:
        # 1) 管理员
        if not db.query(AdminUser).filter(AdminUser.username == "admin").first():
            # 口令取环境变量 ADMIN_INIT_PASSWORD；未设置则随机生成并打印，仓库不留明文
            init_password = os.environ.get("ADMIN_INIT_PASSWORD") or secrets.token_urlsafe(12)
            db.add(AdminUser(
                username="admin", password_hash=hash_password(init_password),
                display_name="运营管理员",
            ))
            print(f"已创建管理员 admin / {init_password}")

        # 2) 区域
        region = db.query(Region).filter(Region.code == REGION["code"]).first()
        if region is None:
            region = Region(**REGION)
            db.add(region)
            db.flush()
            print(f"已创建区域 {region.name}")
        existing_region_id = region.id

        # 3) 应用设置（仅写显式内容项，其余走默认值）
        from app.models.settings import AppSetting
        from app.services.settings_service import SETTING_DEFAULTS
        for key, value in SEED_SETTINGS.items():
            if key in SETTING_DEFAULTS and not db.get(AppSetting, key):
                db.add(AppSetting(key=key, value=value))

        # 4) 景区 / 点位 / 路线
        created_areas = 0
        for spec in AREAS:
            if db.query(ScenicArea).filter(ScenicArea.name == spec["name"]).first():
                print(f"跳过（已存在）：{spec['name']}")
                continue
            spots_spec = spec.get("spots", [])
            routes_spec = spec.get("routes", [])

            area = ScenicArea(region_id=existing_region_id, **{
                k: v for k, v in spec.items() if k not in ("tags", "spots", "routes")
            })
            area.tags = spec.get("tags", [])
            db.add(area)
            db.flush()

            name_to_spot: dict[str, Spot] = {}
            for s in spots_spec:
                spot = Spot(scenic_area_id=area.id, **{
                    k: v for k, v in s.items() if k != "narration"
                })
                spot.narration = s.get("narration", {})
                db.add(spot)
                name_to_spot[spot.name] = spot
            db.flush()

            for r in routes_spec:
                route = TourRoute(scenic_area_id=area.id, **{
                    k: v for k, v in r.items() if k != "stop_names"
                })
                db.add(route)
                db.flush()
                for seq, spot_name in enumerate(r.get("stop_names", []), start=1):
                    spot = name_to_spot.get(spot_name)
                    if spot is None:
                        print(f"  !! 路线「{route.name}」引用了不存在的点位：{spot_name}")
                        continue
                    db.add(RouteStop(route_id=route.id, spot_id=spot.id, seq=seq))

            created_areas += 1
            print(f"已创建景区：{spec['name']}（{len(spots_spec)} 个点位 / {len(routes_spec)} 条路线）")

        db.commit()
        total_spots = db.query(Spot).count()
        total_routes = db.query(TourRoute).count()
        print(f"完成：本次新增景区 {created_areas} 个；库内点位 {total_spots} 个、路线 {total_routes} 条")

        # 5) 文创好物（按名称幂等；点位/景区按名称解析关联）
        from app.models.product import Product

        area_by_name = {a.name: a for a in db.query(ScenicArea).all()}
        spot_by_name = {s.name: s for s in db.query(Spot).all()}
        created_products = 0
        for spec in PRODUCTS:
            if db.query(Product).filter(Product.name == spec["name"]).first():
                continue
            area = area_by_name.get(spec.get("area", ""))
            spots = [spot_by_name[n] for n in spec.get("spots", []) if n in spot_by_name]
            product = Product(
                name=spec["name"], price=spec["price"],
                orig_price=spec.get("orig_price", 0.0),
                desc=spec.get("desc", ""), stock=spec.get("stock", 99),
                scenic_area_id=area.id if area else None,
            )
            product.tags = spec.get("tags", [])
            product.spot_ids = [s.id for s in spots]
            db.add(product)
            created_products += 1
        db.commit()
        print(f"文创好物：新增 {created_products} 件（库内共 {db.query(Product).count()} 件）")
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
