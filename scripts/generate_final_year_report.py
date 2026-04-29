from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "final_year_project_report.pdf"


REPORT_SECTIONS = [
    (
        "Certificate",
        [
            "This is to certify that the project titled Online Examination System has been developed as a final year project using Python and Django.",
            "The project demonstrates the design and implementation of a web-based examination platform for students, teachers, and administrators.",
            "The work includes user authentication, exam management, secure exam delivery, result processing, analytics, and deployment support.",
        ],
    ),
    (
        "Acknowledgement",
        [
            "I would like to express sincere gratitude to my teachers, mentors, friends, and family for their guidance and encouragement during the development of this project.",
            "Their support helped in understanding the practical requirements of an online examination system and in completing the project successfully.",
        ],
    ),
    (
        "Abstract",
        [
            "The Online Examination System is a Django-based web application designed to conduct, manage, and evaluate examinations digitally.",
            "The system provides separate interfaces for students, teachers, and administrators. Teachers can create exams, schedule them, add questions, configure marks, and review answers.",
            "Students can register, log in, view available exams, attempt exams, and check results. Administrators can manage users, exams, results, and portal settings.",
            "The project also includes anti-cheating controls, randomized questions, randomized options, negative marking, leaderboards, profile analytics, email support, and deployment-ready configuration.",
        ],
    ),
    (
        "Introduction",
        [
            "Traditional examination systems require physical classrooms, printed question papers, manual checking, and large administrative effort.",
            "An online examination system reduces paperwork, saves time, improves result accuracy, and allows exams to be conducted in a controlled digital environment.",
            "This project provides an end-to-end solution for educational institutions that want to conduct objective and written examinations through a web application.",
        ],
    ),
    (
        "Problem Statement",
        [
            "Manual examination processes are time-consuming and prone to errors in scheduling, evaluation, result calculation, and record maintenance.",
            "Institutions require a system where teachers can create exams, students can attempt them securely, and results can be generated automatically or reviewed manually when required.",
            "The project aims to solve these problems by creating a centralized online exam portal with role-based access and automated workflows.",
        ],
    ),
    (
        "Objectives",
        [
            "To develop a web-based platform for conducting online examinations.",
            "To provide separate dashboards for administrators, teachers, and students.",
            "To allow teachers to create, publish, schedule, and manage exams.",
            "To support multiple question types including MCQ and written answers.",
            "To calculate objective results automatically with negative marking support.",
            "To provide manual review workflow for written answers.",
            "To include anti-cheating controls such as tab-switch and fullscreen violation tracking.",
            "To provide reports, leaderboards, and student performance analytics.",
            "To support deployment using Gunicorn, Whitenoise, and PostgreSQL-ready configuration.",
        ],
    ),
    (
        "Scope Of The Project",
        [
            "The system can be used by schools, colleges, coaching centers, and training institutes for conducting online tests.",
            "It supports local development with SQLite and production deployment with PostgreSQL.",
            "The current scope includes exam creation, scheduling, attempt management, result calculation, analytics, and admin management.",
            "The system can be extended in the future with certificate generation, advanced proctoring, SMS notifications, and payment integration if required.",
        ],
    ),
    (
        "Technology Stack",
        [
            "Backend: Python and Django 5.2.12.",
            "Frontend: HTML, CSS, JavaScript, Bootstrap-style templates, and Chart.js-ready analytics.",
            "Database: SQLite for local development and PostgreSQL support for deployment.",
            "Static File Serving: Django staticfiles and Whitenoise.",
            "Deployment: Render-compatible setup using Gunicorn and environment variables.",
            "Email: SMTP support using Gmail App Password or any compatible SMTP provider.",
        ],
    ),
    (
        "System Users",
        [
            "Administrator: Manages users, exams, results, portal settings, and overall system data.",
            "Teacher: Creates exams, manages questions, reviews written answers, and views exam reports.",
            "Student: Registers, logs in, attempts exams, views results, leaderboards, and profile analytics.",
        ],
    ),
    (
        "Main Modules",
        [
            "Authentication Module: Handles login, registration, password reset, account roles, and student ID support.",
            "Exam Management Module: Allows teachers to create, edit, publish, schedule, and delete exams.",
            "Question Management Module: Supports MCQ and written questions with answer options and correct answer configuration.",
            "Exam Attempt Module: Provides exam instructions, timer, question navigation, answer saving, and submission.",
            "Evaluation Module: Calculates MCQ scores automatically and supports manual review for written answers.",
            "Analytics Module: Shows teacher reports, student performance, leaderboards, average scores, and weak question analysis.",
            "Admin Module: Provides administrative control over users, exams, results, and portal settings.",
            "Notification Module: Supports email-based password reset and notification workflows.",
        ],
    ),
    (
        "Functional Requirements",
        [
            "The system shall allow student and teacher registration.",
            "The system shall allow users to log in according to their assigned role.",
            "The system shall allow teachers to create and manage exams.",
            "The system shall allow teachers to add, edit, and delete questions.",
            "The system shall allow students to attempt active and published exams.",
            "The system shall prevent students from attempting expired or unpublished exams.",
            "The system shall calculate scores, percentages, and pass or fail status.",
            "The system shall allow teachers to review written answers and update results.",
            "The system shall display leaderboards and result history.",
            "The system shall allow administrators to manage system data through Django admin.",
        ],
    ),
    (
        "Non Functional Requirements",
        [
            "Security: The system uses authentication, role-based access, CSRF protection, password validation, and secure deployment settings.",
            "Reliability: The system validates exam availability, attempt limits, and result states to reduce incorrect submissions.",
            "Usability: The application provides simple dashboards and clear workflows for each role.",
            "Maintainability: The project follows Django app structure with separate accounts and exams modules.",
            "Scalability: PostgreSQL and deployment-ready settings allow the project to be hosted in a production environment.",
        ],
    ),
    (
        "Database Design",
        [
            "The database stores users, roles, exams, questions, result records, answer records, and portal settings.",
            "The custom user model supports account roles and student ID information.",
            "The exam model stores scheduling, marking rules, instructions, publication status, and attempt limits.",
            "The question model stores MCQ and written question details.",
            "The result and result answer models store submitted answers, awarded marks, review status, and anti-cheating information.",
        ],
    ),
    (
        "Security And Anti Cheating",
        [
            "The project includes failed login attempt tracking and temporary account lockout support.",
            "During exams, the system can track fullscreen exits, tab switches, copy-paste actions, webcam warnings, and automatic submissions.",
            "These details are stored with the result so that teachers can review suspicious activity.",
            "The deployed application can use HTTPS, secure cookies, CSRF protection, and environment-based secret configuration.",
        ],
    ),
    (
        "Testing",
        [
            "The project includes Django tests for authentication, exam workflows, result processing, and email-related behavior.",
            "Testing verifies that students can attempt exams, teachers can manage exams, and results are calculated correctly.",
            "Additional manual testing was performed for login, registration, exam creation, exam attempt, result viewing, and admin workflows.",
        ],
    ),
    (
        "Deployment",
        [
            "The project is prepared for deployment on Render using Gunicorn as the application server.",
            "Whitenoise is used for serving static files in production.",
            "Environment variables are used for secret key, debug mode, allowed hosts, database URL, email credentials, and password reset domain.",
            "PostgreSQL can be connected using the DATABASE_URL environment variable.",
            "The project includes a custom ensure_superuser command for creating or updating an admin user during deployment.",
        ],
    ),
    (
        "Advantages",
        [
            "Reduces paper usage and manual checking effort.",
            "Provides fast result generation for objective questions.",
            "Supports flexible exam scheduling and attempt limits.",
            "Improves transparency through reports and leaderboards.",
            "Provides role-based workflows for students, teachers, and administrators.",
            "Can be hosted online and accessed from different locations.",
        ],
    ),
    (
        "Limitations",
        [
            "Advanced live proctoring is not fully implemented.",
            "Internet connectivity is required for online use.",
            "Subjective answers still require manual review by teachers.",
            "The system depends on correct environment configuration for production email and database services.",
        ],
    ),
    (
        "Future Scope",
        [
            "Certificate generation for passed students.",
            "Advanced webcam-based proctoring and face detection.",
            "SMS or WhatsApp notifications.",
            "Question bank import from Excel or CSV files.",
            "Detailed subject-wise analytics.",
            "Payment integration for paid examinations or courses.",
            "Mobile application support.",
        ],
    ),
    (
        "Conclusion",
        [
            "The Online Examination System successfully provides a complete platform for managing digital examinations.",
            "It reduces manual effort, improves result accuracy, and provides useful dashboards for students, teachers, and administrators.",
            "The project demonstrates practical use of Django, database design, role-based access, result processing, security controls, and deployment configuration.",
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

    add_line("ONLINE EXAMINATION SYSTEM", 20, 28)
    add_line("Final Year Project Report", 16, 24)
    add_line("Submitted in partial fulfillment of the requirements for the final year project.", 10, 16)
    add_line("", 10, 16)
    add_line("Submitted By: Student Name", 11, 16)
    add_line("Department: Computer Science / Information Technology", 11, 16)
    add_line("Academic Year: 2025-2026", 11, 16)
    add_line("", 10, 16)
    add_line("Project Guide: Faculty Guide Name", 11, 16)
    add_line("Institution: Institution Name", 11, 16)
    add_line("", 10, 16)

    add_line("Table Of Contents", 14, 20)
    for index, (heading, _) in enumerate(REPORT_SECTIONS, start=1):
        add_line(f"{index}. {heading}", 10, 14)
    add_line("", 10, 16)

    for index, (heading, paragraphs) in enumerate(REPORT_SECTIONS, start=1):
        add_line(f"{index}. {heading}", 14, 20)
        for paragraph in paragraphs:
            wrapped = wrap_line(paragraph)
            for part_index, part in enumerate(wrapped):
                add_line(part, 10, 14)
            add_line("", 10, 8)
        add_line("", 10, 10)

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
    commands.append(f"(Online Examination System | Page {page_number} of {page_count}) Tj")
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
