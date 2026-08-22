"""
db package
-----------
Database access split by domain, all on SQLAlchemy (see entity/database.py for
the engine/session). `from db import <name>` resolves every query function via
the re-exports below.
"""

from db.records import *    # noqa: F401,F403  (activity records / stats)
from db.competition import *  # noqa: F401,F403  (learn-together / competition)
from db.progress import *   # noqa: F401,F403  (lesson progress / recent learning)
from db.learning import *   # noqa: F401,F403  (vocab-learning & practice stats)
from db.content import *    # noqa: F401,F403  (lesson / passage content)
