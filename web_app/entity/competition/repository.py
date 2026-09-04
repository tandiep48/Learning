"""
entity/competition/repository.py
-----------------------------------
All database queries and mutations for the multiplayer "Learn Together"
(vocab competition) feature using SQLAlchemy ORM — rooms, membership,
chat, sessions, scores and answers.

No raw SQL strings — all queries go through the ORM session. Session
lifecycle (commit/rollback/remove) is owned by the service layer.
"""

from sqlalchemy import select, update, func, case, and_, literal, literal_column
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from entity.user.entity import User
from entity.competition.entity import (
    CompetitionRoom,
    CompetitionRoomMember,
    CompetitionChatMessage,
    CompetitionSession,
    CompetitionScore,
    CompetitionVocabAnswer,
)


class CompetitionRepository:
    """Encapsulates all queries/mutations for the competition tables."""

    def __init__(self, session: Session):
        self.session = session

    # ------------------------------------------------------------------
    # Rooms
    # ------------------------------------------------------------------

    def insert_room(self, room_code, host_user_id, level, passage_ids, word_count,
                     max_users, section_timeout_minutes,
                     category="vocab", activity_type="all"):
        return self.session.execute(
            pg_insert(CompetitionRoom)
            .values(
                room_code=room_code, host_user_id=host_user_id, category=category,
                activity_type=activity_type,
                level=level, passage_ids=list(passage_ids), word_count=word_count,
                max_users=max_users, section_timeout_minutes=section_timeout_minutes,
                status="waiting",
            )
            .returning(CompetitionRoom.id)
        ).scalar_one()

    def update_room_settings(self, room_id, category, activity_type, level, passage_ids,
                              word_count, max_users, section_timeout_minutes):
        self.session.execute(
            update(CompetitionRoom)
            .where(CompetitionRoom.id == room_id)
            .values(
                category=category, activity_type=activity_type,
                level=level, passage_ids=list(passage_ids),
                word_count=word_count, max_users=max_users,
                section_timeout_minutes=section_timeout_minutes,
                updated_at=func.now(),
            )
        )

    def upsert_room_member(self, room_id, user_id, role, status="online"):
        self.session.execute(
            pg_insert(CompetitionRoomMember)
            .values(room_id=room_id, user_id=user_id, role=role, status=status)
            .on_conflict_do_update(
                index_elements=["room_id", "user_id"],
                set_={
                    "role": role, "status": status,
                    "left_at": None, "last_seen_at": func.now(),
                },
            )
        )

    def get_room_row(self, room_code):
        r = CompetitionRoom
        return self.session.execute(
            select(
                r.id, r.room_code, r.host_user_id, r.level, r.passage_ids, r.word_count,
                r.max_users, r.section_timeout_minutes, r.status, r.created_at, r.updated_at,
                r.category, r.activity_type,
            )
            .where(r.room_code == str(room_code).upper())
        ).first()

    def update_room_status(self, room_id, status):
        self.session.execute(
            update(CompetitionRoom)
            .where(CompetitionRoom.id == room_id)
            .values(status=status, updated_at=func.now())
        )

    def reopen_room_for_session(self, session_id):
        self.session.execute(
            update(CompetitionRoom)
            .where(
                CompetitionSession.id == session_id,
                CompetitionRoom.id == CompetitionSession.room_id,
            )
            .values(status="waiting", updated_at=func.now())
        )

    # ------------------------------------------------------------------
    # Room membership
    # ------------------------------------------------------------------

    def get_active_member_count(self, room_id):
        m = CompetitionRoomMember
        return int(self.session.execute(
            select(func.count()).select_from(m)
            .where(m.room_id == room_id, m.status != "left")
        ).scalar() or 0)

    def is_room_member(self, room_id, user_id):
        m = CompetitionRoomMember
        return self.session.execute(
            select(m.id).where(m.room_id == room_id, m.user_id == user_id)
        ).first() is not None

    def upsert_join_member(self, room_id, user_id, role):
        m = CompetitionRoomMember
        self.session.execute(
            pg_insert(m)
            .values(room_id=room_id, user_id=user_id, role=role, status="online")
            .on_conflict_do_update(
                index_elements=["room_id", "user_id"],
                set_={"status": "online", "left_at": None, "last_seen_at": func.now()},
            )
        )

    def mark_member_left(self, room_id, user_id):
        m = CompetitionRoomMember
        self.session.execute(
            update(m)
            .where(m.room_id == room_id, m.user_id == user_id)
            .values(status="left", left_at=func.now(), last_seen_at=func.now())
        )

    def get_room_members(self, room_id):
        m = CompetitionRoomMember
        return self.session.execute(
            select(m.user_id, User.username, m.role, m.status, m.joined_at)
            .select_from(m).join(User, User.id == m.user_id)
            .where(m.room_id == room_id, m.status != "left")
            .order_by(case((m.role == "host", 0), else_=1), m.joined_at)
        ).all()

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def get_recent_chat(self, room_id, limit=50):
        c = CompetitionChatMessage
        return self.session.execute(
            select(c.id, c.user_id, User.username, c.message, c.created_at)
            .select_from(c).join(User, User.id == c.user_id)
            .where(c.room_id == room_id)
            .order_by(c.created_at.desc())
            .limit(limit)
        ).all()

    def insert_chat_message(self, room_id, user_id, text):
        c = CompetitionChatMessage
        return self.session.execute(
            pg_insert(c)
            .values(room_id=room_id, user_id=user_id, message=text)
            .returning(c.id, c.created_at)
        ).first()

    def get_username(self, user_id):
        row = self.session.execute(
            select(User.username).where(User.id == user_id)
        ).first()
        return row[0] if row else None

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def get_latest_session_row(self, room_id):
        s = CompetitionSession
        return self.session.execute(
            select(s.id, s.status, s.current_section, s.section_started_at,
                   s.section_ends_at, s.started_at, s.finished_at)
            .where(s.room_id == room_id)
            .order_by(s.id.desc())
            .limit(1)
        ).first()

    def get_latest_session_id(self, room_id):
        return self.session.execute(
            select(CompetitionSession.id)
            .where(CompetitionSession.room_id == room_id)
            .order_by(CompetitionSession.id.desc())
            .limit(1)
        ).first()

    def insert_session(self, room_id, minutes, category="vocab", lesson_tasks=None):
        return self.session.execute(
            pg_insert(CompetitionSession)
            .values(
                room_id=room_id, status="running", current_section=category,
                section_started_at=func.now(),
                section_ends_at=func.now() + literal_column("interval '1 minute'") * minutes,
                started_at=func.now(), lesson_tasks=lesson_tasks,
            )
            .returning(CompetitionSession.id)
        ).scalar_one()

    def seed_scores_for_session(self, session_id, room_id):
        self.session.execute(
            pg_insert(CompetitionScore)
            .from_select(
                ["session_id", "user_id"],
                select(literal(session_id), CompetitionRoomMember.user_id)
                .where(
                    CompetitionRoomMember.room_id == room_id,
                    CompetitionRoomMember.status != "left",
                ),
            )
            .on_conflict_do_nothing(index_elements=["session_id", "user_id"])
        )

    def get_session_row(self, session_id):
        s = CompetitionSession
        r = CompetitionRoom
        return self.session.execute(
            select(
                s.id, s.room_id, r.room_code, s.status, s.current_section,
                s.section_started_at, s.section_ends_at, s.started_at, s.finished_at,
                r.category, r.activity_type, s.lesson_tasks,
            )
            .select_from(s).join(r, r.id == s.room_id)
            .where(s.id == session_id)
        ).first()

    def update_session_status(self, session_id, status, finished=False):
        values = {"status": status}
        if finished:
            values["finished_at"] = func.now()
        self.session.execute(
            update(CompetitionSession).where(CompetitionSession.id == session_id).values(**values)
        )

    # ------------------------------------------------------------------
    # Scores / answers
    # ------------------------------------------------------------------

    def is_session_active_for_user(self, session_id, user_id):
        """True while the session is running and the user is a scored participant."""
        return self.session.execute(
            select(literal(1))
            .select_from(CompetitionSession)
            .join(
                CompetitionScore,
                and_(
                    CompetitionScore.session_id == CompetitionSession.id,
                    CompetitionScore.user_id == user_id,
                ),
            )
            .where(CompetitionSession.id == session_id, CompetitionSession.status == "running")
        ).first() is not None

    def insert_vocab_answer(self, session_id, user_id, word, activity_type, is_correct,
                             response_time_ms, points):
        """One-shot per (session, user, word, activity_type); returns the inserted row
        (id) or None if it already existed."""
        return self.session.execute(
            pg_insert(CompetitionVocabAnswer)
            .values(
                session_id=session_id, user_id=user_id, word=word,
                activity_type=activity_type, is_correct=is_correct,
                response_time_ms=int(response_time_ms or 0), points=points,
            )
            .on_conflict_do_nothing(
                index_elements=["session_id", "user_id", "word", "activity_type"]
            )
            .returning(CompetitionVocabAnswer.id)
        ).first()

    def increment_score(self, session_id, user_id, points, response_time_ms):
        self.session.execute(
            update(CompetitionScore)
            .where(
                CompetitionScore.session_id == session_id,
                CompetitionScore.user_id == user_id,
            )
            .values(
                total_points=CompetitionScore.total_points + points,
                total_response_time_ms=CompetitionScore.total_response_time_ms + int(response_time_ms or 0),
                updated_at=func.now(),
            )
        )

    def get_scores_rows(self, session_id):
        sc = CompetitionScore
        return self.session.execute(
            select(
                sc.user_id, User.username, sc.listening_points, sc.reading_points,
                sc.total_points, sc.total_response_time_ms, sc.rank, sc.finished_at,
            )
            .select_from(sc).join(User, User.id == sc.user_id)
            .where(sc.session_id == session_id)
            .order_by(sc.total_points.desc(), sc.total_response_time_ms.asc(), User.username)
        ).all()

    def mark_score_finished(self, session_id, user_id):
        sc = CompetitionScore
        self.session.execute(
            update(sc)
            .where(sc.session_id == session_id, sc.user_id == user_id, sc.finished_at.is_(None))
            .values(finished_at=func.now(), updated_at=func.now())
        )

    def get_finished_counts(self, session_id):
        """(total, done) scored participants for a session."""
        sc = CompetitionScore
        row = self.session.execute(
            select(
                func.count().label("total"),
                func.count().filter(sc.finished_at.isnot(None)).label("done"),
            )
            .where(sc.session_id == session_id)
        ).first()
        return row[0], row[1]

    def rank_scores(self, session_id):
        sc = CompetitionScore
        ranked = (
            select(
                sc.id,
                func.row_number().over(
                    order_by=[
                        sc.total_points.desc(),
                        sc.total_response_time_ms.asc(),
                        func.coalesce(sc.finished_at, func.now()).asc(),
                    ]
                ).label("next_rank"),
            )
            .where(sc.session_id == session_id)
            .subquery("ranked")
        )
        self.session.execute(
            update(sc)
            .where(sc.id == ranked.c.id)
            .values(rank=ranked.c.next_rank, updated_at=func.now())
        )
