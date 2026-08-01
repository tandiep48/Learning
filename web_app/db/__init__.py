"""
db package
-----------
Database access split by domain. `from db import <name>` still resolves every
former db.py function via the re-exports below.
"""

from db.connection import *  # noqa: F401,F403  (connection + DB config)
from db.records import *    # noqa: F401,F403  (activity records / stats)
from db.user import *       # noqa: F401,F403  (users / profile)
from db.competition import *  # noqa: F401,F403  (learn-together / competition)
from db.progress import *   # noqa: F401,F403  (lesson progress / recent learning)
from db.learning import *   # noqa: F401,F403  (vocab-learning & practice stats)
from db.content import *    # noqa: F401,F403  (lesson / passage content)
