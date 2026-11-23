"""A ready-made demo course, so visitors can try the course features at once.

Course code demo-acid-base, class password demo-class, teacher password demo-teacher.
Step 1: groups G01 to G06 determine the factor of the NaOH solution.
Step 2: groups G07 to G12 titrate vinegar; f_NaOH comes from step 1.
G06 and G12 have not submitted yet, so visitors can try the entry form.
"""
import random

from . import db
from .auth import hash_password
from .chain import step_result
from .synthetic import sim_naoh, sim_vinegar

CODE = "demo-acid-base"
CLASS_PASSWORD = "demo-class"
TEACHER_PASSWORD = "demo-teacher"


def seed_demo_course(conn) -> None:
    if db.get_course(conn, CODE):
        return
    db.create_course(conn, CODE, "Demo course: acid-base chain", 12, 6,
                     hash_password(TEACHER_PASSWORD), hash_password(CLASS_PASSWORD))
    s1 = db.add_step(conn, CODE, "naoh-titer", "Find the factor of our NaOH solution",
                     db.group_codes(12)[:6], {})
    s2 = db.add_step(conn, CODE, "vinegar-acetic-acid", "Acetic acid in the class vinegar",
                     db.group_codes(12)[6:], {"f_NaOH": s1})
    rng = random.Random("demo-course")
    for i, code in enumerate(db.group_codes(12)[:5]):
        mech = "overshoot" if code == "G03" else None
        runs = [sim_naoh(rng, mech) for _ in range(3)]
        db.insert_submission(conn, "naoh-titer", code, i % 5 + 1, runs, "synthetic", step_id=s1)
    f, _ = step_result(conn, db.get_step(conn, s1))
    for i, code in enumerate(db.group_codes(12)[6:11]):
        runs = [sim_vinegar(rng, None) for _ in range(3)]
        for r in runs:
            r["f_NaOH"] = round(f, 4)
        db.insert_submission(conn, "vinegar-acetic-acid", code, i % 5 + 1, runs, "synthetic", step_id=s2)
