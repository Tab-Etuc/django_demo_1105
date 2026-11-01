from datetime import time
from os import environ

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from courses.academic import CoursePrerequisite, StudentProfile
from courses.models import Course, CourseOffering
from enrollments.models import Enrollment

# 本作業使用真實課名、虛構班別／課綱／上課時間。
WEEK_TOPICS = [
    "課程介紹、學習目標與評分說明",
    "核心觀念與背景知識",
    "領域基礎與案例導讀",
    "工具與基本操作",
    "實作練習（一）",
    "實務案例分析",
    "專題發想與小組討論",
    "實作練習（二）",
    "期中複習與學習檢核",
    "期中實作與成果檢討",
    "進階技術與應用",
    "案例設計與需求分析",
    "團隊專題進度報告",
    "實作練習（三）",
    "測試、修正與成果整理",
    "專題成果撰寫與練習",
    "期末發表及同儕回饋",
    "學期統整與期末評量",
]


def demo_syllabus(course, section, original=None):
    source = original or {
        "summary": course.description,
        "objectives": ["了解核心概念", "將課堂所學應用於實作"],
        "evaluation": {"作業": 40, "期中": 30, "期末": 30},
        "materials": "教師提供之作業示範教材",
        "is_demo": True,
    }
    emphasis = "實務應用" if section == "B" else "基礎與理論"
    return {
        **source,
        "weeks": [f"{course.name}：{topic}（{emphasis}）" for topic in WEEK_TOPICS],
        "is_demo": True,
    }


def demo_class_group(assigned_class):
    return {"甲": "甲班", "乙": "乙班"}.get(assigned_class[-1:], "") if assigned_class else ""


PERIODS = [
    ("08:10", "09:00"),
    ("09:10", "10:00"),
    ("10:10", "11:00"),
    ("11:10", "12:00"),
    ("13:30", "14:20"),
    ("14:25", "15:15"),
    ("15:25", "16:15"),
    ("16:20", "17:10"),
    ("17:15", "18:05"),
]


def demo_user(username, role, password=None):
    user, created = User.objects.get_or_create(username=username, defaults={"role": role})
    if created:
        user.first_name = {
            "demo_teacher_a": "示範教師甲",
            "demo_teacher_b": "示範教師乙",
            "demo_teacher_c": "示範教師丙",
        }.get(username, "")
        if username.startswith("demo_faculty_"):
            user.first_name = f"示範教師 {username.removeprefix('demo_faculty_')}"
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
    return user


def demo_course(
    code,
    name,
    credits,
    category,
    *,
    term: int | None = 1,
    area="",
    teacher=None,
    program_type="four_year",
    department="資訊管理系",
):
    course, _ = Course.objects.get_or_create(
        code=code,
        defaults={
            "name": name,
            "credits": credits,
            "category": category,
            "teacher": teacher,
            "general_area": area,
            "recommended_term": term,
            "curriculum_year": 115,
            "is_demo": True,
            "program_type": program_type,
            "department": department,
            "description": f"{name}的教學內容與修課規劃（作業示範資料）。",
        },
    )
    if course.is_demo:
        updates = {}
        if course.curriculum_year is None:
            updates["curriculum_year"] = 115
        if course.program_type != program_type:
            updates["program_type"] = program_type
        if course.department != department:
            updates["department"] = department
        if updates:
            Course.objects.filter(pk=course.pk).update(**updates)
    return course


def demo_offering(
    course,
    teacher,
    day,
    first,
    last,
    room,
    section="A",
    *,
    assigned=False,
    assigned_class="",
    capacity=30,
    syllabus=None,
    min_grade=1,
    max_grade=4,
    target_grade=None,
):
    assigned_class = assigned_class or ("資管一甲" if assigned else "")
    class_label = demo_class_group(assigned_class)
    source_syllabus = demo_syllabus(course, section, syllabus)
    offering, _ = CourseOffering.objects.get_or_create(
        course=course,
        semester="115-1",
        section=section,
        defaults={
            "teacher": teacher,
            "day_of_week": day,
            "start_time": time.fromisoformat(PERIODS[first - 1][0]),
            "end_time": time.fromisoformat(PERIODS[last - 1][1]),
            "room": room,
            "capacity": capacity,
            "class_label": class_label,
            "target_grade": target_grade,
            "assigned_class": assigned_class,
            "min_grade": min_grade,
            "max_grade": max_grade,
            "syllabus": source_syllabus,
        },
    )
    updates = {}
    if offering.class_label != class_label and (
        not offering.class_label or offering.class_label.startswith(("四技", "二技"))
    ):
        updates["class_label"] = class_label
    if target_grade is not None and offering.target_grade != target_grade:
        updates["target_grade"] = target_grade
    if (
        offering.course.is_demo
        and offering.syllabus.get("is_demo")
        and len(offering.syllabus.get("weeks", [])) < 18
    ):
        updates["syllabus"] = demo_syllabus(course, section, offering.syllabus)
    if updates:
        CourseOffering.objects.filter(pk=offering.pk).update(**updates)
    return offering


