import os
from alembic import context
from sqlalchemy import create_engine
from app.service import Base
url = os.getenv("DATABASE_URL", context.config.get_main_option("sqlalchemy.url"))
with create_engine(url).connect() as conn:
    context.configure(connection=conn, target_metadata=Base.metadata); 
    with context.begin_transaction(): context.run_migrations()
