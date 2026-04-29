from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "project_features.pdf"


FEATURE_SECTIONS = [
    (
        "Project Overview",
        [
            "The Online Examination System is a Django-based web application for managing digital examinations in an educational institution.",
            "The system supports three main roles: Administrator, Teacher, and Student.",
            "It covers the complete exam workflow from registration and exam creation to attempt tracking, result calculation, review, analytics, and reporting.",
        ],
    ),
    (
        "User And Authentication Features",
        [
            "Separate student and teacher registration flows.",
            "Student ID support for student accounts.",
            "Role-based dashboards for administrators, teachers, and students.",
            "Login using username, email, or student ID depending on the account.",
            "Password validation, password reset pages, and email-based reset workflow.",
            "Failed login attempt tracking with temporary account lockout.",
            "Manual account activation status support for administrative control.",
        ],
    ),
    (
        "Teacher Features",
        [
            "Create exams with title, duration, schedule, pass percentage, marking rules, instructions, and attempt limits.",
            "Publish or unpublish exams.",
            "Edit and delete exams created by the teacher.",
            "Add, edit, manage, and delete exam questions.",
            "Support both MCQ questions and written/descriptive questions.",
            "Configure correct marks and negative marks for each exam.",
            "View teacher dashboard analytics including attempts, average score, pending reviews, and weak questions.",
            "Review written answers manually, award marks, provide feedback, and recalculate final results.",
            "Export exam results in CSV and Excel-friendly formats.",
        ],
    ),
    (
        "Student Features",
        [
            "View available exams based on published status and active schedule.",
            "Read exam instructions before starting an attempt.",
            "Attempt exams only within the configured start and end time.",
            "Attempt limit handling with support for fixed limits and unlimited attempts.",
            "Answer MCQ and written questions in the same exam.",
            "Navigate between questions during the exam.",
            "Mark questions for review before final submission.",
            "View instant results for objective exams.",
            "See pending review status when written answers require teacher evaluation.",
            "View result history, profile analytics, performance trend, and average score.",
            "Access exam leaderboards for finalized results.",
        ],
    ),
    (
        "Exam Delivery Features",
        [
            "Randomized question order for each exam attempt.",
            "Randomized MCQ option order to reduce answer sharing.",
            "Real-time timer and automatic submission support.",
            "Exam availability validation for unpublished, not-started, expired, and empty exams.",
            "Session-based answer tracking during exam navigation.",
            "Clear result status labels such as Pass, Fail, and Pending Review.",
        ],
    ),
    (
        "Anti-Cheating And Monitoring Features",
        [
            "Fullscreen entry gate before starting the exam.",
            "Fullscreen exit detection and violation counting.",
            "Tab switch detection and violation counting.",
            "Copy, cut, paste, and right-click blocking during exam attempts.",
            "Webcam permission warning count support.",
            "Real-time anti-cheating state recording through AJAX.",
            "Auto-submit behavior when violation thresholds are reached.",
            "Violation counts and anti-cheating notes saved with the result.",
            "Teacher reports display tab switch, fullscreen, copy-paste, webcam, and auto-submit information.",
        ],
    ),
    (
        "Result And Analytics Features",
        [
            "Automatic score calculation for MCQ answers.",
            "Negative marking support for wrong answers.",
            "Percentage calculation and pass/fail evaluation using exam pass percentage.",
            "Pending review workflow for written answers.",
            "Question-wise performance analysis with attempts, correct count, and accuracy.",
            "Leaderboard showing top finalized scores.",
            "Teacher reports with highest score, lowest score, average score, attempted count, and weak questions.",
            "Student analytics with attempted exams, pending reviews, average percentage, and recent results.",
        ],
    ),
    (
        "Admin Features",
        [
            "Custom Django admin management dashboard.",
            "Admin summary for students, teachers, exams, published exams, results, and pending reviews.",
            "Portal settings for site name, support email, certificate title, and default pass percentage.",
            "Manage users with role labels for Admin, Teacher, and Student.",
            "Inline question and result management from the exam admin page.",
            "Bulk publish and unpublish exams.",
            "Bulk mark selected results or answers as reviewed with automatic recalculation.",
        ],
    ),
    (
        "Notification And Deployment Features",
        [
            "Email notification helper support for registration, exam creation, and result publishing workflows.",
            "Console email fallback when SMTP environment variables are not configured.",
            "Environment-driven database and deployment settings.",
            "Whitenoise support for static file serving.",
            "Gunicorn, PostgreSQL adapter, and Render-friendly deployment files included.",
            "Custom command for repeatable superuser creation in deployment environments.",
        ],
    ),
    (
        "Technology Stack",
        [
            "Backend: Python and Django 5.2.12.",
            "Frontend: HTML, CSS, JavaScript, Bootstrap-style templates, and Chart.js-ready analytics.",
            "Database: SQLite for local development with PostgreSQL deployment support.",
            "Static files: Django staticfiles and Whitenoise.",
        ],
    ),
]


def escape_pdf_text(value):
    return (
        value.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", "")
    )


def wrap_line(text, width=92):
    return textwrap.wrap(text, width=width, replace_whitespace=False) or [""]


def build_pages():
    pages = []
    current = []
    line_limit = 43

    def add_line(line="", size=10, leading=14):
        nonlocal current
        if len(current) >= line_limit:
            pages.append(current)
            current = []
        current.append((line, size, leading))

    add_line("ONLINE EXAMINATION SYSTEM", 20, 26)
    add_line("Project Features Document", 15, 22)
    add_line("Generated from the current Django project source code.", 10, 16)
    add_line("", 10, 14)

    for heading, bullets in FEATURE_SECTIONS:
        add_line(heading, 14, 20)
        for bullet in bullets:
            wrapped = wrap_line(bullet)
            for index, part in enumerate(wrapped):
                prefix = "- " if index == 0 else "  "
                add_line(prefix + part, 10, 14)
        add_line("", 10, 12)

    add_line("Conclusion", 14, 20)
    conclusion = (
        "The project provides a complete online examination platform with role-based access, "
        "secure exam delivery, automated evaluation, manual review for written answers, analytics, "
        "leaderboards, exports, and administrative controls."
    )
    for part in wrap_line(conclusion):
        add_line(part, 10, 14)

    if current:
        pages.append(current)
    return pages


def page_stream(lines, page_number, page_count):
    commands = [
        "BT",
        "/F1 10 Tf",
        "50 790 Td",
    ]
    first = True
    for text, size, leading in lines:
        if not first:
            commands.append(f"0 -{leading} Td")
        first = False
        commands.append(f"/F1 {size} Tf")
        commands.append(f"({escape_pdf_text(text)}) Tj")

    commands.append("/F1 8 Tf")
    commands.append("0 -24 Td")
    commands.append(f"(Page {page_number} of {page_count}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1", errors="replace")


def build_pdf():
    pages = build_pages()
    objects = []

    def add_object(data):
        objects.append(data)
        return len(objects)

    catalog_id = add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
    pages_id = add_object(b"")
    font_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids = []
    content_ids = []
    for page_number, lines in enumerate(pages, start=1):
        stream = page_stream(lines, page_number, len(pages))
        content_id = add_object(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_id = add_object(
            (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        content_ids.append(content_id)
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, data in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(data)
        output.extend(b"\nendobj\n")

    xref_position = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    output.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            "startxref\n"
            f"{xref_position}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    return output


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(build_pdf())
    print(OUTPUT)


if __name__ == "__main__":
    main()