def move_demo_offering(code, section, teacher, day, first, last, room=None):
    offering = CourseOffering.objects.filter(
        course__code="NTUB115-" + code,
        course__is_demo=True,
        semester="115-1",
        section=section,
    ).first()
    if not offering:
        return
    start, end = time.fromisoformat(PERIODS[first - 1][0]), time.fromisoformat(PERIODS[last - 1][1])
    if (
        offering.day_of_week,
        offering.start_time,
        offering.end_time,
        offering.teacher_id,
        offering.room,
    ) != (
        day,
        start,
        end,
        teacher.pk,
        room or offering.room,
    ):
        offering.day_of_week, offering.start_time, offering.end_time = day, start, end
        offering.teacher = teacher
        if room:
            offering.room = room
        offering.save()


class Command(BaseCommand):
    help = "建立大學 115 屆資管四技選課 Demo 種子，重複執行不重複新增。"

    @transaction.atomic
    def handle(self, *args, **options):
        student = demo_user(
            "demo_student",
            "student",
            environ.get("DEMO_STUDENT_PASSWORD", "Demo1234!"),
        )
        teacher_a = demo_user(
            "demo_teacher_a", "teacher", environ.get("DEMO_TEACHER_PASSWORD", "Demo1234!")
        )
        teacher_b = demo_user(
            "demo_teacher_b", "teacher", environ.get("DEMO_TEACHER_PASSWORD", "Demo1234!")
        )
        teacher_c = demo_user("demo_teacher_c", "teacher")
        student_b = demo_user(
            "demo_student_b", "student", environ.get("DEMO_STUDENT_PASSWORD", "Demo1234!")
        )
        student_two = demo_user(
            "demo_student_two_year", "student", environ.get("DEMO_STUDENT_PASSWORD", "Demo1234!")
        )
        StudentProfile.objects.get_or_create(
            student=student_b,
            defaults={
                "grade": 1,
                "admission_year": 115,
                "class_name": "資管一乙",
                "semester": "115-1",
            },
        )
        StudentProfile.objects.get_or_create(
            student=student_two,
            defaults={
                "grade": 1,
                "admission_year": 115,
                "program_type": "two_year",
                "class_name": "資管二技一甲",
                "semester": "115-1",
            },
        )
        occupied = demo_user("demo_seat_taken", "student")
        StudentProfile.objects.get_or_create(
            student=student,
            defaults={
                "grade": 1,
                "admission_year": 115,
                "class_name": "資管一甲",
                "semester": "115-1",
            },
        )

        # Bring existing Demo rows to the new Wednesday-afternoon schedule safely.
        move_demo_offering("103", "B", teacher_c, 2, 1, 3)
        move_demo_offering("103", "A", teacher_b, 2, 5, 7)
        move_demo_offering("104", "A", teacher_a, 1, 8, 9, room="示範教室C")

        required = [
            ("001", "程式設計（一）", 3, "required", 0, 1, 3),
            ("002", "管理學", 3, "required", 0, 5, 7),
            ("003", "計算機概論", 3, "required", 1, 1, 3),
            ("004", "經濟學", 3, "required", 1, 5, 7),
            ("005", "大學國文選（一）", 2, "general_base", 2, 5, 6),
            ("006", "英文（一）", 2, "general_base", 2, 7, 8),
            ("007", "現代商業導論與學習方法", 2, "required", 3, 1, 2),
            ("008", "體育（一）", 0, "pe", 4, 1, 2),
        ]
        for code, name, credits, category, day, first, last in required:
            course = demo_course("NTUB115-" + code, name, credits, category, teacher=teacher_a)
            offering = demo_offering(
                course,
                teacher_a,
                day,
                first,
                last,
                "示範原班教室",
                assigned=True,
                target_grade=1,
            )
            if code in ("005", "006"):
                move_demo_offering(code, "A", teacher_a, day, first, last)
            Enrollment.objects.get_or_create(
                student=student, offering=offering, defaults={"is_assigned": True}
            )
            offering_b = demo_offering(
                course,
                teacher_c,
                day,
                first,
                last,
                "乙班示範教室",
                section="B",
                assigned_class="資管一乙",
                target_grade=1,
            )
            Enrollment.objects.get_or_create(
                student=student_b, offering=offering_b, defaults={"is_assigned": True}
            )

        electives = [
            ("101", "數位內容概論", 3, "professional_elective", "", 3, 5, 7, "A", teacher_a, 30),
            ("101", "數位內容概論", 3, "professional_elective", "", 3, 3, 4, "B", teacher_b, 30),
            (
                "102",
                "國際視野英語文課程（示範）",
                2,
                "general_interest",
                "",
                4,
                5,
                6,
                "A",
                teacher_a,
                30,
            ),
            (
                "103",
                "網站應用程式設計",
                3,
                "professional_elective",
                "",
                2,
                5,
                7,
                "A",
                teacher_b,
                30,
            ),
            (
                "103",
                "網站應用程式設計",
                3,
                "professional_elective",
                "",
                2,
                1,
                3,
                "B",
                teacher_c,
                30,
            ),
            ("104", "行銷管理", 3, "professional_elective", "", 1, 8, 9, "A", teacher_a, 1),
            (
                "105",
                "公民意識與生活（示範）",
                2,
                "general_core",
                "civic",
                1,
                8,
                9,
                "A",
                teacher_b,
                30,
            ),
            (
                "106",
                "環境與永續（示範）",
                2,
                "general_core",
                "sustainability",
                4,
                7,
                8,
                "A",
                teacher_a,
                30,
            ),
            (
                "107",
                "藝術與生活（示範）",
                2,
                "general_core",
                "aesthetics",
                3,
                8,
                9,
                "A",
                teacher_b,
                30,
            ),
        ]
        for (
            code,
            name,
            credits,
            category,
            area,
            day,
            first,
            last,
            section,
            teacher,
            capacity,
        ) in electives:
            course = demo_course(
                "NTUB115-" + code, name, credits, category, teacher=teacher_a, area=area, term=None
            )
            if code == "102" and not course.english_interest:
                course.english_interest = True
                course.save()
            syllabus = {
                "summary": f"{name}示範課綱。",
                "objectives": ["理解基礎概念", "完成學期作品"],
                "weeks": ["課程導論", "實務案例", "分組練習", "成果展示"],
                "evaluation": (
                    {"平時作業": 30, "期中專題": 30, "期末專題": 40}
                    if section == "B"
                    else {"作業": 40, "期中": 30, "期末": 30}
                ),
                "materials": "示範教材",
                "is_demo": True,
            }
            offering = demo_offering(
                course,
                teacher,
                day,
                first,
                last,
                "示範教室C" if code == "104" else "示範教室" + section,
                section,
                capacity=capacity,
                syllabus=syllabus,
            )
            if code == "104":
                Enrollment.objects.get_or_create(student=occupied, offering=offering)

        future = [
            ("201", "程式設計（二）", 3, 2),
            ("202", "Python 程式設計", 3, 2),
            ("203", "資料結構", 3, 3),
            ("204", "資料庫管理", 3, 3),
            ("205", "資訊網路", 3, 4),
            ("206", "作業系統", 3, 4),
            ("207", "資訊管理實務專題一", 3, 7),
            ("208", "資訊管理實務專題二", 3, 8),
            ("209", "微積分（一）", 3, 2),
            ("210", "會計學", 3, 2),
            ("211", "統計學", 3, 3),
            ("212", "管理數學", 3, 3),
            ("213", "物件導向系統分析與設計", 3, 4),
            ("214", "電子商務與網路行銷", 3, 4),
            ("215", "資訊安全", 3, 5),
            ("216", "管理資訊系統", 3, 5),
            ("217", "資訊倫理與法律", 2, 5),
            ("218", "行動商務應用", 3, 6),
            ("219", "科技英文導讀", 2, 6),
            ("220", "資管講座", 2, 7),
        ]
        saved = {}
        for code, name, credits, term in future:
            saved[code] = demo_course(
                "NTUB115-" + code, name, credits, "required", term=term, teacher=teacher_a
            )
        CoursePrerequisite.objects.get_or_create(
            course=saved["203"],
            required_course=saved["201"],
        )
        # Expanded catalogue: all additional courses, teachers and timetables are fictional.
        # Code, department and degree system are stable so rerunning this command is safe.
        extended = [
            ("301", "人工智慧概論", 3, "資訊管理系", "four_year", 1, 2),
            ("302", "資料視覺化", 2, "資訊管理系", "four_year", 1, 1),
            ("303", "雲端運算與應用", 3, "資訊管理系", "four_year", 2, 1),
            ("304", "網路安全實務", 3, "資訊管理系", "four_year", 2, 1),
            ("305", "使用者介面設計", 2, "資訊管理系", "four_year", 1, 2),
            ("306", "機器學習導論", 3, "資訊管理系", "four_year", 2, 1),
            ("307", "系統分析與設計", 3, "資訊管理系", "four_year", 2, 2),
            ("308", "企業資源規劃", 3, "資訊管理系", "four_year", 3, 1),
            ("309", "數位行銷實務", 2, "資訊管理系", "four_year", 1, 1),
            ("310", "行動應用程式設計", 3, "資訊管理系", "four_year", 2, 1),
            ("311", "資料庫系統實作", 2, "資訊管理系", "four_year", 1, 1),
            ("312", "專案管理", 2, "資訊管理系", "four_year", 3, 1),
            ("401", "企業經營管理概論", 2, "企業管理系", "four_year", 1, 1),
            ("402", "商用英文簡報", 2, "應用外語系", "four_year", 1, 1),
            ("403", "投資與理財", 2, "財務金融系", "four_year", 1, 1),
            ("404", "會計資訊應用", 3, "會計資訊系", "four_year", 1, 1),
            ("405", "行銷企劃實務", 3, "企業管理系", "four_year", 2, 1),
            ("406", "國際商務溝通", 2, "國際商務系", "four_year", 1, 1),
            ("501", "進階資料庫應用", 3, "資訊管理系", "two_year", 1, 2),
            ("502", "ERP 企業實務", 3, "資訊管理系", "two_year", 1, 2),
            ("503", "資料探勘", 3, "資訊管理系", "two_year", 1, 1),
            ("504", "商業智慧分析", 3, "資訊管理系", "two_year", 2, 1),
            ("505", "資訊管理專題", 3, "資訊管理系", "two_year", 1, 1),
            ("506", "二技雲端服務實務", 2, "資訊管理系", "two_year", 2, 1),
            ("601", "二技數位行銷", 2, "企業管理系", "two_year", 1, 1),
            ("602", "二技財務管理", 3, "財務金融系", "two_year", 1, 1),
        ]
        for index, (code, name, credits, dept, program, grade, sections) in enumerate(extended):
            required_two_year = code in {"501", "502", "505"}
            category = "required" if required_two_year else "professional_elective"
            course = demo_course(
                "NTUB-DEMO-" + code,
                name,
                credits,
                category,
                term=1 if required_two_year else None,
                program_type=program,
                department=dept,
            )
            if sections == 1:
                # Remove only unused, untouched duplicate demo B offerings from earlier seeds.
                CourseOffering.objects.filter(
                    course=course,
                    semester="115-1",
                    section="B",
                    room=f"示範-{code}-B",
                    enrollments__isnull=True,
                    meetings__isnull=True,
                ).delete()
            for offset, section in enumerate(("A", "B")[:sections]):
                teacher = demo_user(f"demo_faculty_{code}_{section}", "teacher")
                first = (1, 3, 5, 7)[(index + offset) % 4]
                day = (index + offset * 2) % 5
                offer = demo_offering(
                    course,
                    teacher,
                    day,
                    first,
                    first + 2,
                    f"示範-{code}-{section}",
                    section=section,
                    capacity=25 + index % 18,
                    assigned_class="資管二技一甲" if required_two_year and section == "A" else "",
                    min_grade=grade,
                    max_grade=4 if program == "four_year" else 2,
                    target_grade=grade,
                )
                if required_two_year and section == "A":
                    Enrollment.objects.get_or_create(
                        student=student_two,
                        offering=offer,
                        defaults={"is_assigned": True},
                    )
        self.stdout.write(
            self.style.SUCCESS("Demo 資料已就緒：四技／二技、資訊管理系甲乙班與跨系班別。")
        )
