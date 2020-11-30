from os import supports_dir_fd
from aiohttp import web
from pathlib import Path
import jinja2
import psycopg2.errors

from urllib.parse import urlencode

from dbconn import db_block

home_path = Path(__file__).parent
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(home_path)))


async def view_list_grades(request):
    with db_block() as db:
        db.execute("""
        SELECT sn AS stu_sn, name as stu_name FROM student ORDER BY name
        """)
        students = list(db)

        db.execute("""
        SELECT sn AS cou_sn, name as cou_name FROM course ORDER BY name
        """)
        courses = list(db)

        db.execute("""
        SELECT g.stu_sn, g.cou_sn, 
            s.name as stu_name, 
            c.name as cou_name, 
            g.grade 
        FROM course_grade as g
            INNER JOIN student as s ON g.stu_sn = s.sn
            INNER JOIN course as c  ON g.cou_sn = c.sn
        ORDER BY stu_sn, cou_sn;
        """)

        items = list(db)

    webpage = jinja_env.get_template('list.html').render(students=students,
                                                         courses=courses,
                                                         items=items)
    return web.Response(text=webpage, content_type="text/html")


def view_grade_editor(request):
    stu_sn = request.match_info.get("stu_sn")
    cou_sn = request.match_info.get("cou_sn")
    if stu_sn is None or cou_sn is None:
        return web.HTTPBadRequest(text="stu_sn, cou_sn, must be required")

    with db_block() as db:
        db.execute("""
        SELECT grade FROM course_grade
            WHERE stu_sn = %(stu_sn)s AND cou_sn = %(cou_sn)s;
        """, dict(stu_sn=stu_sn, cou_sn=cou_sn))

        record = db.fetch_first()

    if record is None:
        return web.HTTPNotFound(text=f"no such grade: stu_sn={stu_sn}, cou_sn={cou_sn}")

    webpage = jinja_env.get_template('edit.html').render(stu_sn=stu_sn,
                                                         cou_sn=cou_sn,
                                                         grade=record.grade)
    return web.Response(text=webpage, content_type="text/html")

def grade_deletion_dialog(request):
    stu_sn = request.match_info.get("stu_sn")
    cou_sn = request.match_info.get("cou_sn")
    if stu_sn is None or cou_sn is None:
        return web.HTTPBadRequest(text="stu_sn, cou_sn, must be required")

    with db_block() as db:
        db.execute("""
        SELECT g.stu_sn, g.cou_sn, 
            s.name as stu_name, 
            c.name as cou_name, 
            g.grade 
        FROM course_grade as g
            INNER JOIN student as s ON g.stu_sn = s.sn
            INNER JOIN course as c  ON g.cou_sn = c.sn
        WHERE stu_sn = %(stu_sn)s AND cou_sn = %(cou_sn)s;
        """, dict(stu_sn=stu_sn, cou_sn=cou_sn))

        record = db.fetch_first()

    if record is None:
        return web.HTTPNotFound(text=f"no such grade: stu_sn={stu_sn}, cou_sn={cou_sn}")

    webpage = jinja_env.get_template('grade_dialog_deletion.html').render(record=record)
    return web.Response(text=webpage, content_type="text/html")


async def dialog_error(request):
    message = request.query.get("message")
    return_path = request.query.get("return")

    webpage = jinja_env.get_template('dialog_error.html').render(message=message,
                                                                 return_path=return_path)
    return web.Response(text=webpage, content_type="text/html")


async def action_grade_add(request):
    params = await request.post()
    stu_sn = params.get("stu_sn")
    cou_sn = params.get("cou_sn")
    grade = params.get("grade")

    if stu_sn is None or cou_sn is None or grade is None:
        return web.HTTPBadRequest(text="stu_sn, cou_sn, grade must be required")

    try:
        stu_sn = int(stu_sn)
        cou_sn = int(cou_sn)
        grade = float(grade)
    except ValueError:
        return web.HTTPBadRequest(text="invalid value")

    try:
        with db_block() as db:
            db.execute("""
            INSERT INTO course_grade (stu_sn, cou_sn, grade) 
            VALUES ( %(stu_sn)s, %(cou_sn)s, %(grade)s)
            """, dict(stu_sn=stu_sn, cou_sn=cou_sn, grade=grade))
    except psycopg2.errors.UniqueViolation:
        query = urlencode({
            "message": "已经添加该学生的课程成绩",
            "return": "/"
        })
        return web.HTTPFound(location=f"/error?{query}")
    except psycopg2.errors.ForeignKeyViolation as ex:
        return web.HTTPBadRequest(text=f"无此学生或课程: {ex}")

    return web.HTTPFound(location="/")


async def edit_grade_action(request):
    stu_sn = request.match_info.get("stu_sn")
    cou_sn = request.match_info.get("cou_sn")
    if stu_sn is None or cou_sn is None:
        return web.HTTPBadRequest(text="stu_sn, cou_sn, must be required")

    params = await request.post()
    grade = params.get("grade")

    try:
        stu_sn = int(stu_sn)
        cou_sn = int(cou_sn)
        grade = float(grade)
    except ValueError:
        return web.HTTPBadRequest(text="invalid value")

    with db_block() as db:
        db.execute("""
        UPDATE course_grade SET grade=%(grade)s
        WHERE stu_sn = %(stu_sn)s AND cou_sn = %(cou_sn)s
        """, dict(stu_sn=stu_sn, cou_sn=cou_sn, grade=grade))

    return web.HTTPFound(location="/")


def delete_grade_action(request):
    stu_sn = request.match_info.get("stu_sn")
    cou_sn = request.match_info.get("cou_sn")
    if stu_sn is None or cou_sn is None:
        return web.HTTPBadRequest(text="stu_sn, cou_sn, must be required")

    with db_block() as db:
        db.execute("""
        DELETE FROM course_grade
            WHERE stu_sn = %(stu_sn)s AND cou_sn = %(cou_sn)s
        """, dict(stu_sn=stu_sn, cou_sn=cou_sn))

    return web.HTTPFound(location="/")


app = web.Application()
app.add_routes([
    web.get('/', view_list_grades),
    web.get('/error', dialog_error),
    web.get('/grade/edit/{stu_sn}/{cou_sn}', view_grade_editor),
    web.get('/grade/delete/{stu_sn}/{cou_sn}', grade_deletion_dialog),
    web.post('/action/grade/add', action_grade_add),
    web.post('/action/grade/edit/{stu_sn}/{cou_sn}', edit_grade_action),
    web.post('/action/grade/delete/{stu_sn}/{cou_sn}', delete_grade_action),
    web.static("/", home_path / "static"),
])

if __name__ == "__main__":
    web.run_app(app, port=8080)
