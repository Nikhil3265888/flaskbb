"""PostgreSQL smoke test for FlaskBB-Guard, run by the CI pipeline.

It uses a real FlaskBB installation on PostgreSQL (not the SQLite test
database) and checks that saving posts stores toxicity scores and reports
the toxic post.
"""

import os
import sys

import sqlalchemy as sa
from flaskbb import create_app
from flaskbb.extensions import db
from flaskbb.forum.models import Post, Report, Topic
from flaskbb.utils.populate import create_user


def main(config_path: str) -> int:
    app = create_app(os.path.abspath(config_path))
    with app.app_context():
        from flaskbb_guard.models import ToxicityScore

        dialect = db.engine.dialect.name
        print(f"Database: {dialect}")
        if dialect != "postgresql":
            print("FAIL: expected PostgreSQL")
            return 1

        topic = db.session.execute(sa.select(Topic).order_by(Topic.id)).scalars().first()
        member = create_user("ci_member", "Member12345", "ci_member@example.com", "member")

        safe = Post(content="Thanks, this forum is really helpful!")
        safe.save(user=member, topic=topic)
        rude = Post(content="This is a stupid idea and you are an idiot.")
        rude.save(user=member, topic=topic)

        scores = {
            s.post_id: s for s in db.session.execute(sa.select(ToxicityScore)).scalars().all()
        }
        reports = db.session.execute(sa.select(Report).filter_by(post_id=rude.id)).scalars().all()

        checks = {
            "safe post has a score": safe.id in scores,
            "rude post has a score": rude.id in scores,
            "safe post was not reported": not db.session.execute(
                sa.select(Report).filter_by(post_id=safe.id)
            ).first(),
            "rude post was reported once": len(reports) == 1,
        }
        for name, ok in checks.items():
            print(f"{'PASS' if ok else 'FAIL'}: {name}")
        for post_id, score in sorted(scores.items()):
            print(f"  post {post_id}: {score.score} {score.label} ({score.model_name})")
        return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "flaskbb.cfg"))
